"""AI Rating service — signal scoring and provider statistics.

Evaluates trading signals based on multiple factors and maintains
aggregate provider statistics for the leaderboard.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import Provider
from app.models.signal import Signal, SignalAction, SignalStatus

logger = logging.getLogger(__name__)

# --- Scoring weights ---
WEIGHT_RISK_MANAGEMENT = 0.25  # Has TP and SL
WEIGHT_RISK_REWARD = 0.25  # TP/SL ratio
WEIGHT_PROVIDER_HISTORY = 0.30  # Provider win rate
WEIGHT_SIGNAL_FREQUENCY = 0.10  # Spam penalty
WEIGHT_COMPLETENESS = 0.10  # Signal data completeness

# Provider composite score weights
PROVIDER_WIN_RATE_WEIGHT = 0.40
PROVIDER_CONSISTENCY_WEIGHT = 0.30
PROVIDER_PROFIT_WEIGHT = 0.30

# Spam threshold: max signals per hour before penalty
SPAM_THRESHOLD_PER_HOUR = 10


@dataclass
class RatingBreakdown:
    """Detailed breakdown of a signal's AI rating."""

    risk_management_score: float = 0.0
    risk_management_reason: str = ""

    risk_reward_score: float = 0.0
    risk_reward_reason: str = ""

    provider_history_score: float = 0.0
    provider_history_reason: str = ""

    signal_frequency_score: float = 0.0
    signal_frequency_reason: str = ""

    completeness_score: float = 0.0
    completeness_reason: str = ""

    final_confidence: float = 0.0
    reasoning: str = ""

    def to_dict(self) -> dict:
        return {
            "final_confidence": round(self.final_confidence, 3),
            "reasoning": self.reasoning,
            "factors": {
                "risk_management": {
                    "score": round(self.risk_management_score, 3),
                    "weight": WEIGHT_RISK_MANAGEMENT,
                    "reason": self.risk_management_reason,
                },
                "risk_reward": {
                    "score": round(self.risk_reward_score, 3),
                    "weight": WEIGHT_RISK_REWARD,
                    "reason": self.risk_reward_reason,
                },
                "provider_history": {
                    "score": round(self.provider_history_score, 3),
                    "weight": WEIGHT_PROVIDER_HISTORY,
                    "reason": self.provider_history_reason,
                },
                "signal_frequency": {
                    "score": round(self.signal_frequency_score, 3),
                    "weight": WEIGHT_SIGNAL_FREQUENCY,
                    "reason": self.signal_frequency_reason,
                },
                "completeness": {
                    "score": round(self.completeness_score, 3),
                    "weight": WEIGHT_COMPLETENESS,
                    "reason": self.completeness_reason,
                },
            },
        }


class AIRatingService:
    """Scores trading signals and calculates provider statistics."""

    # ─── Signal Rating ─────────────────────────────────────────

    def _score_risk_management(self, signal: Signal) -> tuple[float, str]:
        """Score based on presence and quality of TP/SL."""
        has_tp = signal.take_profit is not None
        has_sl = signal.stop_loss is not None

        if has_tp and has_sl:
            return 1.0, "Both TP and SL defined — solid risk management"
        elif has_tp or has_sl:
            return 0.5, f"Only {'TP' if has_tp else 'SL'} defined — partial risk management"
        else:
            return 0.1, "No TP or SL — poor risk management"

    def _score_risk_reward(self, signal: Signal) -> tuple[float, str]:
        """Score based on risk/reward ratio."""
        if signal.take_profit is None or signal.stop_loss is None:
            return 0.5, "Cannot calculate R:R — missing TP or SL"

        entry = signal.entry_price
        if entry <= 0:
            return 0.0, "Invalid entry price"

        if signal.action == SignalAction.BUY:
            reward = abs(signal.take_profit - entry)
            risk = abs(entry - signal.stop_loss)
        else:  # SELL
            reward = abs(entry - signal.take_profit)
            risk = abs(signal.stop_loss - entry)

        if risk <= 0:
            return 0.1, "SL at or above entry — invalid risk"

        rr_ratio = reward / risk

        if rr_ratio >= 3.0:
            return 1.0, f"Excellent R:R ratio {rr_ratio:.1f}:1"
        elif rr_ratio >= 2.0:
            return 0.8, f"Good R:R ratio {rr_ratio:.1f}:1"
        elif rr_ratio >= 1.5:
            return 0.6, f"Acceptable R:R ratio {rr_ratio:.1f}:1"
        elif rr_ratio >= 1.0:
            return 0.4, f"Low R:R ratio {rr_ratio:.1f}:1"
        else:
            return 0.15, f"Poor R:R ratio {rr_ratio:.1f}:1 — risk exceeds reward"

    async def _score_provider_history(
        self, db: AsyncSession, provider_id: uuid.UUID
    ) -> tuple[float, str]:
        """Score based on provider's historical performance."""
        provider = await db.get(Provider, provider_id)
        if not provider:
            return 0.5, "Provider not found"

        if provider.total_signals < 5:
            return 0.5, f"New provider — only {provider.total_signals} signals, insufficient history"

        win_rate = provider.win_rate
        if win_rate is None:
            return 0.5, "No closed signals yet"

        if win_rate >= 0.7:
            return 1.0, f"Excellent win rate: {win_rate:.0%}"
        elif win_rate >= 0.55:
            return 0.7, f"Good win rate: {win_rate:.0%}"
        elif win_rate >= 0.4:
            return 0.4, f"Average win rate: {win_rate:.0%}"
        else:
            return 0.15, f"Poor win rate: {win_rate:.0%}"

    async def _score_signal_frequency(
        self, db: AsyncSession, provider_id: uuid.UUID
    ) -> tuple[float, str]:
        """Penalize providers that spam signals."""
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        result = await db.execute(
            select(func.count()).select_from(Signal).where(
                and_(
                    Signal.provider_id == provider_id,
                    Signal.created_at >= one_hour_ago,
                )
            )
        )
        recent_count = result.scalar() or 0

        if recent_count <= 3:
            return 1.0, f"{recent_count} signals in last hour — normal frequency"
        elif recent_count <= SPAM_THRESHOLD_PER_HOUR:
            return 0.6, f"{recent_count} signals in last hour — elevated frequency"
        else:
            return 0.1, f"{recent_count} signals in last hour — spam detected"

    def _score_completeness(self, signal: Signal) -> tuple[float, str]:
        """Score based on how complete the signal data is."""
        fields_present = 0
        total_fields = 4  # TP, SL, timeframe, raw_message

        if signal.take_profit is not None:
            fields_present += 1
        if signal.stop_loss is not None:
            fields_present += 1
        if signal.timeframe:
            fields_present += 1
        if signal.raw_message:
            fields_present += 1

        score = fields_present / total_fields
        return score, f"{fields_present}/{total_fields} optional fields provided"

    async def rate_signal(
        self, db: AsyncSession, signal: Signal
    ) -> RatingBreakdown:
        """Calculate AI confidence score for a signal.

        Returns a RatingBreakdown with detailed factor analysis.
        """
        breakdown = RatingBreakdown()

        # 1. Risk management
        score, reason = self._score_risk_management(signal)
        breakdown.risk_management_score = score
        breakdown.risk_management_reason = reason

        # 2. Risk/Reward ratio
        score, reason = self._score_risk_reward(signal)
        breakdown.risk_reward_score = score
        breakdown.risk_reward_reason = reason

        # 3. Provider history
        score, reason = await self._score_provider_history(db, signal.provider_id)
        breakdown.provider_history_score = score
        breakdown.provider_history_reason = reason

        # 4. Signal frequency
        score, reason = await self._score_signal_frequency(db, signal.provider_id)
        breakdown.signal_frequency_score = score
        breakdown.signal_frequency_reason = reason

        # 5. Completeness
        score, reason = self._score_completeness(signal)
        breakdown.completeness_score = score
        breakdown.completeness_reason = reason

        # Weighted sum
        confidence = (
            breakdown.risk_management_score * WEIGHT_RISK_MANAGEMENT
            + breakdown.risk_reward_score * WEIGHT_RISK_REWARD
            + breakdown.provider_history_score * WEIGHT_PROVIDER_HISTORY
            + breakdown.signal_frequency_score * WEIGHT_SIGNAL_FREQUENCY
            + breakdown.completeness_score * WEIGHT_COMPLETENESS
        )
        breakdown.final_confidence = max(0.0, min(1.0, confidence))

        # Build reasoning summary
        factors = []
        if breakdown.risk_management_score >= 0.8:
            factors.append("good risk management")
        if breakdown.risk_reward_score >= 0.8:
            factors.append("favorable R:R ratio")
        if breakdown.provider_history_score >= 0.7:
            factors.append("reliable provider")
        if breakdown.signal_frequency_score < 0.5:
            factors.append("high signal frequency")

        if factors:
            breakdown.reasoning = "Key factors: " + ", ".join(factors)
        else:
            breakdown.reasoning = "Average signal quality across all factors"

        return breakdown

    async def rate_and_update_signal(
        self, db: AsyncSession, signal: Signal
    ) -> Signal:
        """Rate a signal and persist the scores to the database."""
        breakdown = await self.rate_signal(db, signal)
        signal.ai_confidence = breakdown.final_confidence
        signal.ai_reasoning = breakdown.reasoning
        await db.commit()
        await db.refresh(signal)
        logger.info(
            f"Rated signal {signal.id}: confidence={breakdown.final_confidence:.2f}"
        )
        return signal

    # ─── Signal Lifecycle ──────────────────────────────────────

    async def close_signal(
        self,
        db: AsyncSession,
        signal: Signal,
        close_price: float,
        status: SignalStatus | None = None,
    ) -> Signal:
        """Close a signal with the given price and calculate profit.

        If status is not provided, auto-determines based on TP/SL hit.
        """
        if signal.status != SignalStatus.ACTIVE:
            raise ValueError(f"Signal already closed with status {signal.status.value}")

        signal.close_price = close_price

        # Calculate profit percentage
        if signal.action == SignalAction.BUY:
            signal.profit_pct = ((close_price - signal.entry_price) / signal.entry_price) * 100
        else:  # SELL
            signal.profit_pct = ((signal.entry_price - close_price) / signal.entry_price) * 100

        # Auto-determine status
        if status:
            signal.status = status
        elif signal.profit_pct >= 0:
            signal.status = SignalStatus.CLOSED_TP
        else:
            signal.status = SignalStatus.CLOSED_SL

        await db.commit()
        await db.refresh(signal)

        # Recalculate provider stats
        await self.recalculate_provider_stats(db, signal.provider_id)

        logger.info(
            f"Closed signal {signal.id}: {signal.status.value}, "
            f"profit={signal.profit_pct:.2f}%"
        )
        return signal

    async def expire_old_signals(self, db: AsyncSession, max_age_hours: int = 168):
        """Expire active signals older than max_age_hours (default 7 days)."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        result = await db.execute(
            select(Signal).where(
                and_(
                    Signal.status == SignalStatus.ACTIVE,
                    Signal.created_at < cutoff,
                )
            )
        )
        expired_signals = result.scalars().all()
        provider_ids = set()

        for signal in expired_signals:
            signal.status = SignalStatus.EXPIRED
            provider_ids.add(signal.provider_id)

        if expired_signals:
            await db.commit()
            logger.info(f"Expired {len(expired_signals)} old signals")

            # Recalculate stats for affected providers
            for pid in provider_ids:
                await self.recalculate_provider_stats(db, pid)

        return len(expired_signals)

    # ─── Provider Statistics ───────────────────────────────────

    async def recalculate_provider_stats(
        self, db: AsyncSession, provider_id: uuid.UUID
    ) -> Provider | None:
        """Recalculate all statistics for a provider based on closed signals."""
        provider = await db.get(Provider, provider_id)
        if not provider:
            return None

        # Count closed signals by status
        closed_statuses = [
            SignalStatus.CLOSED_TP,
            SignalStatus.CLOSED_SL,
            SignalStatus.CLOSED_MANUAL,
        ]

        tp_count = (
            await db.execute(
                select(func.count()).select_from(Signal).where(
                    and_(
                        Signal.provider_id == provider_id,
                        Signal.status == SignalStatus.CLOSED_TP,
                    )
                )
            )
        ).scalar() or 0

        sl_count = (
            await db.execute(
                select(func.count()).select_from(Signal).where(
                    and_(
                        Signal.provider_id == provider_id,
                        Signal.status == SignalStatus.CLOSED_SL,
                    )
                )
            )
        ).scalar() or 0

        total_closed = tp_count + sl_count

        # Win rate
        if total_closed > 0:
            provider.win_rate = tp_count / total_closed
        else:
            provider.win_rate = None

        # Average profit
        avg_result = await db.execute(
            select(func.avg(Signal.profit_pct)).where(
                and_(
                    Signal.provider_id == provider_id,
                    Signal.status.in_(closed_statuses),
                    Signal.profit_pct.isnot(None),
                )
            )
        )
        provider.avg_profit = avg_result.scalar()

        # Consistency: standard deviation of profits (lower = more consistent)
        stddev_result = await db.execute(
            select(func.coalesce(func.stddev(Signal.profit_pct), 0.0)).where(
                and_(
                    Signal.provider_id == provider_id,
                    Signal.status.in_(closed_statuses),
                    Signal.profit_pct.isnot(None),
                )
            )
        )
        profit_stddev = stddev_result.scalar() or 0.0
        # Convert stddev to consistency score (0-1): lower stddev = higher consistency
        consistency_score = max(0.0, 1.0 - (profit_stddev / 50.0))

        # Normalized profit score (0-1)
        avg_profit = provider.avg_profit or 0.0
        profit_score = max(0.0, min(1.0, (avg_profit + 10) / 20))  # -10% → 0, +10% → 1

        # Composite AI score
        if provider.win_rate is not None:
            provider.ai_score = (
                provider.win_rate * PROVIDER_WIN_RATE_WEIGHT
                + consistency_score * PROVIDER_CONSISTENCY_WEIGHT
                + profit_score * PROVIDER_PROFIT_WEIGHT
            )
        else:
            provider.ai_score = None

        # Total signals count
        total_result = await db.execute(
            select(func.count()).select_from(Signal).where(
                Signal.provider_id == provider_id
            )
        )
        provider.total_signals = total_result.scalar() or 0

        await db.commit()
        await db.refresh(provider)

        logger.info(
            f"Updated provider {provider.name} stats: "
            f"win_rate={provider.win_rate}, avg_profit={provider.avg_profit}, "
            f"ai_score={provider.ai_score}"
        )
        return provider


ai_rating_service = AIRatingService()
