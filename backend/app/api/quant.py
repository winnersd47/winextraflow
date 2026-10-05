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
from sqlalchemy import func, select
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

    # All meaningful ticker regimes (min 3 signals each)
    from sqlalchemy import distinct
    all_tickers_result = await db.execute(
        select(Signal.ticker, func.count().label("cnt"))
        .group_by(Signal.ticker)
        .having(func.count() >= 3)
        .order_by(func.count().desc())
    )
    all_tickers = [row[0] for row in all_tickers_result.all()]

    ticker_regimes = {}
    for t in all_tickers:
        state = await regime_detector.detect(db, ticker=t)
        if state.regime.value != "unknown":
            ticker_regimes[t] = {
                "regime": state.regime.value,
                "confidence": state.confidence,
                "signals": state.buy_ratio,
            }

    # Evaluate latest 10 signals
    recent = (await db.execute(
        select(Signal).order_by(Signal.created_at.desc()).limit(10)
    )).scalars().all()

    async def _eval(sig: Signal) -> dict:
        provider = await db.get(Provider, sig.provider_id) if sig.provider_id else None
        d = await meta_agent.evaluate(db, sig, provider)
        return {
            "signal_id": d.signal_id,
            "ticker": d.ticker,
            "action": sig.action.value,
            "entry_price": sig.entry_price,
            "strategy_name": d.strategy_name,
            "strategy_name_ru": d.strategy_name_ru,
            "meta_score": d.meta_score,
            "recommendation": d.recommendation,
            "recommendation_ru": d.recommendation_ru,
            "regime": d.regime,
            "regime_compatible": d.regime_compatible,
        }

    evaluations = [await _eval(sig) for sig in recent]

    # Top 10 by quality — independent ranking (may overlap with latest)
    # Scan active + recent closed signals with highest AI confidence
    candidates = (await db.execute(
        select(Signal).where(Signal.ai_confidence.isnot(None))
        .order_by(Signal.ai_confidence.desc())
        .limit(50)
    )).scalars().all()

    top_evals_raw = []
    for sig in candidates:
        ev = await _eval(sig)
        top_evals_raw.append(ev)

    top_evals_raw.sort(key=lambda x: x["meta_score"], reverse=True)
    top_evals = top_evals_raw[:10]

    return {
        "market": {
            "regime": overall.regime.value,
            "confidence": overall.confidence,
            "volatility": overall.volatility_proxy,
            "signal_frequency": overall.signal_frequency,
            "buy_ratio": overall.buy_ratio,
        },
        "ticker_regimes": ticker_regimes,
        "evaluations": evaluations,
        "top_quality": top_evals,
        "architecture_level": 2,
        "architecture_levels": {
            1: "Regime Detection + Strategy Mapping + Execution",
            2: "Adaptive Scoring + AI Validation + Dynamic Weighting (CURRENT)",
            3: "Multi-Agent Decision + Reinforcement Learning (PLANNED)",
            4: "Evolutionary Ecosystem + Digital Twin (PLANNED)",
        },
    }


@router.get("/readiness")
async def architecture_readiness(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Check readiness for L3/L4 architecture transitions with detailed metrics."""
    from app.services.quant.readiness import readiness_monitor
    return await readiness_monitor.check_l3_readiness(db)


@router.get("/recommend/{signal_id}")
async def recommend_trade(
    signal_id: uuid.UUID,
    balance: float = 10000,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get TP/SL/Volume recommendation for a signal based on evolutionary analysis."""
    signal = (await db.execute(select(Signal).where(Signal.id == signal_id))).scalar_one_or_none()
    if not signal:
        raise HTTPException(404, "Signal not found")
    provider = await db.get(Provider, signal.provider_id) if signal.provider_id else None
    from app.services.quant.recommendations import recommendation_engine
    return await recommendation_engine.recommend(db, signal, provider, balance)


@router.get("/auto-evolve")
async def auto_evolve(user: User = Depends(get_current_user)):
    """Check MQL5 for new articles and evolve architecture. Rate-limited: 1/hour."""
    from app.services.quant.auto_evolution import check_and_evolve
    return await check_and_evolve()


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


@router.post("/langgraph/{signal_id}")
async def langgraph_evaluate(
    signal_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """LangGraph-агент: полная оценка сигнала через явный граф состояний.

    Phase 4 Step 4 — демонстрирует преимущества LangGraph перед imperative pipeline:
    - Каждый узел возвращает частичное состояние → audit trail в поле 'trace'
    - Условные переходы явные (approve/reject), не спрятаны в if-else
    - Новый узел llm_reasoning синтезирует человеко-читаемый вердикт на основе
      всего контекста (regime + WEF factors + meta_score) — чего нет в /evaluate

    Узлы: load_context → detect_regime → compute_wef → meta_evaluate
          → llm_reasoning → quality_gate → [approve | reject]

    Ответ содержит полный breakdown: wef_factors, meta_score, llm_analysis,
    quality_passed, rejection_reasons, trace всех шагов.
    """
    from app.services.quant.langgraph_signal_agent import run_signal_analysis

    state = await run_signal_analysis(db, signal_id)

    return {
        "signal_id": signal_id,
        "verdict": "approve" if state.get("quality_passed") else "reject",
        "regime": state.get("regime"),
        "regime_confidence": state.get("regime_confidence"),
        "wef_score": state.get("wef_score"),
        "wef_coverage": state.get("wef_coverage"),
        "wef_factors": state.get("wef_factors"),
        "meta_score": state.get("meta_score"),
        "meta_recommendation": state.get("meta_recommendation"),
        "meta_recommendation_ru": state.get("meta_recommendation_ru"),
        "strategy_name": state.get("strategy_name"),
        "regime_compatible": state.get("regime_compatible"),
        "llm_analysis": state.get("llm_analysis"),
        "quality_passed": state.get("quality_passed"),
        "rejection_reasons": state.get("rejection_reasons", []),
        "trace": state.get("trace", []),
    }
