"""Market Regime Detection — Level 1 of Autonomous Architecture.

Classifies current market state into regimes:
  TRENDING_UP, TRENDING_DOWN, RANGING, HIGH_VOLATILITY, LOW_VOLATILITY, BREAKOUT

Uses signal flow analysis: price direction, TP/SL hit ratios, volatility proxy.
No external market data needed — works entirely from platform's own signal history.
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal import Signal, SignalAction, SignalStatus

logger = logging.getLogger(__name__)


class MarketRegime(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    BREAKOUT = "breakout"
    UNKNOWN = "unknown"


@dataclass
class MarketStateVector:
    """Feature vector describing current market state."""
    regime: MarketRegime
    confidence: float  # 0.0 — 1.0
    buy_ratio: float   # % of BUY signals in recent window
    tp_hit_rate: float  # TP hit rate in recent closed signals
    sl_hit_rate: float  # SL hit rate
    avg_profit_pct: float  # average profit of recent closed signals
    volatility_proxy: float  # stddev of profit_pct (proxy for market volatility)
    signal_frequency: float  # signals per hour in recent window
    dominant_tickers: list[str]  # top tickers by frequency
    timestamp: str


class RegimeDetector:
    """Detects market regime from platform signal data (no external feeds needed)."""

    def __init__(self, lookback_hours: int = 720):  # 30 days default
        self.lookback_hours = lookback_hours

    async def detect(self, db: AsyncSession, ticker: str | None = None) -> MarketStateVector:
        """Analyze recent signals and classify market regime."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours)

        # Recent signals
        query = select(Signal).where(Signal.created_at >= cutoff)
        if ticker:
            query = query.where(Signal.ticker == ticker.upper())
        result = await db.execute(query.order_by(Signal.created_at.desc()))
        signals = result.scalars().all()

        if len(signals) < 3:
            return MarketStateVector(
                regime=MarketRegime.UNKNOWN, confidence=0.0,
                buy_ratio=0.5, tp_hit_rate=0.0, sl_hit_rate=0.0,
                avg_profit_pct=0.0, volatility_proxy=0.0, signal_frequency=0.0,
                dominant_tickers=[], timestamp=datetime.now(timezone.utc).isoformat(),
            )

        # ─── Feature extraction ──────────────────────────────
        total = len(signals)
        buys = sum(1 for s in signals if s.action == SignalAction.BUY)
        buy_ratio = buys / total

        closed = [s for s in signals if s.profit_pct is not None]
        tp_hits = sum(1 for s in closed if s.status == SignalStatus.CLOSED_TP)
        sl_hits = sum(1 for s in closed if s.status == SignalStatus.CLOSED_SL)
        closed_count = len(closed)

        tp_hit_rate = tp_hits / closed_count if closed_count > 0 else 0.0
        sl_hit_rate = sl_hits / closed_count if closed_count > 0 else 0.0

        profits = [s.profit_pct for s in closed if s.profit_pct is not None]
        avg_profit = sum(profits) / len(profits) if profits else 0.0
        vol_proxy = 0.0
        if len(profits) >= 2:
            mean = sum(profits) / len(profits)
            vol_proxy = math.sqrt(sum((p - mean) ** 2 for p in profits) / len(profits))

        hours_span = max((signals[0].created_at - signals[-1].created_at).total_seconds() / 3600, 1) if len(signals) > 1 and signals[0].created_at and signals[-1].created_at else self.lookback_hours
        freq = total / hours_span

        # Top tickers
        ticker_counts: dict[str, int] = {}
        for s in signals:
            ticker_counts[s.ticker] = ticker_counts.get(s.ticker, 0) + 1
        dominant = sorted(ticker_counts, key=ticker_counts.get, reverse=True)[:5]

        # ─── Regime classification ───────────────────────────
        regime = MarketRegime.UNKNOWN
        confidence = 0.0

        if vol_proxy > 5.0:
            regime = MarketRegime.HIGH_VOLATILITY
            confidence = min(vol_proxy / 10.0, 1.0)
        elif vol_proxy < 1.5 and closed_count >= 3:
            regime = MarketRegime.LOW_VOLATILITY
            confidence = 1.0 - vol_proxy / 1.5
        elif buy_ratio > 0.65 and tp_hit_rate > 0.55:
            regime = MarketRegime.TRENDING_UP
            confidence = buy_ratio * tp_hit_rate * 1.5
        elif buy_ratio < 0.35 and tp_hit_rate > 0.55:
            regime = MarketRegime.TRENDING_DOWN
            confidence = (1 - buy_ratio) * tp_hit_rate * 1.5
        elif 0.4 <= buy_ratio <= 0.6 and tp_hit_rate > 0.5:
            regime = MarketRegime.RANGING
            confidence = tp_hit_rate
        elif sl_hit_rate > 0.5 and vol_proxy > 3.0:
            regime = MarketRegime.BREAKOUT
            confidence = sl_hit_rate * 0.8

        confidence = round(min(confidence, 1.0), 3)

        state = MarketStateVector(
            regime=regime,
            confidence=confidence,
            buy_ratio=round(buy_ratio, 3),
            tp_hit_rate=round(tp_hit_rate, 3),
            sl_hit_rate=round(sl_hit_rate, 3),
            avg_profit_pct=round(avg_profit, 2),
            volatility_proxy=round(vol_proxy, 2),
            signal_frequency=round(freq, 2),
            dominant_tickers=dominant,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        logger.info(f"Regime detected: {regime.value} (conf={confidence}, ticker={ticker or 'ALL'})")
        return state


regime_detector = RegimeDetector()
