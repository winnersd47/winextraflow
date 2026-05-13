"""Autonomous Market Intelligence Ecosystem — integrated into WinExtraFlow.

Architecture levels:
  Level 1: Regime Detection → Strategy Mapping → Execution
  Level 2: Adaptive Scoring → AI Validation → Dynamic Weighting
  Level 3: Multi-Agent Decision → Reinforcement Learning → Feedback Loop (future)
  Level 4: Evolutionary Ecosystem → Digital Twin → Autonomous Intelligence (future)
"""

from app.services.quant.regime import RegimeDetector, MarketRegime
from app.services.quant.strategy_classifier import StrategyClassifier, StrategyID
from app.services.quant.meta_agent import MetaAgent

__all__ = [
    "RegimeDetector", "MarketRegime",
    "StrategyClassifier", "StrategyID",
    "MetaAgent",
]
