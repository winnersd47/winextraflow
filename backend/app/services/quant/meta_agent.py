"""Meta Agent — Level 2: Adaptive Scoring + Dynamic Weighting.

The Meta Agent sits between signal classification and execution.
It evaluates signal quality in context of:
  - Market regime (from RegimeDetector)
  - Strategy classification (from StrategyClassifier)
  - Provider historical performance
  - AI confidence

Output: Enhanced signal score with regime-adjusted recommendation.

This is the foundation for Level 3 (Multi-Agent) and Level 4 (Evolutionary).
"""

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal import Signal
from app.models.provider import Provider
from app.services.quant.regime import MarketStateVector, MarketRegime, regime_detector
from app.services.quant.strategy_classifier import (
    StrategyClassifier,
    StrategyID,
    ClassificationResult,
    STRATEGY_META,
    strategy_classifier,
)

logger = logging.getLogger(__name__)


# Dynamic weights based on regime (Level 2: adaptive scoring)
REGIME_WEIGHTS = {
    MarketRegime.TRENDING_UP: {
        "ai_confidence": 0.25,
        "provider_score": 0.20,
        "risk_reward": 0.20,
        "regime_fit": 0.20,
        "strategy_confidence": 0.15,
    },
    MarketRegime.TRENDING_DOWN: {
        "ai_confidence": 0.25,
        "provider_score": 0.20,
        "risk_reward": 0.20,
        "regime_fit": 0.20,
        "strategy_confidence": 0.15,
    },
    MarketRegime.RANGING: {
        "ai_confidence": 0.20,
        "provider_score": 0.25,
        "risk_reward": 0.25,
        "regime_fit": 0.15,
        "strategy_confidence": 0.15,
    },
    MarketRegime.HIGH_VOLATILITY: {
        "ai_confidence": 0.15,
        "provider_score": 0.15,
        "risk_reward": 0.30,
        "regime_fit": 0.25,
        "strategy_confidence": 0.15,
    },
    MarketRegime.LOW_VOLATILITY: {
        "ai_confidence": 0.20,
        "provider_score": 0.30,
        "risk_reward": 0.20,
        "regime_fit": 0.15,
        "strategy_confidence": 0.15,
    },
    MarketRegime.BREAKOUT: {
        "ai_confidence": 0.15,
        "provider_score": 0.15,
        "risk_reward": 0.25,
        "regime_fit": 0.30,
        "strategy_confidence": 0.15,
    },
}

DEFAULT_WEIGHTS = {
    "ai_confidence": 0.25,
    "provider_score": 0.25,
    "risk_reward": 0.20,
    "regime_fit": 0.15,
    "strategy_confidence": 0.15,
}


@dataclass
class MetaAgentDecision:
    """Enhanced signal evaluation from the Meta Agent."""
    # Signal identification
    signal_id: str
    ticker: str

    # Market context
    regime: str
    regime_confidence: float

    # Strategy classification
    strategy_id: int
    strategy_name: str
    strategy_name_ru: str
    strategy_confidence: float
    regime_compatible: bool

    # Meta score (0.0 — 1.0)
    meta_score: float
    recommendation: str  # "strong_buy", "buy", "neutral", "avoid", "strong_avoid"
    recommendation_ru: str

    # Score breakdown
    factors: dict[str, float]
    weights: dict[str, float]

    # Reasoning
    reasoning: list[str]


RECOMMENDATIONS = {
    "strong_buy": "Excellent",
    "buy": "Good",
    "neutral": "Neutral",
    "avoid": "Weak",
    "strong_avoid": "Skip",
}

RECOMMENDATIONS_RU = {
    "strong_buy": "Отличный сигнал",
    "buy": "Хороший сигнал",
    "neutral": "Нейтрально",
    "avoid": "Слабый сигнал",
    "strong_avoid": "Пропустить",
}


class MetaAgent:
    """AI Meta Agent — evaluates signals with full market context."""

    async def evaluate(
        self,
        db: AsyncSession,
        signal: Signal,
        provider: Provider | None = None,
    ) -> MetaAgentDecision:
        """Full signal evaluation pipeline:
        1. Detect market regime
        2. Classify signal strategy
        3. Calculate dynamic-weighted meta score
        4. Generate recommendation
        """
        # Step 1: Market regime
        market_state = await regime_detector.detect(db, ticker=signal.ticker)

        # Step 2: Strategy classification
        classification = strategy_classifier.classify(signal, market_state)

        # Step 3: Factor calculation
        factors = {}

        # Factor: AI confidence
        factors["ai_confidence"] = signal.ai_confidence or 0.5

        # Factor: Provider historical score
        provider_score = 0.5
        if provider:
            if provider.ai_score:
                provider_score = provider.ai_score
            elif provider.win_rate:
                provider_score = provider.win_rate
        factors["provider_score"] = provider_score

        # Factor: Risk/Reward
        rr = 0.5
        if signal.take_profit and signal.stop_loss and signal.entry_price:
            entry = signal.entry_price
            from app.models.signal import SignalAction
            if signal.action == SignalAction.BUY:
                tp_d = abs(signal.take_profit - entry)
                sl_d = abs(entry - signal.stop_loss)
            else:
                tp_d = abs(entry - signal.take_profit)
                sl_d = abs(signal.stop_loss - entry)
            if sl_d > 0:
                rr_ratio = tp_d / sl_d
                rr = min(rr_ratio / 3.0, 1.0)  # Normalize: 3:1 R:R = 1.0
        factors["risk_reward"] = rr

        # Factor: Regime fit
        factors["regime_fit"] = 1.0 if classification.regime_compatible else 0.3

        # Factor: Strategy classification confidence
        factors["strategy_confidence"] = classification.confidence

        # Step 4: Dynamic weighting
        weights = REGIME_WEIGHTS.get(market_state.regime, DEFAULT_WEIGHTS)

        meta_score = sum(factors[k] * weights.get(k, 0.2) for k in factors)
        meta_score = round(min(max(meta_score, 0.0), 1.0), 3)

        # Step 5: Recommendation
        if meta_score >= 0.75:
            rec = "strong_buy"
        elif meta_score >= 0.55:
            rec = "buy"
        elif meta_score >= 0.40:
            rec = "neutral"
        elif meta_score >= 0.25:
            rec = "avoid"
        else:
            rec = "strong_avoid"

        # Reasoning
        reasoning = []
        strategy_meta = STRATEGY_META.get(classification.strategy_id, {})
        reasoning.append(f"Strategy: {strategy_meta.get('name', '?')} (ID {classification.strategy_id})")
        reasoning.append(f"Market regime: {market_state.regime.value} (conf {market_state.confidence:.0%})")
        reasoning.append(classification.reasoning)
        if not classification.regime_compatible:
            reasoning.append(f"WARNING: Strategy not optimal for {market_state.regime.value} regime")
        if provider:
            reasoning.append(f"Provider: {provider.name} (score {provider_score:.2f})")

        decision = MetaAgentDecision(
            signal_id=str(signal.id),
            ticker=signal.ticker,
            regime=market_state.regime.value,
            regime_confidence=market_state.confidence,
            strategy_id=classification.strategy_id,
            strategy_name=strategy_meta.get("name", "Unknown"),
            strategy_name_ru=strategy_meta.get("name_ru", "Неизвестная"),
            strategy_confidence=classification.confidence,
            regime_compatible=classification.regime_compatible,
            meta_score=meta_score,
            recommendation=rec,
            recommendation_ru=RECOMMENDATIONS_RU.get(rec, rec),
            factors={k: round(v, 3) for k, v in factors.items()},
            weights={k: round(v, 3) for k, v in weights.items()},
            reasoning=reasoning,
        )

        logger.info(
            f"MetaAgent: {signal.ticker} → {rec} (score={meta_score:.2f}, "
            f"strategy={classification.strategy_id}, regime={market_state.regime.value})"
        )

        # Record evolutionary event
        try:
            from app.services.quant.evolution import evolutionary_registry
            detected = ["regime_detection", "signal_confidence", "strategy_classification"]
            if signal.take_profit and signal.stop_loss:
                detected.append("risk_reward_analysis")
            if provider and provider.ai_score:
                detected.append("provider_scoring")
            if market_state.regime != MarketRegime.UNKNOWN:
                detected.append("dynamic_weighting")
            evolutionary_registry.record_signal_evolution(
                strategy_id=classification.strategy_id,
                meta_score=meta_score,
                regime=market_state.regime.value,
                components_detected=detected,
            )
        except Exception as e:
            logger.warning(f"Evolution recording failed: {e}")

        return decision


meta_agent = MetaAgent()
