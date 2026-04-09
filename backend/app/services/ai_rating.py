"""AI Rating service — enhanced signal scoring and provider statistics.

Evaluates trading signals based on 9 weighted factors including
Sharpe Ratio, Profit Factor, Max Drawdown, and Time Decay.
Maintains aggregate provider statistics for the leaderboard.
"""

import logging
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import Provider
from app.models.signal import Signal, SignalAction, SignalStatus

logger = logging.getLogger(__name__)

# ─── Scoring weights (9 factors, total = 1.0) ─────────────────
WEIGHTS = {
    "risk_management": 0.15,
    "risk_reward": 0.15,
    "provider_history": 0.15,
    "sharpe_ratio": 0.15,
    "profit_factor": 0.10,
    "max_drawdown": 0.10,
    "time_decay": 0.05,
    "signal_frequency": 0.08,
    "completeness": 0.07,
}

# Provider composite score weights
PROVIDER_WEIGHTS = {
    "win_rate": 0.25,
    "consistency": 0.15,
    "profit": 0.15,
    "sharpe": 0.20,
    "profit_factor": 0.15,
    "drawdown": 0.10,
}

SPAM_THRESHOLD_PER_HOUR = 10
# Risk-free rate for Sharpe (annualized, e.g. 5%)
RISK_FREE_RATE_DAILY = 0.05 / 365


@dataclass
class RatingBreakdown:
    """Detailed breakdown of a signal's AI rating."""

    scores: dict[str, float] = None
    reasons: dict[str, str] = None
    final_confidence: float = 0.0
    reasoning: str = ""

    def __post_init__(self):
        if self.scores is None:
            self.scores = {}
        if self.reasons is None:
            self.reasons = {}

    def to_dict(self) -> dict:
        return {
            "final_confidence": round(self.final_confidence, 3),
            "reasoning": self.reasoning,
            "factors": {
                key: {
                    "score": round(self.scores.get(key, 0), 3),
                    "weight": WEIGHTS.get(key, 0),
                    "reason": self.reasons.get(key, ""),
                }
                for key in WEIGHTS
            },
        }


class AIRatingService:
    """Scores trading signals and calculates provider statistics."""

    # ─── Signal Rating Factors ─────────────────────────────────

    def _score_risk_management(self, signal: Signal) -> tuple[float, str]:
        has_tp = signal.take_profit is not None
        has_sl = signal.stop_loss is not None
        if has_tp and has_sl:
            return 1.0, "Both TP and SL defined — solid risk management"
        elif has_tp or has_sl:
            return 0.5, f"Only {'TP' if has_tp else 'SL'} defined — partial risk management"
        return 0.1, "No TP or SL — poor risk management"

    def _score_risk_reward(self, signal: Signal) -> tuple[float, str]:
        if signal.take_profit is None or signal.stop_loss is None:
            return 0.5, "Cannot calculate R:R — missing TP or SL"
        entry = signal.entry_price
        if entry <= 0:
            return 0.0, "Invalid entry price"

        if signal.action == SignalAction.BUY:
            reward = abs(signal.take_profit - entry)
            risk = abs(entry - signal.stop_loss)
        else:
            reward = abs(entry - signal.take_profit)
            risk = abs(signal.stop_loss - entry)

        if risk <= 0:
            return 0.1, "SL at or above entry — invalid risk"

        rr = reward / risk
        if rr >= 3.0:
            return 1.0, f"Excellent R:R {rr:.1f}:1"
        if rr >= 2.0:
            return 0.8, f"Good R:R {rr:.1f}:1"
        if rr >= 1.5:
            return 0.6, f"Acceptable R:R {rr:.1f}:1"
        if rr >= 1.0:
            return 0.4, f"Low R:R {rr:.1f}:1"
        return 0.15, f"Poor R:R {rr:.1f}:1 — risk exceeds reward"

    async def _score_provider_history(
        self, db: AsyncSession, provider_id: uuid.UUID
    ) -> tuple[float, str]:
        provider = await db.get(Provider, provider_id)
        if not provider:
            return 0.5, "Provider not found"
        if provider.total_signals < 5:
            return 0.5, f"New provider — {provider.total_signals} signals"
        wr = provider.win_rate
        if wr is None:
            return 0.5, "No closed signals yet"
        if wr >= 0.7:
            return 1.0, f"Excellent win rate: {wr:.0%}"
        if wr >= 0.55:
            return 0.7, f"Good win rate: {wr:.0%}"
        if wr >= 0.4:
            return 0.4, f"Average win rate: {wr:.0%}"
        return 0.15, f"Poor win rate: {wr:.0%}"

    async def _score_sharpe_ratio(
        self, db: AsyncSession, provider_id: uuid.UUID
    ) -> tuple[float, str]:
        """Score based on provider's Sharpe Ratio."""
        provider = await db.get(Provider, provider_id)
        if not provider or provider.sharpe_ratio is None:
            return 0.5, "Sharpe ratio not available"
        sr = provider.sharpe_ratio
        if sr >= 2.0:
            return 1.0, f"Excellent Sharpe ratio: {sr:.2f}"
        if sr >= 1.0:
            return 0.75, f"Good Sharpe ratio: {sr:.2f}"
        if sr >= 0.5:
            return 0.5, f"Average Sharpe ratio: {sr:.2f}"
        if sr >= 0:
            return 0.25, f"Low Sharpe ratio: {sr:.2f}"
        return 0.1, f"Negative Sharpe ratio: {sr:.2f}"

    async def _score_profit_factor(
        self, db: AsyncSession, provider_id: uuid.UUID
    ) -> tuple[float, str]:
        """Score based on provider's Profit Factor (gross profit / gross loss)."""
        provider = await db.get(Provider, provider_id)
        if not provider or provider.profit_factor is None:
            return 0.5, "Profit factor not available"
        pf = provider.profit_factor
        if pf >= 3.0:
            return 1.0, f"Excellent profit factor: {pf:.2f}"
        if pf >= 2.0:
            return 0.8, f"Good profit factor: {pf:.2f}"
        if pf >= 1.5:
            return 0.6, f"Acceptable profit factor: {pf:.2f}"
        if pf >= 1.0:
            return 0.35, f"Marginal profit factor: {pf:.2f}"
        return 0.1, f"Losing strategy — PF: {pf:.2f}"

    async def _score_max_drawdown(
        self, db: AsyncSession, provider_id: uuid.UUID
    ) -> tuple[float, str]:
        """Score based on provider's maximum drawdown (lower is better)."""
        provider = await db.get(Provider, provider_id)
        if not provider or provider.max_drawdown is None:
            return 0.5, "Max drawdown not available"
        dd = abs(provider.max_drawdown)
        if dd <= 5:
            return 1.0, f"Minimal drawdown: {dd:.1f}%"
        if dd <= 10:
            return 0.8, f"Low drawdown: {dd:.1f}%"
        if dd <= 20:
            return 0.55, f"Moderate drawdown: {dd:.1f}%"
        if dd <= 35:
            return 0.3, f"High drawdown: {dd:.1f}%"
        return 0.1, f"Severe drawdown: {dd:.1f}%"

    async def _score_time_decay(
        self, db: AsyncSession, provider_id: uuid.UUID
    ) -> tuple[float, str]:
        """Score recent performance higher than old performance.

        Looks at the last 30 days of closed signals vs prior history.
        """
        now = datetime.now(timezone.utc)
        thirty_days_ago = now - timedelta(days=30)
        closed_statuses = [SignalStatus.CLOSED_TP, SignalStatus.CLOSED_SL]

        # Recent win rate (last 30 days)
        recent_tp = (await db.execute(
            select(func.count()).select_from(Signal).where(and_(
                Signal.provider_id == provider_id,
                Signal.status == SignalStatus.CLOSED_TP,
                Signal.updated_at >= thirty_days_ago,
            ))
        )).scalar() or 0

        recent_sl = (await db.execute(
            select(func.count()).select_from(Signal).where(and_(
                Signal.provider_id == provider_id,
                Signal.status == SignalStatus.CLOSED_SL,
                Signal.updated_at >= thirty_days_ago,
            ))
        )).scalar() or 0

        recent_total = recent_tp + recent_sl
        if recent_total < 3:
            return 0.5, "Insufficient recent data (last 30 days)"

        recent_wr = recent_tp / recent_total

        # Compare with overall
        provider = await db.get(Provider, provider_id)
        overall_wr = provider.win_rate if provider and provider.win_rate else 0.5

        if recent_wr > overall_wr + 0.1:
            return 0.9, f"Improving: recent WR {recent_wr:.0%} > overall {overall_wr:.0%}"
        if recent_wr >= overall_wr - 0.05:
            return 0.6, f"Stable: recent WR {recent_wr:.0%} ~ overall {overall_wr:.0%}"
        return 0.2, f"Declining: recent WR {recent_wr:.0%} < overall {overall_wr:.0%}"

    async def _score_signal_frequency(
        self, db: AsyncSession, provider_id: uuid.UUID
    ) -> tuple[float, str]:
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        result = await db.execute(
            select(func.count()).select_from(Signal).where(and_(
                Signal.provider_id == provider_id,
                Signal.created_at >= one_hour_ago,
            ))
        )
        count = result.scalar() or 0
        if count <= 3:
            return 1.0, f"{count} signals/hour — normal"
        if count <= SPAM_THRESHOLD_PER_HOUR:
            return 0.6, f"{count} signals/hour — elevated"
        return 0.1, f"{count} signals/hour — spam"

    def _score_completeness(self, signal: Signal) -> tuple[float, str]:
        present = sum([
            signal.take_profit is not None,
            signal.stop_loss is not None,
            bool(signal.timeframe),
            bool(signal.raw_message),
        ])
        score = present / 4
        return score, f"{present}/4 optional fields provided"

    # ─── Rate Signal ──────────────────────────────────────────

    async def rate_signal(
        self, db: AsyncSession, signal: Signal
    ) -> RatingBreakdown:
        breakdown = RatingBreakdown()

        # Evaluate all factors
        factor_funcs = {
            "risk_management": lambda: self._score_risk_management(signal),
            "risk_reward": lambda: self._score_risk_reward(signal),
            "completeness": lambda: self._score_completeness(signal),
        }
        async_factor_funcs = {
            "provider_history": lambda: self._score_provider_history(db, signal.provider_id),
            "sharpe_ratio": lambda: self._score_sharpe_ratio(db, signal.provider_id),
            "profit_factor": lambda: self._score_profit_factor(db, signal.provider_id),
            "max_drawdown": lambda: self._score_max_drawdown(db, signal.provider_id),
            "time_decay": lambda: self._score_time_decay(db, signal.provider_id),
            "signal_frequency": lambda: self._score_signal_frequency(db, signal.provider_id),
        }

        # Sync factors
        for key, fn in factor_funcs.items():
            score, reason = fn()
            breakdown.scores[key] = score
            breakdown.reasons[key] = reason

        # Async factors
        for key, fn in async_factor_funcs.items():
            score, reason = await fn()
            breakdown.scores[key] = score
            breakdown.reasons[key] = reason

        # Weighted sum
        confidence = sum(
            breakdown.scores.get(k, 0.5) * w for k, w in WEIGHTS.items()
        )
        breakdown.final_confidence = max(0.0, min(1.0, confidence))

        # Build reasoning
        strong = [k.replace("_", " ") for k, s in breakdown.scores.items() if s >= 0.8]
        weak = [k.replace("_", " ") for k, s in breakdown.scores.items() if s <= 0.3]

        parts = []
        if strong:
            parts.append(f"Strong: {', '.join(strong)}")
        if weak:
            parts.append(f"Weak: {', '.join(weak)}")
        breakdown.reasoning = ". ".join(parts) if parts else "Average quality across all factors"

        return breakdown

    async def rate_and_update_signal(
        self, db: AsyncSession, signal: Signal
    ) -> Signal:
        breakdown = await self.rate_signal(db, signal)
        signal.ai_confidence = breakdown.final_confidence
        signal.ai_reasoning = breakdown.reasoning
        await db.commit()
        await db.refresh(signal)
        logger.info(f"Rated signal {signal.id}: confidence={breakdown.final_confidence:.2f}")
        return signal

    # ─── Signal Lifecycle ──────────────────────────────────────

    async def close_signal(
        self,
        db: AsyncSession,
        signal: Signal,
        close_price: float,
        status: SignalStatus | None = None,
    ) -> Signal:
        if signal.status != SignalStatus.ACTIVE:
            raise ValueError(f"Signal already closed with status {signal.status.value}")

        signal.close_price = close_price
        if signal.action == SignalAction.BUY:
            signal.profit_pct = ((close_price - signal.entry_price) / signal.entry_price) * 100
        else:
            signal.profit_pct = ((signal.entry_price - close_price) / signal.entry_price) * 100

        if status:
            signal.status = status
        elif signal.profit_pct >= 0:
            signal.status = SignalStatus.CLOSED_TP
        else:
            signal.status = SignalStatus.CLOSED_SL

        await db.commit()
        await db.refresh(signal)
        await self.recalculate_provider_stats(db, signal.provider_id)

        logger.info(f"Closed signal {signal.id}: {signal.status.value}, profit={signal.profit_pct:.2f}%")
        return signal

    async def expire_old_signals(self, db: AsyncSession, max_age_hours: int = 168):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        result = await db.execute(
            select(Signal).where(and_(
                Signal.status == SignalStatus.ACTIVE,
                Signal.created_at < cutoff,
            ))
        )
        expired_signals = result.scalars().all()
        provider_ids = set()
        for signal in expired_signals:
            signal.status = SignalStatus.EXPIRED
            provider_ids.add(signal.provider_id)
        if expired_signals:
            await db.commit()
            logger.info(f"Expired {len(expired_signals)} old signals")
            for pid in provider_ids:
                await self.recalculate_provider_stats(db, pid)
        return len(expired_signals)

    # ─── Provider Statistics (Enhanced) ────────────────────────

    async def recalculate_provider_stats(
        self, db: AsyncSession, provider_id: uuid.UUID
    ) -> Provider | None:
        provider = await db.get(Provider, provider_id)
        if not provider:
            return None

        closed_statuses = [SignalStatus.CLOSED_TP, SignalStatus.CLOSED_SL, SignalStatus.CLOSED_MANUAL]

        # ── Basic counts ──
        tp_count = (await db.execute(
            select(func.count()).select_from(Signal).where(and_(
                Signal.provider_id == provider_id,
                Signal.status == SignalStatus.CLOSED_TP,
            ))
        )).scalar() or 0

        sl_count = (await db.execute(
            select(func.count()).select_from(Signal).where(and_(
                Signal.provider_id == provider_id,
                Signal.status == SignalStatus.CLOSED_SL,
            ))
        )).scalar() or 0

        total_closed = tp_count + sl_count
        provider.win_rate = tp_count / total_closed if total_closed > 0 else None

        # ── Average profit ──
        provider.avg_profit = (await db.execute(
            select(func.avg(Signal.profit_pct)).where(and_(
                Signal.provider_id == provider_id,
                Signal.status.in_(closed_statuses),
                Signal.profit_pct.isnot(None),
            ))
        )).scalar()

        # ── Get all closed profit values for advanced metrics ──
        profits_result = await db.execute(
            select(Signal.profit_pct).where(and_(
                Signal.provider_id == provider_id,
                Signal.status.in_(closed_statuses),
                Signal.profit_pct.isnot(None),
            )).order_by(Signal.created_at)
        )
        profits = [row[0] for row in profits_result.all()]

        if len(profits) >= 3:
            # ── Sharpe Ratio ──
            mean_return = sum(profits) / len(profits)
            stddev = math.sqrt(sum((p - mean_return) ** 2 for p in profits) / len(profits))
            if stddev > 0:
                provider.sharpe_ratio = round(
                    (mean_return - RISK_FREE_RATE_DAILY * 100) / stddev * math.sqrt(252), 2
                )
            else:
                provider.sharpe_ratio = 0.0 if mean_return <= 0 else 5.0  # Cap at 5

            # ── Profit Factor ──
            gross_profit = sum(p for p in profits if p > 0)
            gross_loss = abs(sum(p for p in profits if p < 0))
            if gross_loss > 0:
                provider.profit_factor = round(gross_profit / gross_loss, 2)
            else:
                provider.profit_factor = 10.0 if gross_profit > 0 else None

            # ── Max Drawdown ──
            cumulative = 0.0
            peak = 0.0
            max_dd = 0.0
            for p in profits:
                cumulative += p
                if cumulative > peak:
                    peak = cumulative
                dd = peak - cumulative
                if dd > max_dd:
                    max_dd = dd
            provider.max_drawdown = round(-max_dd, 2)  # Stored as negative
        else:
            provider.sharpe_ratio = None
            provider.profit_factor = None
            provider.max_drawdown = None

        # ── Consistency ──
        stddev_val = 0.0
        if len(profits) >= 2:
            mean_p = sum(profits) / len(profits)
            stddev_val = math.sqrt(sum((p - mean_p) ** 2 for p in profits) / len(profits))
        consistency_score = max(0.0, 1.0 - (stddev_val / 50.0))

        # ── Composite AI Score ──
        if provider.win_rate is not None and len(profits) >= 3:
            avg_p = provider.avg_profit or 0.0
            profit_score = max(0.0, min(1.0, (avg_p + 10) / 20))
            sharpe_score = max(0.0, min(1.0, (provider.sharpe_ratio or 0) / 3.0))
            pf_score = max(0.0, min(1.0, ((provider.profit_factor or 0) - 0.5) / 2.5))
            dd_score = max(0.0, min(1.0, 1.0 - abs(provider.max_drawdown or 0) / 40.0))

            provider.ai_score = round(
                provider.win_rate * PROVIDER_WEIGHTS["win_rate"]
                + consistency_score * PROVIDER_WEIGHTS["consistency"]
                + profit_score * PROVIDER_WEIGHTS["profit"]
                + sharpe_score * PROVIDER_WEIGHTS["sharpe"]
                + pf_score * PROVIDER_WEIGHTS["profit_factor"]
                + dd_score * PROVIDER_WEIGHTS["drawdown"],
                3,
            )
        elif provider.win_rate is not None:
            avg_p = provider.avg_profit or 0.0
            profit_score = max(0.0, min(1.0, (avg_p + 10) / 20))
            provider.ai_score = round(
                provider.win_rate * 0.5 + consistency_score * 0.25 + profit_score * 0.25, 3
            )
        else:
            provider.ai_score = None

        # ── Total signals ──
        provider.total_signals = (await db.execute(
            select(func.count()).select_from(Signal).where(Signal.provider_id == provider_id)
        )).scalar() or 0

        await db.commit()
        await db.refresh(provider)

        logger.info(
            f"Updated {provider.name}: wr={provider.win_rate}, sharpe={provider.sharpe_ratio}, "
            f"pf={provider.profit_factor}, dd={provider.max_drawdown}, score={provider.ai_score}"
        )
        return provider


ai_rating_service = AIRatingService()
