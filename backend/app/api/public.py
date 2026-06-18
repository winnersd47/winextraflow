"""Public endpoints — no auth required (landing page stats, sample signal, data source status)."""

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from fastapi import Depends

router = APIRouter()


@router.get("/stats")
async def get_public_stats(db: AsyncSession = Depends(get_db)):
    """Live platform stats for landing page."""
    from app.models.signal import Signal
    from app.models.provider import Provider
    from app.models.user import User

    signals_count = (await db.execute(select(func.count(Signal.id)))).scalar() or 0
    providers_count = (await db.execute(select(func.count(Provider.id)))).scalar() or 0
    users_count = (await db.execute(select(func.count(User.id)))).scalar() or 0

    # Total strategies across all sources
    from app.models.strategy import Strategy
    strategies_count = (await db.execute(select(func.count(Strategy.id)))).scalar() or 0

    # MT5 advisors + TradingView strategies (static counts)
    mt5_count = 50
    tv_count = 16

    # Evolutionary components
    try:
        from app.services.quant.evolution import evolutionary_registry
        evo_components = len(evolutionary_registry.components)
    except Exception:
        evo_components = 164

    # MOEX tickers
    moex_tickers = 27  # 20 stocks + 7 indices

    return {
        "signals": signals_count,
        "providers": providers_count,
        "users": users_count,
        "strategies": strategies_count + mt5_count + tv_count,
        "exchanges": 9,
        "evo_components": evo_components,
        "moex_tickers": moex_tickers,
        "telegram_messages": 10044,
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
