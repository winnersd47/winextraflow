"""Public endpoints — no auth required (landing page stats, sample signal, data source status)."""

from fastapi import APIRouter
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from fastapi import Depends

router = APIRouter()


@router.get("/stats")
async def get_public_stats(db: AsyncSession = Depends(get_db)):
    """Live platform stats for the landing page.

    Counts real rows only. Previously this returned every row in the table, so the
    landing page advertised 1436 signals when 120 came from a real source, and 34
    providers when 14 were real. `strategies` also had two hardcoded constants
    (mt5_count=50, tv_count=16) added to the real count, and `telegram_messages`
    was the literal 10044 presented as a live figure.

    A number here is either counted from the database or it is not shown.
    """
    from app.models.provider import Provider
    from app.models.signal import Signal
    from app.models.strategy import Strategy
    from app.models.user import User
    from app.services.signal_quality import SEED_MARKERS, TEST_TICKERS

    not_seed = and_(
        Signal.ticker.notin_(TEST_TICKERS),
        or_(Signal.raw_message.is_(None),
            and_(*[Signal.raw_message.notlike(f"{m}%") for m in SEED_MARKERS])),
    )
    signals_count = (await db.execute(
        select(func.count(Signal.id)).where(not_seed))).scalar() or 0
    providers_count = (await db.execute(select(func.count(Provider.id)).where(
        Provider.is_seed.is_(False)))).scalar() or 0
    users_count = (await db.execute(select(func.count(User.id)))).scalar() or 0
    strategies_count = (await db.execute(
        select(func.count(Strategy.id)).where(Strategy.is_published.is_(True)))).scalar() or 0

    # Evolutionary components — a real registry, counted at runtime.
    try:
        from app.services.quant.evolution import evolutionary_registry
        evo_components = len(evolutionary_registry.components)
    except Exception:
        evo_components = 0

    # Markets the platform actually fetches candles for (see backtesting_real).
    markets = 5   # MOEX shares, MOEX FORTS, US/EU stocks, Binance, forex

    return {
        "signals": signals_count,
        "providers": providers_count,
        "users": users_count,
        "strategies": strategies_count,
        "markets": markets,
        "exchanges": markets,      # kept for the existing landing-page field
        "evo_components": evo_components,
    }


@router.get("/sample-signal")
async def get_sample_signal(db: AsyncSession = Depends(get_db)):
    """Best recent signal for landing page demo."""
    from app.models.signal import Signal

    # Get highest-rated signal
    stmt = (
        select(Signal)
        .where(Signal.ai_confidence.isnot(None))
        .order_by(Signal.ai_confidence.desc())
        .limit(1)
    )
    signal = (await db.execute(stmt)).scalar_one_or_none()

    if not signal:
        # Fallback demo signal
        return {
            "ticker": "SBER",
            "action": "BUY",
            "entry_price": 312.50,
            "take_profit": 340.00,
            "stop_loss": 298.00,
            "ai_confidence": 0.87,
            "ai_reasoning": "Strong uptrend, favorable risk/reward 1:1.9, provider win rate 72%",
            "provider_name": "Alpha Signals",
        }

    # Get provider name
    provider_name = "Unknown"
    if signal.provider_id:
        from app.models.provider import Provider
        provider = (await db.execute(select(Provider).where(Provider.id == signal.provider_id))).scalar_one_or_none()
        if provider:
            provider_name = provider.name.replace("[TEST] ", "")

    return {
        "ticker": signal.ticker,
        "action": signal.action.value if hasattr(signal.action, "value") else str(signal.action),
        "entry_price": signal.entry_price,
        "take_profit": signal.take_profit,
        "stop_loss": signal.stop_loss,
        "ai_confidence": signal.ai_confidence,
        "ai_reasoning": signal.ai_reasoning or "",
        "provider_name": provider_name,
    }


@router.get("/market-pulse")
async def market_pulse():
    """Full market pulse — aggregated data from 7 free external APIs.

    No auth required. Data includes:
    - Fear & Greed Index (crypto sentiment)
    - Bitcoin price/volume/market cap
    - Currency rates (USD/RUB, EUR/USD)
    - Crypto dominance (BTC%, ETH%)
    - Commodities (Gold, Oil, Gas)
    - Global indices (S&P 500, Dow, NASDAQ, DAX, Nikkei)
    - DeFi TVL
    """
    from app.services.external_data import get_market_pulse
    return await get_market_pulse()


@router.get("/fear-greed")
async def fear_greed():
    """Crypto Fear & Greed Index (0-100). No auth."""
    from app.services.external_data import get_fear_greed_index
    return await get_fear_greed_index()


@router.get("/crypto-top")
async def crypto_top(limit: int = 20):
    """Top cryptocurrencies by market cap. No auth."""
    from app.services.external_data import get_top_crypto
    return {"coins": await get_top_crypto(limit)}


@router.get("/data-status")
async def data_source_status():
    """Simplified data source status (public, no auth).

    Returns only status per source — no sensitive details.
    Used by frontend to show warning banners.
    """
    from app.services.health_monitor import health_monitor
    report = await health_monitor.check_all()
    return {
        "overall": report["overall"],
        "sources": {
            key: {"name": s["name"], "status": s["status"], "latency_ms": s["latency_ms"]}
            for key, s in report["sources"].items()
        },
    }


@router.get("/ticker-tape")
async def ticker_tape():
    """Live prices for the dashboard ticker tape.

    Replaces the TradingView ticker-tape widget. Their free widget requires the
    attribution badge to stay visible, and that badge overlapped the prices; hiding
    it with CSS would breach their terms. The platform already fetches these prices
    itself (MOEX ISS, Binance, Yahoo), so the dependency was unnecessary — and the
    external script is one more thing that loads slowly or not at all on RU networks.
    """
    from app.services.live_price import get_live_price

    WATCH = [
        ("SBER", "Сбер", "₽"), ("GAZP", "Газпром", "₽"), ("LKOH", "Лукойл", "₽"),
        ("BTCUSDT", "Bitcoin", "$"), ("ETHUSDT", "Ethereum", "$"),
        ("SOLUSDT", "Solana", "$"),
        ("AAPL", "Apple", "$"), ("NVDA", "NVIDIA", "$"), ("TSLA", "Tesla", "$"),
    ]

    items = []
    for ticker, title, cur in WATCH:
        p = await get_live_price(ticker)
        if not p or not p.get("price"):
            continue                      # a missing quote is skipped, not faked
        change = p.get("change_pct")
        # Three different metrics, so three different labels rather than one that
        # would be wrong for two of them:
        #   Binance change_pct — rolling 24 hours
        #   Yahoo  change_pct — versus the previous daily close
        #   MOEX   no change field at all — derived from the session open
        src = (p.get("source") or "").lower()
        window = "prev_close" if "yahoo" in src else "24h"
        if change is None and p.get("open"):
            change = (p["price"] - p["open"]) / p["open"] * 100
            window = "session"
        items.append({
            "ticker": ticker, "title": title, "currency": cur,
            "price": round(p["price"], 2),
            "change_pct": round(change, 2) if change is not None else None,
            "change_window": window if change is not None else None,
            "source": p.get("source"),
        })
    return {"items": items, "count": len(items)}


@router.get("/heatmap")
async def heatmap(market: str = "moex"):
    """Heatmap data for one market, in a single shape for all three.

    Replaces the TradingView heatmap widget, whose terms require a visible
    attribution link. Every figure here comes from a source the platform already
    uses: MOEX ISS, CoinGecko, Yahoo. A ticker whose quote fails is omitted rather
    than rendered as a flat zero, which would read as "unchanged".
    """
    import asyncio

    from app.services.live_price import get_live_price

    market = (market or "moex").lower()
    out: list[dict] = []

    if market == "crypto":
        from app.services.external_data import get_top_crypto
        for c in await get_top_crypto(24):
            if c.get("price") is None or c.get("change_24h") is None:
                continue
            out.append({
                "ticker": c["symbol"], "name": c.get("name") or c["symbol"],
                "price": round(c["price"], 4),
                "change_pct": round(c["change_24h"], 2),
                "volume": c.get("market_cap") or 0,
                "sector": "Crypto",
            })

    elif market == "us":
        # A slice of the screener's US list — enough to read as a map without
        # making two dozen sequential Yahoo calls.
        GROUPS = {
            "Tech": ["AAPL", "MSFT", "NVDA", "GOOG", "META"],
            "Semis": ["AMD", "INTC", "AVGO", "QCOM"],
            "Finance": ["JPM", "GS", "V"],
            "Energy": ["XOM", "CVX"],
            "Consumer": ["TSLA", "AMZN", "WMT", "NKE"],
        }
        pairs = [(t, sector) for sector, ts in GROUPS.items() for t in ts]
        quotes = await asyncio.gather(*(get_live_price(t) for t, _ in pairs),
                                     return_exceptions=True)
        for (ticker, sector), q in zip(pairs, quotes):
            if isinstance(q, Exception) or not q or not q.get("price"):
                continue
            ch = q.get("change_pct")
            if ch is None and q.get("open"):
                ch = (q["price"] - q["open"]) / q["open"] * 100
            if ch is None:
                continue
            out.append({"ticker": ticker, "name": ticker,
                        "price": round(q["price"], 2),
                        "change_pct": round(ch, 2),
                        "volume": q.get("volume") or 0, "sector": sector})

    else:
        # MOEX keeps its own endpoint (it has sector mapping and full coverage);
        # proxied here so the frontend has one URL shape for every market.
        from app.api.moex import MOEX_SECTORS
        from app.services.moex import moex_service
        try:
            quotes = await moex_service.get_live_quotes()
        except Exception:
            quotes = []
        for q in quotes or []:
            ticker = q.get("ticker", "")
            if not ticker or q.get("change_pct") is None:
                continue
            out.append({
                "ticker": ticker, "name": q.get("name") or ticker,
                "price": round(q.get("price") or 0, 2),
                "change_pct": round(q["change_pct"], 2),
                "volume": q.get("volume") or 0,
                "sector": MOEX_SECTORS.get(ticker, "Other"),
            })

    out.sort(key=lambda x: (x["sector"], -(x["volume"] or 0)))
    return {"market": market, "tickers": out, "total": len(out)}


@router.get("/econ-calendar")
async def econ_calendar(days_ahead: int = 60):
    """Economic calendar from primary sources (CBR, MOEX ISS, FRED).

    Replaces the TradingView calendar widget. Aggregators were rejected: paid or
    key-gated with attribution terms, or scraping investing.com against its terms.
    """
    from app.services.econ_calendar import get_calendar
    return await get_calendar(days_ahead)


@router.get("/geometry-baseline")
async def geometry_baseline(ticker: str, action: str = "buy",
                            tp_mult: float = 4.0, sl_mult: float = 2.0):
    """Random-entry baseline for a signal's own risk/reward geometry.

    A single signal cannot be backtested — one trade is not a strategy. What is
    testable is the geometry: at this instrument's volatility, how often did price
    travel tp_mult x ATR in the given direction before sl_mult x ATR against it?

    The walk enters on EVERY historical bar, so this is the random-entry baseline —
    the number a signal has to beat to be worth anything. Measured on the four
    instruments checked so far it sits close to the breakeven rate, which is the
    useful part: it is not a free lunch, and the entry rule has to earn its keep.

    Explicitly NOT the probability that this signal wins: that would require the
    entry condition, which is not tested here.
    """
    from app.services.signal_geometry import breakeven_hit_rate, geometry_hit_rate_cached

    r = await geometry_hit_rate_cached(ticker, action, tp_mult, sl_mult)
    be = breakeven_hit_rate(tp_mult, sl_mult)
    edge = None
    if r["hit_rate_pct"] is not None:
        edge = round(r["hit_rate_pct"] - be, 1)
    return {
        **r,
        "breakeven_pct": be,
        "vs_breakeven_pp": edge,
        "measures": "достижимость цели при волатильности инструмента, "
                    "вход на каждом баре (случайный вход)",
        "does_not_measure": "вероятность успеха конкретного сигнала — "
                            "для этого нужно правило входа, оно здесь не проверяется",
    }
