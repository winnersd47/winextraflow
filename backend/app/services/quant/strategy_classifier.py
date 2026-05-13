"""Strategy Classifier — maps signals to Strategy IDs from the architecture.

Strategy IDs (from ARCHITECTURE_BASE.md):
  1. Trend Following
  2. Mean Reversion
  3. Range / Flat
  4. Breakout
  5. Multi-Indicator Systems
  6. Statistical / Arbitrage
  7. ML / AI Strategies

Classification uses signal characteristics: action, TP/SL distances,
provider history, AI confidence, market regime context.
"""

import logging
from dataclasses import dataclass
from enum import IntEnum

from app.models.signal import Signal, SignalAction
from app.services.quant.regime import MarketRegime, MarketStateVector

logger = logging.getLogger(__name__)


class StrategyID(IntEnum):
    """Strategy classification IDs per architecture spec."""
    TREND_FOLLOWING = 1
    MEAN_REVERSION = 2
    RANGE_FLAT = 3
    BREAKOUT = 4
    MULTI_INDICATOR = 5
    STATISTICAL_ARB = 6
    ML_AI = 7


STRATEGY_META = {
    StrategyID.TREND_FOLLOWING: {
        "name": "Trend Following",
        "name_ru": "Следование за трендом",
        "description": "Follows established market trends. Works best in trending markets.",
        "description_ru": "Следование за устоявшимся рыночным трендом. Лучше работает в трендовых рынках.",
        "best_regime": [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN],
        "risk": "medium",
    },
    StrategyID.MEAN_REVERSION: {
        "name": "Mean Reversion",
        "name_ru": "Возврат к среднему",
        "description": "Expects price to return to average. Works in ranging markets.",
        "description_ru": "Ожидание возврата цены к среднему значению. Работает в боковых рынках.",
        "best_regime": [MarketRegime.RANGING, MarketRegime.LOW_VOLATILITY],
        "risk": "medium",
    },
    StrategyID.RANGE_FLAT: {
        "name": "Range / Flat",
        "name_ru": "Диапазонная торговля",
        "description": "Trades within price channels. Tight TP/SL near support/resistance.",
        "description_ru": "Торговля внутри ценовых каналов. Близкие TP/SL у уровней поддержки/сопротивления.",
        "best_regime": [MarketRegime.RANGING, MarketRegime.LOW_VOLATILITY],
        "risk": "low",
    },
    StrategyID.BREAKOUT: {
        "name": "Breakout",
        "name_ru": "Пробой уровня",
        "description": "Catches price breakouts from consolidation. Wide TP, tight SL.",
        "description_ru": "Ловля пробоев из консолидации. Широкий TP, узкий SL.",
        "best_regime": [MarketRegime.BREAKOUT, MarketRegime.HIGH_VOLATILITY],
        "risk": "high",
    },
    StrategyID.MULTI_INDICATOR: {
        "name": "Multi-Indicator",
        "name_ru": "Мульти-индикаторная",
        "description": "Combines multiple technical indicators for confirmation.",
        "description_ru": "Комбинация нескольких технических индикаторов для подтверждения.",
        "best_regime": [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN, MarketRegime.RANGING],
        "risk": "medium",
    },
    StrategyID.STATISTICAL_ARB: {
        "name": "Statistical / Arbitrage",
        "name_ru": "Статистический арбитраж",
        "description": "Exploits statistical relationships between correlated assets.",
        "description_ru": "Использование статистических зависимостей между коррелированными активами.",
        "best_regime": [MarketRegime.LOW_VOLATILITY, MarketRegime.RANGING],
        "risk": "low",
    },
    StrategyID.ML_AI: {
        "name": "ML / AI Strategy",
        "name_ru": "ML / AI стратегия",
        "description": "Machine learning or AI-driven signal generation.",
        "description_ru": "Сигналы на основе машинного обучения или искусственного интеллекта.",
        "best_regime": list(MarketRegime),
        "risk": "variable",
    },
}


@dataclass
class ClassificationResult:
    strategy_id: StrategyID
    confidence: float
    reasoning: str
    regime_compatible: bool  # Is this strategy suitable for current regime?


class StrategyClassifier:
    """Classifies signals into Strategy IDs based on signal characteristics."""

    def classify(self, signal: Signal, market_state: MarketStateVector | None = None) -> ClassificationResult:
        """Classify a signal into a Strategy ID."""

        # Feature extraction from signal
        has_tp = signal.take_profit is not None
        has_sl = signal.stop_loss is not None
        entry = signal.entry_price or 1.0

        rr_ratio = 0.0
        tp_dist_pct = 0.0
        sl_dist_pct = 0.0

        if has_tp:
            if signal.action == SignalAction.BUY:
                tp_dist_pct = abs(signal.take_profit - entry) / entry * 100
            else:
                tp_dist_pct = abs(entry - signal.take_profit) / entry * 100
        if has_sl:
            if signal.action == SignalAction.BUY:
                sl_dist_pct = abs(entry - signal.stop_loss) / entry * 100
            else:
                sl_dist_pct = abs(signal.stop_loss - entry) / entry * 100
        if sl_dist_pct > 0:
            rr_ratio = tp_dist_pct / sl_dist_pct

        ai_conf = signal.ai_confidence or 0.5

        # ─── Classification rules ────────────────────────────
        strategy_id = StrategyID.MULTI_INDICATOR  # default
        confidence = 0.5
        reasoning = ""

        if ai_conf >= 0.8:
            # High AI confidence → likely ML/AI generated
            strategy_id = StrategyID.ML_AI
            confidence = ai_conf
            reasoning = f"High AI confidence ({ai_conf:.0%}) suggests ML-driven signal"

        elif rr_ratio >= 2.5 and tp_dist_pct > 3.0:
            # Wide TP, tight SL → Breakout
            strategy_id = StrategyID.BREAKOUT
            confidence = min(rr_ratio / 4.0, 0.9)
            reasoning = f"R:R={rr_ratio:.1f}, TP dist={tp_dist_pct:.1f}% — breakout pattern"

        elif rr_ratio >= 1.5 and tp_dist_pct > 2.0:
            # Good R:R with moderate distance → Trend Following
            strategy_id = StrategyID.TREND_FOLLOWING
            confidence = min(rr_ratio / 3.0, 0.85)
            reasoning = f"R:R={rr_ratio:.1f}, TP={tp_dist_pct:.1f}% — trend following"

        elif has_tp and has_sl and tp_dist_pct < 1.5 and sl_dist_pct < 1.5:
            # Tight TP and SL → Range/Flat
            strategy_id = StrategyID.RANGE_FLAT
            confidence = 0.7
            reasoning = f"Tight TP({tp_dist_pct:.1f}%) + SL({sl_dist_pct:.1f}%) — range trading"

        elif has_tp and tp_dist_pct < 2.0 and rr_ratio < 1.2:
            # Small expected profit, low R:R → Mean Reversion
            strategy_id = StrategyID.MEAN_REVERSION
            confidence = 0.65
            reasoning = f"Low R:R={rr_ratio:.1f}, small TP({tp_dist_pct:.1f}%) — mean reversion"

        elif not has_tp or not has_sl:
            # Missing risk levels → Multi-indicator (less structured)
            strategy_id = StrategyID.MULTI_INDICATOR
            confidence = 0.4
            reasoning = "Missing TP/SL — multi-indicator or discretionary"

        # Regime compatibility check
        regime_compatible = True
        if market_state and market_state.regime != MarketRegime.UNKNOWN:
            meta = STRATEGY_META.get(strategy_id, {})
            best = meta.get("best_regime", [])
            regime_compatible = market_state.regime in best
            if not regime_compatible:
                confidence *= 0.7  # Penalize incompatible strategies
                reasoning += f" [WARN: regime {market_state.regime.value} not ideal]"

        return ClassificationResult(
            strategy_id=strategy_id,
            confidence=round(confidence, 3),
            reasoning=reasoning,
            regime_compatible=regime_compatible,
        )


strategy_classifier = StrategyClassifier()
