"""Quant Intelligence API — market regime, strategy classification, meta agent.

Implements the Autonomous Market Intelligence Architecture:
  GET  /quant/regime           — current market regime detection
  GET  /quant/regime/{ticker}  — regime for specific ticker
  POST /quant/evaluate/{signal_id} — full Meta Agent signal evaluation
  GET  /quant/strategies       — list strategy IDs with metadata
  GET  /quant/dashboard        — full intelligence dashboard
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.signal import Signal
from app.models.provider import Provider
from app.models.user import User
from app.services.quant.regime import regime_detector
from app.services.quant.strategy_classifier import strategy_classifier, StrategyID, STRATEGY_META
from app.services.quant.meta_agent import meta_agent

router = APIRouter()


@router.get("/regime")
async def get_market_regime(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Detect current overall market regime from platform signal data."""
    state = await regime_detector.detect(db)
    return {
        "regime": state.regime.value,
        "confidence": state.confidence,
        "buy_ratio": state.buy_ratio,
        "tp_hit_rate": state.tp_hit_rate,
        "sl_hit_rate": state.sl_hit_rate,
        "avg_profit_pct": state.avg_profit_pct,
        "volatility_proxy": state.volatility_proxy,
        "signal_frequency": state.signal_frequency,
        "dominant_tickers": state.dominant_tickers,
        "timestamp": state.timestamp,
    }


@router.get("/regime/{ticker}")
async def get_ticker_regime(
    ticker: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Detect market regime for a specific ticker."""
    state = await regime_detector.detect(db, ticker=ticker.upper())
    return {
        "ticker": ticker.upper(),
        "regime": state.regime.value,
        "confidence": state.confidence,
        "buy_ratio": state.buy_ratio,
        "tp_hit_rate": state.tp_hit_rate,
        "sl_hit_rate": state.sl_hit_rate,
        "avg_profit_pct": state.avg_profit_pct,
        "volatility_proxy": state.volatility_proxy,
        "signal_frequency": state.signal_frequency,
        "timestamp": state.timestamp,
    }


@router.post("/evaluate/{signal_id}")
async def evaluate_signal(
    signal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Full Meta Agent evaluation of a signal.

    Returns: strategy classification, regime compatibility,
    meta score with dynamic weights, and recommendation.
    """
    signal = (await db.execute(
        select(Signal).where(Signal.id == signal_id)
    )).scalar_one_or_none()
    if not signal:
        raise HTTPException(404, "Signal not found")

    provider = None
    if signal.provider_id:
        provider = await db.get(Provider, signal.provider_id)

    decision = await meta_agent.evaluate(db, signal, provider)

    return {
        "signal_id": decision.signal_id,
        "ticker": decision.ticker,
        "regime": decision.regime,
        "regime_confidence": decision.regime_confidence,
        "strategy": {
            "id": decision.strategy_id,
            "name": decision.strategy_name,
            "name_ru": decision.strategy_name_ru,
            "confidence": decision.strategy_confidence,
            "regime_compatible": decision.regime_compatible,
        },
        "meta_score": decision.meta_score,
        "recommendation": decision.recommendation,
        "recommendation_ru": decision.recommendation_ru,
        "factors": decision.factors,
        "weights": decision.weights,
        "reasoning": decision.reasoning,
    }


@router.get("/strategies")
async def list_strategies(user: User = Depends(get_current_user)):
    """List all 7 Strategy IDs with metadata."""
    return {
        "strategies": [
            {
                "id": sid.value,
                "name": meta["name"],
                "name_ru": meta["name_ru"],
                "description": meta["description"],
                "description_ru": meta["description_ru"],
                "best_regimes": [r.value for r in meta["best_regime"]],
                "risk": meta["risk"],
            }
            for sid, meta in STRATEGY_META.items()
        ],
    }


@router.get("/dashboard")
async def intelligence_dashboard(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Full intelligence dashboard — regime + recent signal evaluations."""
    # Overall regime
    overall = await regime_detector.detect(db)

    # Top ticker regimes
    top_tickers = overall.dominant_tickers[:5]
    ticker_regimes = {}
    for t in top_tickers:
        state = await regime_detector.detect(db, ticker=t)
        ticker_regimes[t] = {"regime": state.regime.value, "confidence": state.confidence}

    # Evaluate latest 5 active signals
    recent = (await db.execute(
        select(Signal).order_by(Signal.created_at.desc()).limit(5)
    )).scalars().all()

    evaluations = []
    for sig in recent:
        provider = await db.get(Provider, sig.provider_id) if sig.provider_id else None
        d = await meta_agent.evaluate(db, sig, provider)
        evaluations.append({
            "signal_id": d.signal_id,
            "ticker": d.ticker,
            "strategy_name": d.strategy_name,
            "strategy_name_ru": d.strategy_name_ru,
            "meta_score": d.meta_score,
            "recommendation": d.recommendation,
            "recommendation_ru": d.recommendation_ru,
            "regime": d.regime,
            "regime_compatible": d.regime_compatible,
        })

    return {
        "market": {
            "regime": overall.regime.value,
            "confidence": overall.confidence,
            "volatility": overall.volatility_proxy,
            "signal_frequency": overall.signal_frequency,
        },
        "ticker_regimes": ticker_regimes,
        "evaluations": evaluations,
        "architecture_level": 2,
        "architecture_levels": {
            1: "Regime Detection + Strategy Mapping + Execution",
            2: "Adaptive Scoring + AI Validation + Dynamic Weighting (CURRENT)",
            3: "Multi-Agent Decision + Reinforcement Learning (PLANNED)",
            4: "Evolutionary Ecosystem + Digital Twin (PLANNED)",
        },
    }


@router.get("/evolution")
async def evolution_state(user: User = Depends(get_current_user)):
    """Full evolutionary state of the architecture — branches, components, roadmap."""
    from app.services.quant.evolution import evolutionary_registry
    return evolutionary_registry.get_state()


@router.get("/articles")
async def processed_articles(user: User = Depends(get_current_user)):
    """List all MQL5 articles processed by the evolutionary protocol."""
    from app.services.quant.article_log import article_log
    return {
        "articles": article_log.get_all(),
        "stats": article_log.get_stats(),
    }
