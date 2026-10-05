"""AI Rating service — signal scoring and provider statistics.

Nine weighted factors. Three read the signal itself (risk management, R:R,
completeness); six read aggregates of the provider that published it.

Missing data does not become 0.5
--------------------------------
Every factor used to return a neutral 0.5 when its input was absent. Measured on
the real database, that made the score almost constant: `win_rate`,
`sharpe_ratio`, `profit_factor` and `max_drawdown` were NULL for all 15 real
providers, so five factors returned exactly 0.5 for all 153 signals and 55% of the
weight carried no information. Together with `signal_frequency` — which never left
1.0 because the spam threshold is never reached — 63% of the score was a constant,
and the whole score took only 7 distinct values in a 46-71 band.

A neutral default is not neutral in effect: it drags every score toward the middle
and makes a well-evidenced 68 indistinguishable from a 68 built on nothing. So a
factor with no input now returns `None`, the weights are renormalized over the
factors that could actually be measured, and `coverage` reports how much of the
weight that was. A score of 68 at coverage 0.37 and a score of 68 at coverage 0.95
are different claims, and the payload now says which one it is.

`MIN_CLOSED_FOR_RATIOS` guards the ratios: a Sharpe over three trades is noise.
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
from app.services.signal_quality import not_excluded

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

# Closed trades a provider needs before Sharpe / Profit Factor / Max Drawdown are
# computed at all. The old floor was 3, which produced a Sharpe of -69.03 on four
# losing trades — a number with no meaning that still fed 15% of the score.
MIN_CLOSED_FOR_RATIOS = 10
# Closed trades before a win rate is trusted. The old gate read `total_signals`
# (every signal ever published) while the number it guarded came from closed ones,
# so a provider with 50 open signals and one closed loss scored "Poor win rate: 0%"
# on a sample of one.
MIN_CLOSED_FOR_WIN_RATE = 5

# Risk-free rate per trade. The previous code took a daily rate and annualized the
# result with sqrt(252), which assumes one observation per trading day; these are
# per-trade returns over holding periods from hours to weeks. Sharpe is therefore
# reported per trade, unannualized, and the score bands below are set for that
# scale — a per-trade Sharpe of 0.5 is strong.
RISK_FREE_PER_TRADE_PCT = 0.0


@dataclass
class RatingBreakdown:
    """Detailed breakdown of a signal's AI rating.

    `scores` holds None for a factor whose input was unavailable. `coverage` is the
    share of the total weight that could be measured, so the caller can tell a
    well-evidenced score from a thin one.
    """

    scores: dict[str, float | None] = None
    reasons: dict[str, str] = None
    final_confidence: float = 0.0
    coverage: float = 0.0
    reasoning: str = ""

    def __post_init__(self):
        if self.scores is None:
            self.scores = {}
        if self.reasons is None:
            self.reasons = {}

    def available(self) -> dict[str, float]:
        """Only the factors that were actually measured."""
        return {k: v for k, v in self.scores.items()
                if k in WEIGHTS and v is not None}

    def to_dict(self) -> dict:
        avail = self.available()
        total_w = sum(WEIGHTS[k] for k in avail) or 1.0
        return {
            "final_confidence": round(self.final_confidence, 3),
            "coverage": round(self.coverage, 3),
            "measured_factors": len(avail),
            "total_factors": len(WEIGHTS),
            "reasoning": self.reasoning,
            "factors": {
                key: {
                    # Kept numeric even when unmeasured: the UI multiplies this by
                    # 100 for a bar width. `available` is the flag to branch on.
                    "score": round(self.scores.get(key) or 0.0, 3),
                    "available": self.scores.get(key) is not None,
                    "weight": WEIGHTS.get(key, 0),
                    # What this factor really contributed after renormalization.
                    "effective_weight": (round(WEIGHTS[key] / total_w, 3)
                                         if key in avail else 0.0),
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

    def _score_risk_reward(self, signal: Signal) -> tuple[float | None, str]:
        if signal.take_profit is None or signal.stop_loss is None:
            # Not a 0.5. Missing levels are already penalised by risk_management
            # and completeness; scoring them again here as "average" both
            # double-counted the defect and hid that nothing was measured.
            return None, "R:R не рассчитан — нет TP или SL"
        entry = signal.entry_price
        if entry <= 0:
            return 0.0, "Invalid entry price"

        # Direction first, and without abs(). Taking absolute values made an
        # inverted pair invisible: a BUY with the target BELOW entry and the stop
        # ABOVE it yielded reward == risk == 5000, an R:R of exactly 1.0, and was
        # scored as an ordinary weak trade. It is not a weak trade — it is a
        # misread direction, and it should not be rated as tradable at all.
        if signal.action == SignalAction.BUY:
            reward = signal.take_profit - entry
            risk = entry - signal.stop_loss
        else:
            reward = entry - signal.take_profit
            risk = signal.stop_loss - entry

        if reward <= 0 and risk <= 0:
            return 0.05, ("Оба уровня не с той стороны входа — направление "
                          "разобрано неверно")
        if reward <= 0:
            return 0.05, (f"Тейк не с той стороны входа для "
                          f"{signal.action.value} — не сделка")
        if risk <= 0:
            return 0.05, (f"Стоп не с той стороны входа для "
                          f"{signal.action.value} — риск не определён")

        rr = reward / risk
        # Not monotonic, and that is the correction. "More R:R is better" was the
        # score's heaviest live factor and it made the score anti-predictive.
        #
        # Measured by scripts/eval_wef.py, replaying 80 stored signals against
        # real candles (cohort with source-given targets, n=55):
        #
        #     WEF band   avg R:R   avg realised P&L
        #     0-79           1.2      -0.41%
        #     80-85          1.8      -2.77%
        #     86-91          2.3      -2.66%
        #     92-100         7.1      -7.04%
        #
        # R:R rose with the score and expectancy fell with it, monotonically —
        # correlation of score with outcome was -0.35 there and -0.73 on the
        # cohort where the source stated both levels.
        #
        # The reason is geometric, not statistical, so it does not depend on this
        # sample: with a 2x ATR stop, an R:R of 7 puts the target 14 ATR away, and
        # signal_geometry.py already measures how rarely that is reached before the
        # stop. In this data a high ratio does not mark a good trade — it marks a
        # distant analyst target paired with our own tight stop, which is the
        # mismatch MAX_RR_RATIO was added to bound. Rewarding it was backwards.
        #
        # So the score now peaks where the geometry is actually attainable and
        # falls off above it, instead of climbing all the way to the cap.
        if rr < 1.0:
            return 0.15, f"R:R {rr:.1f}:1 — риск превышает прибыль"
        if rr < 1.5:
            return 0.40, f"R:R {rr:.1f}:1 — низкое"
        if rr < 2.0:
            return 0.70, f"R:R {rr:.1f}:1 — приемлемое"
        if rr <= 3.0:
            return 1.00, f"R:R {rr:.1f}:1 — достижимая геометрия"
        if rr <= 5.0:
            return 0.55, (f"R:R {rr:.1f}:1 — цель далеко для такого стопа, "
                          f"вероятность дойти падает")
        return 0.20, (f"R:R {rr:.1f}:1 — цель и стоп не согласованы "
                      f"(вероятно дальняя цель источника с нашим стопом)")

    async def _score_provider_history(
        self, db: AsyncSession, provider_id: uuid.UUID
    ) -> tuple[float | None, str]:
        provider = await db.get(Provider, provider_id)
        if not provider:
            return None, "Провайдер не найден"
        wr = provider.win_rate
        if wr is None:
            return None, "Нет закрытых сделок — win rate не измерен"
        # Gate on the sample the win rate is actually built from. The old gate
        # read total_signals, so one closed loss out of 50 published signals
        # became "Poor win rate: 0%" and cost the signal 15% of its score.
        closed = await self._closed_count(db, provider_id)
        if closed < MIN_CLOSED_FOR_WIN_RATE:
            return None, (f"Win rate на выборке {closed} — нужно "
                          f"{MIN_CLOSED_FOR_WIN_RATE}")
        if wr >= 0.7:
            return 1.0, f"Excellent win rate: {wr:.0%}"
        if wr >= 0.55:
            return 0.7, f"Good win rate: {wr:.0%}"
        if wr >= 0.4:
            return 0.4, f"Average win rate: {wr:.0%}"
        return 0.15, f"Poor win rate: {wr:.0%}"

    async def _score_sharpe_ratio(
        self, db: AsyncSession, provider_id: uuid.UUID
    ) -> tuple[float | None, str]:
        """Score the provider's per-trade Sharpe.

        Bands are for an unannualized per-trade figure — see
        RISK_FREE_PER_TRADE_PCT for why the sqrt(252) annualization was removed.
        """
        provider = await db.get(Provider, provider_id)
        if not provider or provider.sharpe_ratio is None:
            return None, (f"Шарп не рассчитан — нужно "
                          f"{MIN_CLOSED_FOR_RATIOS} закрытых сделок")
        sr = provider.sharpe_ratio
        if sr >= 0.5:
            return 1.0, f"Отличный Шарп на сделку: {sr:.2f}"
        if sr >= 0.3:
            return 0.75, f"Хороший Шарп на сделку: {sr:.2f}"
        if sr >= 0.15:
            return 0.5, f"Средний Шарп на сделку: {sr:.2f}"
        if sr >= 0:
            return 0.25, f"Низкий Шарп на сделку: {sr:.2f}"
        return 0.1, f"Отрицательный Шарп: {sr:.2f}"

    async def _score_profit_factor(
        self, db: AsyncSession, provider_id: uuid.UUID
    ) -> tuple[float | None, str]:
        """Score based on provider's Profit Factor (gross profit / gross loss)."""
        provider = await db.get(Provider, provider_id)
        if not provider or provider.profit_factor is None:
            return None, (f"Профит-фактор не рассчитан — нужно "
                          f"{MIN_CLOSED_FOR_RATIOS} закрытых сделок")
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
    ) -> tuple[float | None, str]:
        """Score based on provider's maximum drawdown (lower is better)."""
        provider = await db.get(Provider, provider_id)
        if not provider or provider.max_drawdown is None:
            return None, (f"Просадка не рассчитана — нужно "
                          f"{MIN_CLOSED_FOR_RATIOS} закрытых сделок")
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

    async def _closed_count(self, db: AsyncSession, provider_id: uuid.UUID) -> int:
        """Closed signals for this provider — the sample its win rate rests on."""
        return (await db.execute(
            select(func.count()).select_from(Signal).where(and_(
                Signal.provider_id == provider_id,
                Signal.status.in_([SignalStatus.CLOSED_TP, SignalStatus.CLOSED_SL]),
                not_excluded(),
            ))
        )).scalar() or 0

    async def _score_time_decay(
        self, db: AsyncSession, provider_id: uuid.UUID
    ) -> tuple[float | None, str]:
        """Score recent performance higher than old performance.

        Looks at the last 30 days of closed signals vs prior history.
        """
        now = datetime.now(timezone.utc)
        thirty_days_ago = now - timedelta(days=30)
        closed_statuses = [SignalStatus.CLOSED_TP, SignalStatus.CLOSED_SL]

        # Recent win rate (last 30 days), by when the trade settled.
        # This used to filter on `updated_at`, i.e. the last time any column was
        # written. Editing an old row — a P&L backfill, a re-rating — moved it
        # into the window, so the "last 30 days" cohort was really "rows touched
        # in the last 30 days". Signals closed before `closed_at` existed have it
        # NULL and are simply not counted.
        recent_tp = (await db.execute(
            select(func.count()).select_from(Signal).where(and_(
                Signal.provider_id == provider_id,
                Signal.status == SignalStatus.CLOSED_TP,
                Signal.closed_at.isnot(None),
                not_excluded(),
                Signal.closed_at >= thirty_days_ago,
            ))
        )).scalar() or 0

        recent_sl = (await db.execute(
            select(func.count()).select_from(Signal).where(and_(
                Signal.provider_id == provider_id,
                Signal.status == SignalStatus.CLOSED_SL,
                Signal.closed_at.isnot(None),
                not_excluded(),
                Signal.closed_at >= thirty_days_ago,
            ))
        )).scalar() or 0

        recent_total = recent_tp + recent_sl
        if recent_total < 3:
            return None, f"За 30 дней закрыто {recent_total} — тренд не измерить"

        recent_wr = recent_tp / recent_total

        # Needs a baseline to compare against, and the baseline must be measured
        # too — comparing a recent rate to a hardcoded 0.5 reported a trend that
        # was really just "the recent rate is above or below one half".
        provider = await db.get(Provider, provider_id)
        overall_wr = provider.win_rate if provider else None
        if overall_wr is None:
            return None, "Нет общего win rate для сравнения"

        if recent_wr > overall_wr + 0.1:
            return 0.9, f"Рост: за 30 дней {recent_wr:.0%} > общий {overall_wr:.0%}"
        if recent_wr >= overall_wr - 0.05:
            return 0.6, f"Стабильно: за 30 дней {recent_wr:.0%} ≈ общий {overall_wr:.0%}"
        return 0.2, f"Спад: за 30 дней {recent_wr:.0%} < общий {overall_wr:.0%}"

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

        # A signal without a usable entry price cannot be evaluated at all: every
        # level is relative to it, so R:R, position size and the geometry check
        # are all undefined. Previously only `_score_risk_reward` noticed, and
        # only when both levels were present — so a broken row with no stop
        # skipped the check entirely and still came out mid-range.
        if not signal.entry_price or signal.entry_price <= 0:
            breakdown.scores = {k: None for k in WEIGHTS}
            breakdown.reasons = {k: "Нет корректной цены входа" for k in WEIGHTS}
            breakdown.coverage = 0.0
            breakdown.final_confidence = 0.0
            breakdown.reasoning = ("Сигнал не оценивается: цена входа "
                                   "отсутствует или некорректна")
            return breakdown

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

        # Weighted sum over the factors that were measurable, renormalized so the
        # weights of the rest are not silently redistributed as a middling 0.5.
        avail = breakdown.available()
        total_w = sum(WEIGHTS[k] for k in avail)
        breakdown.coverage = total_w / sum(WEIGHTS.values())

        if total_w > 0:
            confidence = sum(avail[k] * WEIGHTS[k] for k in avail) / total_w
            breakdown.final_confidence = max(0.0, min(1.0, confidence))
        else:
            # Nothing at all was measurable. 0.0 would read as "terrible signal"
            # rather than "no evidence", so the caller must branch on coverage.
            breakdown.final_confidence = 0.0

        # Build reasoning
        strong = [k.replace("_", " ") for k, s in avail.items() if s >= 0.8]
        weak = [k.replace("_", " ") for k, s in avail.items() if s <= 0.3]
        missing = [k for k in WEIGHTS if breakdown.scores.get(k) is None]

        parts = []
        if strong:
            parts.append(f"Сильные: {', '.join(strong)}")
        if weak:
            parts.append(f"Слабые: {', '.join(weak)}")
        if missing:
            parts.append(f"Не измерено ({len(missing)} из {len(WEIGHTS)}): "
                         f"{', '.join(m.replace('_', ' ') for m in missing)}")
        if not strong and not weak:
            parts.insert(0, "Среднее качество по измеримым факторам")
        breakdown.reasoning = ". ".join(parts)

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
        signal.closed_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(signal)
        await self.recalculate_provider_stats(db, signal.provider_id)

        logger.info(f"Closed signal {signal.id}: {signal.status.value}, profit={signal.profit_pct:.2f}%")
        return signal

    async def expire_old_signals(self, db: AsyncSession,
                                 max_age_hours: int | None = None):
        """Write off signals that never reached a level.

        `max_age_hours` defaults to `settings.signal_expiry_hours`. It used to
        hardcode 168 and ignore the setting — which was moot, because nothing
        called this function at all: signals only ever left ACTIVE by hitting a
        stop or by being marked stale. The monitor calls it now.
        """
        from app.config import settings
        if max_age_hours is None:
            max_age_hours = settings.signal_expiry_hours
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
                not_excluded(),
            ))
        )).scalar() or 0

        sl_count = (await db.execute(
            select(func.count()).select_from(Signal).where(and_(
                Signal.provider_id == provider_id,
                Signal.status == SignalStatus.CLOSED_SL,
                not_excluded(),
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
                not_excluded(),
            ))
        )).scalar()

        # ── Get all closed profit values for advanced metrics ──
        profits_result = await db.execute(
            select(Signal.profit_pct).where(and_(
                Signal.provider_id == provider_id,
                Signal.status.in_(closed_statuses),
                Signal.profit_pct.isnot(None),
                not_excluded(),
            )).order_by(Signal.created_at)
        )
        profits = [row[0] for row in profits_result.all()]

        if len(profits) >= MIN_CLOSED_FOR_RATIOS:
            # ── Sharpe Ratio, per trade ──
            # The previous version multiplied by sqrt(252), which annualizes daily
            # observations. These are per-trade returns over holding periods from
            # hours to weeks, so the factor was meaningless: four losing trades
            # produced -69.03, and that number fed 15% of every signal's score.
            mean_return = sum(profits) / len(profits)
            stddev = math.sqrt(sum((p - mean_return) ** 2 for p in profits) / len(profits))
            if stddev > 0:
                provider.sharpe_ratio = round(
                    (mean_return - RISK_FREE_PER_TRADE_PCT) / stddev, 2
                )
            else:
                # Zero dispersion: every trade returned the same. Not skill.
                provider.sharpe_ratio = 0.0

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
        if provider.win_rate is not None and len(profits) >= MIN_CLOSED_FOR_RATIOS:
            avg_p = provider.avg_profit or 0.0
            profit_score = max(0.0, min(1.0, (avg_p + 10) / 20))
            # Divisor matches the per-trade Sharpe scale: 0.5 per trade is strong,
            # so it maps to a full score. The old /3.0 was for the annualized
            # figure that no longer exists.
            sharpe_score = max(0.0, min(1.0, (provider.sharpe_ratio or 0) / 0.5))
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
