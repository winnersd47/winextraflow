"""Real Backtesting Engine — simulates trades on actual OHLCV candles.

Unlike the original backtesting.py which only uses pre-calculated profit_pct,
this engine:
1. Fetches real historical candles from MOEX ISS or Binance API
2. For each signal, walks through candles bar-by-bar
3. Checks if price hit TP or SL first
4. Calculates actual P&L based on real market data

Data sources:
- MOEX ISS API (free, no auth) — RU stocks, daily candles
- Binance API (free, no auth) — crypto, 1h/4h/1d candles
"""

import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

import httpx

logger = logging.getLogger(__name__)


# ═══ CANDLE DATA PROVIDERS ═══

# MOEX FORTS contract codes: BR-9.26, GAZR-12.26, RTS-9.26, Si-3.27
_MOEX_FUTURES_RE = re.compile(r"^[A-Z]{2,4}-\d{1,2}\.\d{2}$")

# ISS addresses futures by SECID ("BRU6"), while channels and traders write the
# SHORTNAME ("BR-9.26"). Passing the shortname returns an empty candle set with a
# 200, which is why futures signals silently had no data at all.
_FORTS_SECIDS: dict[str, str] | None = None


async def _forts_secid(ticker: str) -> str | None:
    """Map a FORTS shortname to its SECID. Cached for the process lifetime."""
    global _FORTS_SECIDS
    t = ticker.upper()
    if _FORTS_SECIDS is None:
        _FORTS_SECIDS = {}
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    "https://iss.moex.com/iss/engines/futures/markets/forts/securities.json",
                    params={"iss.meta": "off", "securities.columns": "SECID,SHORTNAME"},
                )
                block = resp.json().get("securities", {})
                cols, rows = block.get("columns", []), block.get("data", [])
                for row in rows:
                    m = dict(zip(cols, row))
                    if m.get("SHORTNAME") and m.get("SECID"):
                        _FORTS_SECIDS[m["SHORTNAME"].upper()] = m["SECID"]
            logger.info(f"MOEX FORTS: {len(_FORTS_SECIDS)} contracts indexed")
        except Exception as e:
            logger.error(f"FORTS securities index failed: {e}")
    # Absent means the contract has expired — an expired contract has no live
    # candles, and a signal on it is no longer tradable.
    return _FORTS_SECIDS.get(t)


async def fetch_moex_candles(ticker: str, date_from: str, date_to: str,
                             market: str = "shares") -> list[dict]:
    """Fetch daily candles from MOEX ISS API. Free, no auth.

    market="forts" switches to the derivatives engine for FORTS futures
    (BR-9.26, GAZR-9.26, RTS-9.26) — they do not exist on the shares board.
    """
    if market == "forts":
        secid = await _forts_secid(ticker)
        if not secid:
            logger.info(f"MOEX FORTS: {ticker} not among live contracts (expired?)")
            return []
        url = ("https://iss.moex.com/iss/engines/futures/markets/forts/securities/"
               f"{secid}/candles.json")
    else:
        url = ("https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/"
               f"securities/{ticker}/candles.json")
    params = {
        "iss.meta": "off",
        "interval": 24,  # daily
        "from": date_from,
        "till": date_to,
        "candles.columns": "open,close,high,low,volume,begin",
        "limit": 500,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
            cols = data.get("candles", {}).get("columns", [])
            rows = data.get("candles", {}).get("data", [])
            candles = [dict(zip(cols, row)) for row in rows]
            logger.info(f"MOEX: {ticker} → {len(candles)} candles ({date_from} to {date_to})")
            return candles
    except Exception as e:
        logger.error(f"MOEX candle fetch error for {ticker}: {e}")
        return []


async def fetch_binance_candles(ticker: str, date_from: str, date_to: str, interval: str = "1d") -> list[dict]:
    """Fetch candles from Binance API. Free, no auth."""
    url = "https://api.binance.com/api/v3/klines"
    # Convert dates to timestamps
    start_ts = int(datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
    end_ts = int(datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)

    params = {
        # Binance symbols carry no separator: "ZIL/BTC" is rejected, and the error
        # body was then iterated as if it were candle rows, which is where
        # "could not convert string to float: 'o'" came from.
        "symbol": ticker.upper().replace("/", "").replace("-", "").replace("_", ""),
        "interval": interval,
        "startTime": start_ts,
        "endTime": end_ts,
        "limit": 1000,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params)
            raw = resp.json()
            # An error response is a dict ({"code": -1121, "msg": "Invalid symbol"}),
            # not a list of klines. Bail out instead of parsing its keys as prices.
            if not isinstance(raw, list):
                logger.info(f"Binance: {params['symbol']} rejected — {str(raw)[:120]}")
                return []
            candles = [
                {
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                    "begin": datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
                }
                for k in raw
            ]
            logger.info(f"Binance: {ticker} → {len(candles)} candles ({date_from} to {date_to})")
            return candles
    except Exception as e:
        logger.error(f"Binance candle fetch error for {ticker}: {e}")
        return []


# Bybit intervals are minute counts ("D" for daily), not Binance's "1d"/"1h" strings.
_BYBIT_INTERVAL = {"1m": "1", "5m": "5", "15m": "15", "30m": "30",
                   "1h": "60", "4h": "240", "1d": "D", "1w": "W"}


async def fetch_bybit_candles(ticker: str, date_from: str, date_to: str,
                              interval: str = "1d") -> list[dict]:
    """Fetch candles from Bybit v5. Free, no auth. Second crypto source.

    Bybit returns newest-first and each row is a list of strings
    [start, open, high, low, close, volume, turnover] — the opposite order to
    Binance and one element shorter, so the mapping cannot be shared.
    """
    symbol = ticker.upper().replace("/", "").replace("-", "").replace("_", "")
    start_ts = int(datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
    end_ts = int(datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.bybit.com/v5/market/kline",
                params={"category": "spot", "symbol": symbol,
                        "interval": _BYBIT_INTERVAL.get(interval, "D"),
                        "start": start_ts, "end": end_ts, "limit": 1000},
            )
            body = resp.json()
            if body.get("retCode") != 0:
                logger.info(f"Bybit: {symbol} rejected — {body.get('retMsg')}")
                return []
            rows = (body.get("result") or {}).get("list") or []
            candles = [
                {
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                    "begin": datetime.fromtimestamp(int(k[0]) / 1000, tz=timezone.utc)
                                     .strftime("%Y-%m-%d %H:%M"),
                }
                for k in rows
            ]
            candles.reverse()          # Bybit is newest-first; callers expect oldest-first
            logger.info(f"Bybit: {ticker} → {len(candles)} candles ({date_from} to {date_to})")
            return candles
    except Exception as e:
        logger.error(f"Bybit candle fetch error for {ticker}: {e}")
        return []


async def fetch_crypto_candles(ticker: str, date_from: str, date_to: str,
                               interval: str = "1d") -> list[dict]:
    """Crypto candles with a fallback between the two exchanges.

    Candles feed the ATR that sizes every stop, the charts and the backtests. With
    one source, an outage or a block there silently produced zero candles — and a
    signal with no ATR gets no volatility stop at all.
    """
    from app.services.live_price import CRYPTO_PRIMARY

    order = ([fetch_bybit_candles, fetch_binance_candles]
             if CRYPTO_PRIMARY == "bybit"
             else [fetch_binance_candles, fetch_bybit_candles])
    for fetch in order:
        got = await fetch(ticker, date_from, date_to, interval)
        if got:
            return got
    logger.warning(f"No crypto source returned candles for {ticker} "
                   f"(tried Binance and Bybit)")
    return []


# Major + minor + exotic forex pairs
# Single source: services/instruments.py. This module had the longest copy;
# the other two were short, which is how USDTRY became a US stock on a card.
from app.services.instruments import FOREX_CURRENCIES
# Top 50 US stocks by trading volume (2026)
US_STOCKS = {
    # Mega-cap tech
    "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOG", "GOOGL", "META", "NFLX", "AMD",
    # Semiconductors
    "INTC", "AVGO", "QCOM", "MU", "MRVL", "ARM", "SMCI",
    # Fintech / Payments
    "PYPL", "SQ", "COIN", "SOFI", "V", "MA", "GS", "JPM",
    # EV / Energy
    "RIVN", "LCID", "NIO", "F", "GM", "XOM", "CVX",
    # Cloud / SaaS
    "CRM", "SNOW", "PLTR", "NET", "DDOG", "ZS",
    # Social / Media
    "SNAP", "PINS", "RBLX", "SPOT", "DIS",
    # Healthcare / Biotech
    "JNJ", "PFE", "MRNA", "ABBV", "LLY",
    # Retail / Consumer
    "WMT", "COST", "TGT", "NKE", "SBUX",
    # Other popular
    "BA", "UBER", "ABNB", "AI", "IONQ",
}

# Top EU / Global stocks
EU_STOCKS = {
    "SAP", "ASML", "LVMH", "NVO", "SHEL", "AZN", "HSBA", "BP", "RIO", "GSK",
    "MC.PA", "OR.PA", "SIE.DE", "ALV.DE", "BAS.DE",  # Euronext / XETRA
    "NESN.SW", "ROG.SW", "NOVN.SW",  # Swiss
    "TSM", "BABA", "JD", "PDD",  # Asia ADRs
}


async def fetch_forex_candles(ticker: str, date_from: str, date_to: str) -> list[dict]:
    """Fetch forex/stock candles from Yahoo Finance (free, no key, no limits).

    Yahoo Finance symbols:
    - Forex: EURUSD=X, GBPUSD=X
    - US Stocks: AAPL, MSFT, NVDA
    """
    # Convert ticker to Yahoo Finance format
    if _is_forex_pair(ticker):
        yf_symbol = f"{ticker[:3]}{ticker[3:]}=X"
    else:
        yf_symbol = ticker

    # Yahoo Finance v8 API (public, no key)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_symbol}"
    params = {
        "period1": int(datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()),
        "period2": int(datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()),
        "interval": "1d",
    }
    try:
        async with httpx.AsyncClient(timeout=15, headers={"User-Agent": "Mozilla/5.0"}) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
            result = data.get("chart", {}).get("result", [{}])[0]
            timestamps = result.get("timestamp", [])
            quotes = result.get("indicators", {}).get("quote", [{}])[0]

            opens = quotes.get("open", [])
            highs = quotes.get("high", [])
            lows = quotes.get("low", [])
            closes = quotes.get("close", [])
            volumes = quotes.get("volume", [])

            candles = []
            for i, ts in enumerate(timestamps):
                if i >= len(opens) or opens[i] is None or closes[i] is None:
                    continue
                candles.append({
                    "open": float(opens[i]),
                    "high": float(highs[i]),
                    "low": float(lows[i]),
                    "close": float(closes[i]),
                    "volume": float(volumes[i] or 0),
                    "begin": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d"),
                })
            logger.info(f"Yahoo Finance: {yf_symbol} → {len(candles)} candles ({date_from} to {date_to})")
            return candles
    except Exception as e:
        logger.error(f"Yahoo Finance fetch error for {ticker}: {e}")
        return []


def _is_forex_pair(ticker: str) -> bool:
    """Check if ticker looks like a forex pair (6 chars, both halves are known currencies)."""
    t = ticker.upper()
    if len(t) != 6:
        return False
    base = t[:3]
    quote = t[3:]
    return base in FOREX_CURRENCIES and quote in FOREX_CURRENCIES


def detect_source(ticker: str) -> str:
    """Detect data source by ticker format.

    The MOEX list comes from services/instruments.py. This module held the
    longest of the four copies that existed, which is precisely why the
    others going stale was invisible from here.
    """
    from app.services.instruments import is_moex_equity
    t = ticker.upper()
    if is_moex_equity(t):
        return "moex"
    # MOEX FORTS futures (BR-9.26, GAZR-9.26, RTS-9.26, Si-12.26). Yahoo has no
    # such symbols, so without this they fell through to the "stocks" fallback and
    # silently produced no candles — no chart, no ATR, no TP/SL monitoring.
    if _MOEX_FUTURES_RE.match(t):
        return "moex_futures"
    if t.endswith("USDT") or t.endswith("BTC") or t.endswith("BUSD"):
        return "binance"
    if _is_forex_pair(t):
        return "forex"
    if t in US_STOCKS or t in EU_STOCKS:
        return "stocks"
    # A 4-5 letter ticker that is nothing else is far more likely to be a MOEX
    # name we have not listed (LSRG, RAGR came in this way) than a US one, since
    # the MOEX list is hand-maintained while US coverage comes from Yahoo. Try
    # MOEX first; fetch_candles falls back to Yahoo if MOEX returns nothing.
    if 4 <= len(t) <= 5 and t.isalpha() and t not in US_STOCKS:
        return "moex_or_stocks"
    # Fallback: try Yahoo Finance (covers almost everything)
    return "stocks"


async def fetch_candles(ticker: str, date_from: str, date_to: str) -> list[dict]:
    """Auto-detect source and fetch candles."""
    source = detect_source(ticker)
    if source == "moex":
        return await fetch_moex_candles(ticker, date_from, date_to)
    elif source == "moex_futures":
        return await fetch_moex_candles(ticker, date_from, date_to, market="forts")
    elif source == "moex_or_stocks":
        # Unlisted 4-5 letter ticker: MOEX first, Yahoo as the fallback.
        return (await fetch_moex_candles(ticker, date_from, date_to)
                or await fetch_forex_candles(ticker, date_from, date_to))
    elif source == "binance":
        return await fetch_crypto_candles(ticker, date_from, date_to)
    elif source in ("forex", "stocks"):
        return await fetch_forex_candles(ticker, date_from, date_to)
    else:
        # Try all sources
        for fetcher in [fetch_moex_candles, fetch_binance_candles, fetch_forex_candles]:
            candles = await fetcher(ticker, date_from, date_to)
            if candles:
                return candles
        return []


# ═══ TRADE SIMULATION ═══

@dataclass
class SimTrade:
    """Result of a single simulated trade on real candles."""
    ticker: str
    action: str  # buy / sell
    entry_price: float
    take_profit: float | None
    stop_loss: float | None
    exit_price: float
    exit_reason: str  # "tp_hit", "sl_hit", "expired", "last_candle"
    profit_pct: float
    bars_held: int
    entry_date: str
    exit_date: str
    signal_id: str = ""


def simulate_trade(
    action: str,
    entry_price: float,
    take_profit: float | None,
    stop_loss: float | None,
    candles: list[dict],
    max_bars: int = 30,
) -> SimTrade | None:
    """Walk through candles bar-by-bar and check if TP or SL hit."""
    if not candles or entry_price <= 0:
        return None

    is_buy = action.lower() == "buy"

    for i, candle in enumerate(candles[:max_bars]):
        high = candle.get("high", 0)
        low = candle.get("low", 0)
        close = candle.get("close", 0)
        date = candle.get("begin", "")

        if high == 0 or low == 0:
            continue

        # Check TP hit
        if take_profit:
            tp_hit = (is_buy and high >= take_profit) or (not is_buy and low <= take_profit)
            if tp_hit:
                if is_buy:
                    pct = ((take_profit - entry_price) / entry_price) * 100
                else:
                    pct = ((entry_price - take_profit) / entry_price) * 100
                return SimTrade(
                    ticker="", action=action, entry_price=entry_price,
                    take_profit=take_profit, stop_loss=stop_loss,
                    exit_price=take_profit, exit_reason="tp_hit",
                    profit_pct=round(pct, 2), bars_held=i + 1,
                    entry_date="", exit_date=str(date),
                )

        # Check SL hit
        if stop_loss:
            sl_hit = (is_buy and low <= stop_loss) or (not is_buy and high >= stop_loss)
            if sl_hit:
                if is_buy:
                    pct = ((stop_loss - entry_price) / entry_price) * 100
                else:
                    pct = ((entry_price - stop_loss) / entry_price) * 100
                return SimTrade(
                    ticker="", action=action, entry_price=entry_price,
                    take_profit=take_profit, stop_loss=stop_loss,
                    exit_price=stop_loss, exit_reason="sl_hit",
                    profit_pct=round(pct, 2), bars_held=i + 1,
                    entry_date="", exit_date=str(date),
                )

    # Neither TP nor SL hit — close at last candle
    last = candles[min(max_bars - 1, len(candles) - 1)]
    close = last.get("close", entry_price)
    if is_buy:
        pct = ((close - entry_price) / entry_price) * 100
    else:
        pct = ((entry_price - close) / entry_price) * 100

    return SimTrade(
        ticker="", action=action, entry_price=entry_price,
        take_profit=take_profit, stop_loss=stop_loss,
        exit_price=close, exit_reason="expired",
        profit_pct=round(pct, 2), bars_held=len(candles[:max_bars]),
        entry_date="", exit_date=str(last.get("begin", "")),
    )


# ═══ BACKTEST REPORT ═══

@dataclass
class RealBacktestResult:
    """Full backtest report with real candle data."""
    ticker: str
    source: str  # moex / binance
    date_from: str
    date_to: str
    candles_loaded: int
    total_signals: int
    simulated_trades: int

    # Performance
    total_return_pct: float = 0.0
    win_rate: float = 0.0
    avg_profit_pct: float = 0.0
    avg_loss_pct: float = 0.0
    best_trade_pct: float = 0.0
    worst_trade_pct: float = 0.0
    avg_bars_held: float = 0.0

    # Risk
    sharpe_ratio: float | None = None
    profit_factor: float | None = None
    max_drawdown_pct: float = 0.0

    # Exit breakdown
    tp_hits: int = 0
    sl_hits: int = 0
    expired: int = 0

    # Trades
    trades: list[dict] = field(default_factory=list)
    equity_curve: list[dict] = field(default_factory=list)


async def run_real_backtest(
    ticker: str,
    signals: list[dict],
    date_from: str | None = None,
    date_to: str | None = None,
    max_bars_per_trade: int = 30,
    initial_capital: float = 10000.0,
) -> RealBacktestResult:
    """Run backtest on real candles for a list of signals.

    Each signal dict should have: action, entry_price, take_profit, stop_loss, created_at, id
    """
    if not date_from:
        date_from = (datetime.now(timezone.utc) - timedelta(days=180)).strftime("%Y-%m-%d")
    if not date_to:
        date_to = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    source = detect_source(ticker)

    # Fetch candles
    candles = await fetch_candles(ticker, date_from, date_to)

    result = RealBacktestResult(
        ticker=ticker,
        source=source,
        date_from=date_from,
        date_to=date_to,
        candles_loaded=len(candles),
        total_signals=len(signals),
        simulated_trades=0,
    )

    if not candles or not signals:
        return result

    # Build date-indexed candle map for quick lookup
    candle_dates = [c.get("begin", "")[:10] for c in candles]

    trades: list[SimTrade] = []
    profits: list[float] = []
    total_profit = 0.0
    total_loss = 0.0

    for sig in signals:
        entry_price = sig.get("entry_price", 0)
        tp = sig.get("take_profit")
        sl = sig.get("stop_loss")
        action = sig.get("action", "buy")
        created = sig.get("created_at", "")
        sig_date = str(created)[:10] if created else ""

        if entry_price <= 0:
            continue

        # Find candle index after signal date
        start_idx = 0
        for idx, d in enumerate(candle_dates):
            if d >= sig_date:
                start_idx = idx
                break

        # Get candles after signal
        future_candles = candles[start_idx:]
        if not future_candles:
            continue

        # Simulate
        trade = simulate_trade(action, entry_price, tp, sl, future_candles, max_bars_per_trade)
        if not trade:
            continue

        trade.ticker = ticker
        trade.entry_date = sig_date
        trade.signal_id = sig.get("id", "")
        trades.append(trade)
        profits.append(trade.profit_pct)

        if trade.profit_pct >= 0:
            total_profit += trade.profit_pct
        else:
            total_loss += abs(trade.profit_pct)

        if trade.exit_reason == "tp_hit":
            result.tp_hits += 1
        elif trade.exit_reason == "sl_hit":
            result.sl_hits += 1
        else:
            result.expired += 1

    result.simulated_trades = len(trades)

    if not profits:
        return result

    # ── Metrics ──
    wins = sum(1 for p in profits if p >= 0)
    losses = len(profits) - wins
    result.win_rate = round(wins / len(profits), 3) if profits else 0
    result.total_return_pct = round(sum(profits), 2)
    result.avg_profit_pct = round(sum(p for p in profits if p >= 0) / max(wins, 1), 2)
    result.avg_loss_pct = round(sum(p for p in profits if p < 0) / max(losses, 1), 2)
    result.best_trade_pct = round(max(profits), 2)
    result.worst_trade_pct = round(min(profits), 2)
    result.avg_bars_held = round(sum(t.bars_held for t in trades) / len(trades), 1)

    # Profit factor
    if total_loss > 0:
        result.profit_factor = round(total_profit / total_loss, 2)

    # Sharpe ratio
    if len(profits) >= 2:
        avg = sum(profits) / len(profits)
        std = math.sqrt(sum((p - avg) ** 2 for p in profits) / (len(profits) - 1))
        if std > 0:
            result.sharpe_ratio = round((avg - 0.01) / std * math.sqrt(252), 2)

    # Max drawdown
    equity = initial_capital
    peak = equity
    max_dd = 0
    equity_curve = [{"trade": 0, "equity": round(equity, 2), "pct": 0}]

    for i, p in enumerate(profits):
        equity *= (1 + p / 100)
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100
        if dd > max_dd:
            max_dd = dd
        equity_curve.append({
            "trade": i + 1,
            "equity": round(equity, 2),
            "pct": round((equity / initial_capital - 1) * 100, 2),
        })

    result.max_drawdown_pct = round(max_dd, 2)
    result.equity_curve = equity_curve

    # Trade details
    result.trades = [
        {
            "ticker": t.ticker, "action": t.action,
            "entry": t.entry_price, "exit": t.exit_price,
            "tp": t.take_profit, "sl": t.stop_loss,
            "profit_pct": t.profit_pct, "exit_reason": t.exit_reason,
            "bars_held": t.bars_held,
            "entry_date": t.entry_date, "exit_date": t.exit_date,
            "signal_id": t.signal_id,
        }
        for t in trades
    ]

    return result


# ═══ EXTENDED ANALYTICS ═══

def compute_monthly_breakdown(trades: list[SimTrade]) -> list[dict]:
    """P&L breakdown by month."""
    months: dict[str, dict] = {}
    for t in trades:
        month_key = t.exit_date[:7] if t.exit_date and len(t.exit_date) >= 7 else "unknown"
        if month_key not in months:
            months[month_key] = {"month": month_key, "trades": 0, "wins": 0, "pnl_pct": 0.0}
        months[month_key]["trades"] += 1
        months[month_key]["pnl_pct"] += t.profit_pct
        if t.profit_pct >= 0:
            months[month_key]["wins"] += 1

    result = []
    for m in sorted(months.values(), key=lambda x: x["month"]):
        m["pnl_pct"] = round(m["pnl_pct"], 2)
        m["win_rate"] = round(m["wins"] / m["trades"], 2) if m["trades"] > 0 else 0
        result.append(m)
    return result


def compute_buy_and_hold(candles: list[dict]) -> dict:
    """Buy & Hold benchmark: what if you just bought at first candle and held."""
    if not candles or len(candles) < 2:
        return {"return_pct": 0, "start_price": 0, "end_price": 0}
    start = candles[0].get("open", 0) or candles[0].get("close", 0)
    end = candles[-1].get("close", 0)
    if start <= 0:
        return {"return_pct": 0, "start_price": start, "end_price": end}
    return {
        "return_pct": round(((end - start) / start) * 100, 2),
        "start_price": round(start, 4),
        "end_price": round(end, 4),
        "days": len(candles),
    }


def run_monte_carlo(profits: list[float], n_simulations: int = 1000, initial_capital: float = 10000.0) -> dict:
    """Monte Carlo simulation — shuffle trade order 1000 times.

    Shows range of possible outcomes if trades happened in different order.
    Strategy is robust if results are consistent across shuffles.
    """
    import random

    if len(profits) < 3:
        return {"error": "Need at least 3 trades for Monte Carlo"}

    final_equities = []
    max_drawdowns = []

    for _ in range(n_simulations):
        shuffled = profits.copy()
        random.shuffle(shuffled)

        equity = initial_capital
        peak = equity
        max_dd = 0

        for p in shuffled:
            equity *= (1 + p / 100)
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        final_equities.append(equity)
        max_drawdowns.append(max_dd)

    final_equities.sort()
    max_drawdowns.sort()

    return {
        "simulations": n_simulations,
        "trades_per_sim": len(profits),
        "equity": {
            "median": round(final_equities[n_simulations // 2], 2),
            "p5": round(final_equities[int(n_simulations * 0.05)], 2),
            "p25": round(final_equities[int(n_simulations * 0.25)], 2),
            "p75": round(final_equities[int(n_simulations * 0.75)], 2),
            "p95": round(final_equities[int(n_simulations * 0.95)], 2),
            "worst": round(final_equities[0], 2),
            "best": round(final_equities[-1], 2),
        },
        "drawdown": {
            "median": round(max_drawdowns[n_simulations // 2], 2),
            "p95_worst": round(max_drawdowns[int(n_simulations * 0.95)], 2),
            "max": round(max_drawdowns[-1], 2),
        },
        "risk_of_ruin_pct": round(sum(1 for e in final_equities if e < initial_capital * 0.5) / n_simulations * 100, 1),
        "profitable_pct": round(sum(1 for e in final_equities if e > initial_capital) / n_simulations * 100, 1),
    }


def apply_commission(profits: list[float], commission_pct: float) -> list[float]:
    """Subtract commission from each trade (entry + exit)."""
    return [round(p - commission_pct * 2, 2) for p in profits]


def apply_position_sizing(profits: list[float], position_pct: float) -> list[float]:
    """Scale profits by position size (% of capital per trade)."""
    scale = position_pct / 100.0
    return [round(p * scale, 2) for p in profits]
