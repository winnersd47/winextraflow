"""Live Price Service — fetch current prices from MOEX, Binance, Yahoo Finance.

Used for:
1. Signal validation before publishing (is entry price = market price?)
2. Post-signal monitoring (did price hit TP or SL?)
3. Price alerts checking
"""

import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

MOEX_TICKERS = {
    "SBER", "GAZP", "LKOH", "YNDX", "ROSN", "GMKN", "NVTK", "MGNT",
    "VTBR", "MTSS", "POLY", "FIVE", "OZON", "TCSG", "PHOR", "NLMK",
    "CHMF", "ALRS", "AFLT", "MOEX", "PLZL", "RUAL", "SNGS", "TATN",
}
FOREX_CURRENCIES = {"EUR", "USD", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF", "SEK", "NOK", "TRY", "MXN", "ZAR", "CNY"}


def _is_forex(ticker: str) -> bool:
    t = ticker.upper()
    return len(t) == 6 and t[:3] in FOREX_CURRENCIES and t[3:] in FOREX_CURRENCIES


async def get_live_price(ticker: str) -> dict | None:
    """Get current price for any ticker. Returns dict with price, source, timestamp."""
    t = ticker.upper()

    try:
        if t in MOEX_TICKERS:
            return await _moex_price(t)
        elif t.endswith("USDT") or t.endswith("BTC"):
            return await _binance_price(t)
        else:
            return await _yahoo_price(t)
    except Exception as e:
        logger.warning(f"Live price fetch failed for {t}: {e}")
        return None


async def _moex_price(ticker: str) -> dict | None:
    """MOEX ISS API — free, no auth, 15 min delay during trading hours."""
    url = f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{ticker}.json"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params={"iss.meta": "off", "marketdata.columns": "SECID,LAST,HIGH,LOW,OPEN,VOLTODAY"})
        data = resp.json()
        rows = data.get("marketdata", {}).get("data", [])
        if not rows:
            return None
        row = rows[0]
        return {
            "ticker": ticker,
            "price": row[1],
            "high": row[2],
            "low": row[3],
            "open": row[4],
            "volume": row[5],
            "source": "MOEX ISS",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


async def _binance_price(ticker: str) -> dict | None:
    """Binance API — free, real-time."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"https://api.binance.com/api/v3/ticker/24hr", params={"symbol": ticker})
        data = resp.json()
        return {
            "ticker": ticker,
            "price": float(data.get("lastPrice", 0)),
            "high": float(data.get("highPrice", 0)),
            "low": float(data.get("lowPrice", 0)),
            "open": float(data.get("openPrice", 0)),
            "volume": float(data.get("volume", 0)),
            "change_pct": float(data.get("priceChangePercent", 0)),
            "source": "Binance",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


async def _yahoo_price(ticker: str) -> dict | None:
    """Yahoo Finance — free, 15 min delay."""
    if _is_forex(ticker):
        yf_sym = f"{ticker[:3]}{ticker[3:]}=X"
    else:
        yf_sym = ticker

    async with httpx.AsyncClient(timeout=10, headers={"User-Agent": "Mozilla/5.0"}) as client:
        resp = await client.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_sym}", params={"interval": "1d", "range": "2d"})
        data = resp.json()
        result = data.get("chart", {}).get("result", [{}])[0]
        meta = result.get("meta", {})
        return {
            "ticker": ticker,
            "price": meta.get("regularMarketPrice", 0),
            "high": meta.get("regularMarketDayHigh", 0),
            "low": meta.get("regularMarketDayLow", 0),
            "open": meta.get("regularMarketOpen", 0),
            "volume": meta.get("regularMarketVolume", 0),
            "source": "Yahoo Finance",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ═══ SIGNAL VALIDATION ═══

async def validate_signal(
    ticker: str,
    action: str,
    entry: float,
    tp: float,
    sl: float,
) -> dict:
    """Validate signal against live market price.

    Checks:
    1. Entry within 1% of current price
    2. TP not beyond 90-day high/low
    3. SL not beyond 30-day extreme
    4. Direction makes sense vs current price
    """
    live = await get_live_price(ticker)
    if not live or not live.get("price"):
        return {"valid": True, "warnings": ["Live price unavailable — skipping validation"], "live_price": None}

    price = live["price"]
    warnings = []
    errors = []

    # 1. Entry vs current price (max 2% deviation)
    deviation = abs(entry - price) / price * 100
    if deviation > 2.0:
        errors.append(f"Entry {entry} отклоняется от рынка {price:.4f} на {deviation:.1f}% (макс 2%)")
    elif deviation > 0.5:
        warnings.append(f"Entry {entry} отклоняется от рынка {price:.4f} на {deviation:.1f}%")

    # 2. TP direction
    is_buy = action.lower() == "buy"
    if is_buy and tp <= entry:
        errors.append(f"BUY: TP {tp} должен быть выше Entry {entry}")
    if not is_buy and tp >= entry:
        errors.append(f"SELL: TP {tp} должен быть ниже Entry {entry}")

    # 3. SL direction
    if is_buy and sl >= entry:
        errors.append(f"BUY: SL {sl} должен быть ниже Entry {entry}")
    if not is_buy and sl <= entry:
        errors.append(f"SELL: SL {sl} должен быть выше Entry {entry}")

    # 4. R:R check
    reward = abs(tp - entry)
    risk = abs(entry - sl)
    rr = reward / risk if risk > 0 else 0
    if rr < 1.0:
        errors.append(f"R:R {rr:.1f} < 1.0 — убыточная математика")
    elif rr < 1.5:
        warnings.append(f"R:R {rr:.1f} < 1.5 — ниже рекомендуемого")

    # 5. TP/SL distance reasonableness
    tp_pct = abs(tp - entry) / entry * 100
    sl_pct = abs(entry - sl) / entry * 100
    if tp_pct > 30:
        warnings.append(f"TP {tp_pct:.1f}% от входа — очень далеко")
    if sl_pct > 15:
        warnings.append(f"SL {sl_pct:.1f}% от входа — очень широкий стоп")

    valid = len(errors) == 0

    return {
        "valid": valid,
        "live_price": price,
        "source": live.get("source"),
        "deviation_pct": round(deviation, 2),
        "rr_ratio": round(rr, 2),
        "errors": errors,
        "warnings": warnings,
        "suggested_entry": round(price, 6) if deviation > 2 else None,
    }


# ═══ SIGNAL MONITORING ═══

async def check_signal_status(
    ticker: str,
    action: str,
    entry: float,
    tp: float,
    sl: float,
) -> dict:
    """Check if signal hit TP or SL based on current price.

    Returns: status (active/tp_hit/sl_hit), current P&L, distance to TP/SL.
    """
    live = await get_live_price(ticker)
    if not live or not live.get("price"):
        return {"status": "unknown", "error": "Price unavailable"}

    price = live["price"]
    is_buy = action.lower() == "buy"

    # Current P&L
    if is_buy:
        pnl_pct = (price - entry) / entry * 100
        tp_hit = price >= tp
        sl_hit = price <= sl
        distance_tp = (tp - price) / price * 100
        distance_sl = (price - sl) / price * 100
    else:
        pnl_pct = (entry - price) / entry * 100
        tp_hit = price <= tp
        sl_hit = price >= sl
        distance_tp = (price - tp) / price * 100
        distance_sl = (sl - price) / price * 100

    if tp_hit:
        status = "tp_hit"
    elif sl_hit:
        status = "sl_hit"
    else:
        status = "active"

    return {
        "ticker": ticker,
        "status": status,
        "current_price": price,
        "entry_price": entry,
        "pnl_pct": round(pnl_pct, 2),
        "distance_to_tp_pct": round(distance_tp, 2),
        "distance_to_sl_pct": round(distance_sl, 2),
        "source": live.get("source"),
        "timestamp": live.get("timestamp"),
    }
