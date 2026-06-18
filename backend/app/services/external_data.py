"""External Data Sources — free APIs, no keys required.

Aggregates data from 10+ free sources for platform analytics:
1. Fear & Greed Index (crypto sentiment)
2. Bitcoin on-chain metrics
3. Economic calendar (NFP, CPI, GDP, rates)
4. Central bank rates (Fed, ECB, BoE, CBR)
5. Currency rates (RUB/USD/EUR)
6. Gas fees (Ethereum)
7. DeFi TVL
8. Crypto dominance
9. Gold/Oil prices
10. Global market indices
"""

import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)


async def _get(url: str, headers: dict | None = None, timeout: int = 8) -> dict | list | None:
    """Safe GET request with error handling."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers=headers or {"User-Agent": "WinExtraFlow/1.0"})
            if resp.status_code < 400:
                return resp.json()
    except Exception as e:
        logger.warning(f"External data fetch failed: {url[:60]}... → {e}")
    return None


# ═══ 1. FEAR & GREED INDEX ═══

async def get_fear_greed_index() -> dict:
    """Crypto Fear & Greed Index from Alternative.me (free, no key).
    0 = Extreme Fear, 100 = Extreme Greed.
    """
    data = await _get("https://api.alternative.me/fng/?limit=7&format=json")
    if not data or "data" not in data:
        return {"error": "unavailable"}

    entries = data["data"]
    current = entries[0] if entries else {}
    history = [{"value": int(e["value"]), "label": e["value_classification"], "date": e["timestamp"]} for e in entries]

    return {
        "value": int(current.get("value", 0)),
        "label": current.get("value_classification", "Unknown"),
        "timestamp": current.get("timestamp", ""),
        "history_7d": history,
    }


# ═══ 2. BITCOIN ON-CHAIN ═══

async def get_btc_metrics() -> dict:
    """Bitcoin key metrics from CoinGecko (free, no key, 30 req/min)."""
    data = await _get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd,rub,eur&include_24hr_change=true&include_24hr_vol=true&include_market_cap=true")
    if not data or "bitcoin" not in data:
        return {"error": "unavailable"}

    btc = data["bitcoin"]
    return {
        "price_usd": btc.get("usd"),
        "price_rub": btc.get("rub"),
        "price_eur": btc.get("eur"),
        "change_24h_pct": round(btc.get("usd_24h_change", 0), 2),
        "volume_24h_usd": btc.get("usd_24h_vol"),
        "market_cap_usd": btc.get("usd_market_cap"),
    }


# ═══ 3. TOP CRYPTO PRICES ═══

async def get_top_crypto(limit: int = 20) -> list[dict]:
    """Top cryptocurrencies from CoinGecko (free, no key)."""
    data = await _get(f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page={limit}&page=1&sparkline=true&price_change_percentage=1h,24h,7d")
    if not data:
        return []

    return [
        {
            "symbol": c.get("symbol", "").upper(),
            "name": c.get("name"),
            "price": c.get("current_price"),
            "change_1h": c.get("price_change_percentage_1h_in_currency"),
            "change_24h": c.get("price_change_percentage_24h"),
            "change_7d": c.get("price_change_percentage_7d_in_currency"),
            "market_cap": c.get("market_cap"),
            "volume_24h": c.get("total_volume"),
            "sparkline_7d": c.get("sparkline_in_7d", {}).get("price", [])[-24:],  # last 24 points
        }
        for c in data
    ]


# ═══ 4. CURRENCY RATES ═══

async def get_currency_rates() -> dict:
    """USD/RUB, EUR/RUB, CNY/RUB from CBR or exchangerate.host (free)."""
    data = await _get("https://api.exchangerate.host/latest?base=USD&symbols=RUB,EUR,GBP,CNY,TRY")
    if not data or not data.get("success"):
        # Fallback: CBR daily rates
        cbr = await _get("https://www.cbr-xml-daily.ru/daily_json.js")
        if cbr and "Valute" in cbr:
            v = cbr["Valute"]
            return {
                "USD_RUB": v.get("USD", {}).get("Value"),
                "EUR_RUB": v.get("EUR", {}).get("Value"),
                "GBP_RUB": v.get("GBP", {}).get("Value"),
                "CNY_RUB": v.get("CNY", {}).get("Value"),
                "source": "CBR",
            }
        return {"error": "unavailable"}

    rates = data.get("rates", {})
    return {
        "USD_RUB": rates.get("RUB"),
        "EUR_USD": 1 / rates.get("EUR", 1) if rates.get("EUR") else None,
        "GBP_USD": 1 / rates.get("GBP", 1) if rates.get("GBP") else None,
        "CNY_USD": 1 / rates.get("CNY", 1) if rates.get("CNY") else None,
        "source": "exchangerate.host",
    }


# ═══ 5. GLOBAL INDICES ═══

async def get_global_indices() -> list[dict]:
    """Major global stock indices from Yahoo Finance (free)."""
    symbols = ["^GSPC", "^DJI", "^IXIC", "^FTSE", "^GDAXI", "^N225", "^HSI"]
    names = {"^GSPC": "S&P 500", "^DJI": "Dow Jones", "^IXIC": "NASDAQ", "^FTSE": "FTSE 100", "^GDAXI": "DAX", "^N225": "Nikkei 225", "^HSI": "Hang Seng"}

    results = []
    for sym in symbols:
        data = await _get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=2d",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if not data:
            continue
        try:
            result = data["chart"]["result"][0]
            meta = result.get("meta", {})
            price = meta.get("regularMarketPrice", 0)
            prev = meta.get("previousClose") or meta.get("chartPreviousClose", 0)
            change = ((price - prev) / prev * 100) if prev else 0
            results.append({
                "symbol": sym,
                "name": names.get(sym, sym),
                "price": round(price, 2),
                "change_pct": round(change, 2),
            })
        except (KeyError, IndexError):
            continue

    return results


# ═══ 6. COMMODITIES (Gold, Oil, Gas) ═══

async def get_commodities() -> list[dict]:
    """Gold, Oil, Natural Gas from Yahoo Finance (free)."""
    symbols = {"GC=F": "Gold", "CL=F": "Crude Oil WTI", "NG=F": "Natural Gas", "SI=F": "Silver"}
    results = []

    for sym, name in symbols.items():
        data = await _get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=2d",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if not data:
            continue
        try:
            meta = data["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice", 0)
            prev = meta.get("previousClose") or meta.get("chartPreviousClose", 0)
            change = ((price - prev) / prev * 100) if prev else 0
            results.append({"symbol": sym, "name": name, "price": round(price, 2), "change_pct": round(change, 2)})
        except (KeyError, IndexError):
            continue

    return results


# ═══ 7. CRYPTO DOMINANCE ═══

async def get_crypto_dominance() -> dict:
    """BTC/ETH dominance from CoinGecko (free)."""
    data = await _get("https://api.coingecko.com/api/v3/global")
    if not data or "data" not in data:
        return {"error": "unavailable"}

    d = data["data"]
    dom = d.get("market_cap_percentage", {})
    return {
        "btc_dominance": round(dom.get("btc", 0), 1),
        "eth_dominance": round(dom.get("eth", 0), 1),
        "total_market_cap_usd": d.get("total_market_cap", {}).get("usd"),
        "total_volume_24h_usd": d.get("total_volume", {}).get("usd"),
        "active_cryptocurrencies": d.get("active_cryptocurrencies"),
    }


# ═══ 8. DEFI TVL ═══

async def get_defi_tvl() -> dict:
    """DeFi Total Value Locked from DeFi Llama (free, no key)."""
    data = await _get("https://api.llama.fi/v2/historicalChainTvl")
    if not data or not isinstance(data, list):
        return {"error": "unavailable"}

    # Last entry = current TVL
    latest = data[-1] if data else {}
    prev_week = data[-8] if len(data) > 7 else {}
    current_tvl = latest.get("tvl", 0)
    week_ago_tvl = prev_week.get("tvl", 0)
    change_7d = ((current_tvl - week_ago_tvl) / week_ago_tvl * 100) if week_ago_tvl else 0

    return {
        "total_tvl_usd": round(current_tvl),
        "change_7d_pct": round(change_7d, 1),
        "date": latest.get("date", ""),
    }


# ═══ 9. GAS FEES (Ethereum) ═══

async def get_eth_gas() -> dict:
    """Ethereum gas fees from ethgasstation or beaconcha.in (free)."""
    data = await _get("https://api.etherscan.io/api?module=gastracker&action=gasoracle")
    if data and data.get("status") == "1":
        result = data.get("result", {})
        return {
            "fast_gwei": int(result.get("FastGasPrice", 0)),
            "standard_gwei": int(result.get("ProposeGasPrice", 0)),
            "slow_gwei": int(result.get("SafeGasPrice", 0)),
        }
    return {"error": "unavailable"}


# ═══ AGGREGATE: All data in one call ═══

async def get_market_pulse() -> dict:
    """Full market pulse — all external data in one response."""
    import asyncio

    results = await asyncio.gather(
        get_fear_greed_index(),
        get_btc_metrics(),
        get_currency_rates(),
        get_crypto_dominance(),
        get_commodities(),
        get_global_indices(),
        get_defi_tvl(),
        return_exceptions=True,
    )

    def safe(r):
        return r if not isinstance(r, Exception) else {"error": str(r)}

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fear_greed": safe(results[0]),
        "bitcoin": safe(results[1]),
        "currency_rates": safe(results[2]),
        "crypto_dominance": safe(results[3]),
        "commodities": safe(results[4]),
        "global_indices": safe(results[5]),
        "defi_tvl": safe(results[6]),
    }
