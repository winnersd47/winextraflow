"""Signal Quality Gate — auto-filter signals before publication.

Rules:
1. TP and SL must be present
2. R:R ratio >= 1.5
3. WEF Score >= 50%
4. Provider Win Rate >= 55% (if provider has history)
5. No duplicate active signal for same ticker
6. Price > 0

Signals failing the gate are marked as "hidden" — not shown in public feed
but still stored in DB for analytics.
"""

import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal import Signal, SignalAction, SignalStatus
from app.models.provider import Provider

logger = logging.getLogger(__name__)

# Thresholds
MIN_WEF_SCORE = 0.50

# Geometry is judged by the win rate it demands, not by a bare ratio.
#
# `MIN_RR_RATIO = 1.5` rejected everything below it and said nothing about what
# lay above. Both halves of that were wrong. Replaying 80 stored signals against
# real candles showed the HIGHEST ratios performing worst — the 92-100 score band
# averaged R:R 7.1 and -7.04% per trade, against -0.41% for the nearest targets —
# so the flat floor was blind to the end that actually cost money. And it
# excluded an entire trading style on a ratio alone: the forex channels found by
# scripts/find_forex_sources.py all sit at R:R 0.15-0.50.
#
# The breakeven share, risk / (reward + risk), says the thing a reader can judge.
# R:R 0.36 is opaque; "needs 73% of trades to win" is a claim you can weigh
# against a measured win rate — and the platform's own is 0 of 10.
#
# 70% is where the demand stops being a setup and becomes a bet: three wrong
# trades in ten wipe out the other seven. 55% is where it is worth saying out
# loud. Below 20% the target sits four or more stops away, which is the band the
# replay showed losing most.
BREAKEVEN_REJECT_PCT = 70.0
BREAKEVEN_WARN_PCT = 55.0
BREAKEVEN_IMPLAUSIBLE_PCT = 20.0
MIN_RR_RATIO = 1.5          # kept: still read by reporting code and older tests

# Martingale detection. A repeat of the same direction on the same instrument
# after it stopped out is averaging down; several in a row is a doubling series.
# The window is short because a legitimate re-entry days later is a different
# decision, while three in one day is one decision made three times.
MARTINGALE_WINDOW_HOURS = 24
MARTINGALE_FAIL_STREAK = 3
# Upper bounds: beyond these the "signal" is a long-horizon analyst price target
# (e.g. +226% in a year vs a -10% stop = R:R 1:22), not an actionable trade setup.
MAX_RR_RATIO = 10.0
MAX_TP_PCT = 60.0
MIN_PROVIDER_WIN_RATE = 0.55
MIN_PROVIDER_SIGNALS = 5  # need at least N closed signals to judge

# Seed/demo rows share the tables with real signals. Anything customer-facing —
# the public track record, the TP/SL monitor that posts results to VIP — must
# exclude them, or generated numbers get published as trading history.
SEED_MARKERS = ("auto-generated", "demo signal", "test signal")


# Tickers used by load/stress tests. 32 STRESST rows reached the paper accounts
# because they look like ordinary signals — the marker check only reads the message.
TEST_TICKERS = {"TESTTICK", "STRESST", "TESTBTC", "FAKETICK"}


def is_seed_signal(signal: Signal) -> bool:
    """True if this row came from seed_data, a demo fixture or a test, not a source."""
    if (signal.ticker or "").upper() in TEST_TICKERS:
        return True
    raw = (signal.raw_message or "").lower()
    return any(raw.startswith(m) or m in raw[:40] for m in SEED_MARKERS)


def not_excluded():
    """SQL condition: rows that may count toward the measured record.

    Pair it with the seed filter. `is_seed_signal` catches fixtures and test
    tickers by inspecting the row; this catches rows a human ruled out after the
    fact — currently only exact duplicates of another closed signal, which
    double-counted one outcome in the win rate.
    """
    return Signal.excluded_reason.is_(None)


def is_countable(signal: Signal) -> bool:
    """In-Python equivalent of `not_excluded()` plus the seed check."""
    return signal.excluded_reason is None and not is_seed_signal(signal)


async def recent_wef_percentile(db: AsyncSession, q: float = 0.75, limit: int = 200) -> int | None:
    """The q-th percentile WEF score over the last `limit` real scored signals.

    The score's usable range turned out to be narrow — real signals sit between
    roughly 43 and 71 — so a fixed "strong signal" cut-off is arbitrary: at 70 only
    6% of signals ever qualified. A percentile keeps the VIP-exclusive share at the
    intended fraction as the scoring distribution shifts.
    """
    rows = (await db.execute(
        select(Signal.ai_confidence, Signal.raw_message)
        .where(Signal.ai_confidence.isnot(None))
        .order_by(Signal.created_at.desc())
        .limit(limit * 3)          # room to drop seed rows and still fill the window
    )).all()
    scores = sorted(
        round(conf * 100) for conf, raw in rows
        if conf and not any((raw or "").lower().startswith(m) for m in SEED_MARKERS)
    )[-limit:] if rows else []
    if len(scores) < 20:           # too few to speak of a distribution
        return None
    return scores[min(len(scores) - 1, int(len(scores) * q))]


class QualityResult:
    def __init__(self):
        self.passed = True
        self.score = 100  # quality score 0-100
        self.issues: list[str] = []
        self.warnings: list[str] = []
        self.tier = "excellent"  # excellent, good, average, weak, rejected

    def fail(self, reason: str):
        self.passed = False
        self.issues.append(reason)
        self.score -= 25

    def warn(self, reason: str):
        self.warnings.append(reason)
        self.score -= 10

    def finalize(self):
        self.score = max(0, self.score)
        if not self.passed:
            self.tier = "rejected"
        elif self.score >= 80:
            self.tier = "excellent"
        elif self.score >= 60:
            self.tier = "good"
        elif self.score >= 40:
            self.tier = "average"
        else:
            self.tier = "weak"


async def check_signal_quality(
    db: AsyncSession,
    signal: Signal,
    provider: Provider | None = None,
) -> QualityResult:
    """Run all quality checks on a signal. Returns QualityResult."""
    result = QualityResult()

    # 1. TP and SL present
    if not signal.take_profit:
        result.fail("Missing take profit (TP)")
    if not signal.stop_loss:
        result.fail("Missing stop loss (SL)")

    # 2. R:R ratio
    if signal.take_profit and signal.stop_loss and signal.entry_price > 0:
        if signal.action == SignalAction.BUY:
            reward = abs(signal.take_profit - signal.entry_price)
            risk = abs(signal.entry_price - signal.stop_loss)
        else:
            reward = abs(signal.entry_price - signal.take_profit)
            risk = abs(signal.stop_loss - signal.entry_price)

        if risk > 0:
            rr = reward / risk
            tp_pct = reward / signal.entry_price * 100 if signal.entry_price else 0
            # The share of trades that must win for this geometry to break even.
            # It is the same arithmetic signal_geometry.breakeven_hit_rate does,
            # and it says what a bare ratio cannot: "R:R 0.36" is opaque, "needs
            # 73% of trades to win" is a claim a reader can judge.
            breakeven = risk / (reward + risk) * 100

            if rr > MAX_RR_RATIO or tp_pct > MAX_TP_PCT:
                # A +200% target against a -10% stop is a long-horizon analyst price
                # forecast, not a tradeable setup. Publishing it as a trade with
                # "R:R 1:22" is misleading.
                result.fail(
                    f"Unrealistic setup: target {tp_pct:.0f}%, R:R {rr:.1f} "
                    f"(analyst price forecast, not a trade signal)"
                )
            elif breakeven > BREAKEVEN_REJECT_PCT:
                result.fail(
                    f"Нужно {breakeven:.0f}% побед просто чтобы не терять "
                    f"(цель {tp_pct:.2f}%, стоп {risk / signal.entry_price * 100:.2f}%) "
                    f"— выше {BREAKEVEN_REJECT_PCT:.0f}% это не сетап, а ставка"
                )
            elif breakeven > BREAKEVEN_WARN_PCT:
                result.warn(
                    f"Нужно {breakeven:.0f}% побед для безубытка "
                    f"(R:R {rr:.1f}) — требование к точности высокое"
                )
            elif breakeven < BREAKEVEN_IMPLAUSIBLE_PCT:
                # The other end, which the flat R:R floor never looked at. A
                # breakeven of 10% sounds generous, but it means the target sits
                # nine stops away — and replaying 80 stored signals showed that
                # band losing 7.04% per trade while the nearest targets lost
                # 0.41%. An easy-looking breakeven that the market never reaches
                # is worse than a demanding one it does.
                result.warn(
                    f"Безубыток всего {breakeven:.0f}% (R:R {rr:.1f}) — цель "
                    f"далеко для такого стопа, по замерам такая геометрия "
                    f"доходит реже, чем выглядит"
                )
        else:
            result.warn("Risk = 0 (SL equals entry)")

    # 3. WEF Score
    if signal.ai_confidence is not None:
        if signal.ai_confidence < MIN_WEF_SCORE:
            result.fail(f"WEF Score {signal.ai_confidence:.0%} < {MIN_WEF_SCORE:.0%}")
        elif signal.ai_confidence < 0.6:
            result.warn(f"WEF Score {signal.ai_confidence:.0%} is average")

    # 4. Provider Win Rate
    if provider and provider.win_rate is not None:
        if provider.total_signals >= MIN_PROVIDER_SIGNALS:
            if provider.win_rate < MIN_PROVIDER_WIN_RATE:
                result.warn(f"Provider WR {provider.win_rate:.0%} < {MIN_PROVIDER_WIN_RATE:.0%}")
        else:
            result.warn(f"Provider has only {provider.total_signals} signals (need {MIN_PROVIDER_SIGNALS}+ for reliable WR)")

    # 5. No duplicate active signal for same ticker
    existing = (await db.execute(
        select(Signal).where(
            Signal.ticker == signal.ticker,
            Signal.status == SignalStatus.ACTIVE,
            Signal.action == signal.action,
            Signal.id != signal.id,
        ).limit(1)
    )).scalar_one_or_none()
    if existing:
        result.warn(f"Duplicate active {signal.action.value} signal for {signal.ticker}")

    # 5b. Martingale / averaging down.
    #
    # A repeat of the same direction on the same instrument shortly after that
    # instrument stopped out is how a losing run gets dressed up as a win rate.
    # Seen in a channel analysed on 2026-10-16: its own reports marked each win
    # with the number of stake doublings that preceded it — 93 wins after one
    # loss, 44 after two, 24 after three — and summed them into a claimed 83.9%.
    # Counting a recovered series as one win makes the rate meaningless: a
    # level-3 sequence stakes 15 units to win 0.8, so a single failure at the
    # next level erases thirty of those wins.
    #
    # One repeat can be a legitimate re-entry, so that only warns. Three in a
    # row is a system, and the platform should not relay it as a setup.
    if signal.provider_id and signal.entry_price:
        recent_stops = (await db.execute(
            select(Signal).where(
                Signal.provider_id == signal.provider_id,
                Signal.ticker == signal.ticker,
                Signal.action == signal.action,
                Signal.status == SignalStatus.CLOSED_SL,
                Signal.id != signal.id,
                Signal.closed_at.isnot(None),
                Signal.closed_at >= datetime.now(timezone.utc)
                - timedelta(hours=MARTINGALE_WINDOW_HOURS),
            ).order_by(Signal.closed_at.desc()).limit(MARTINGALE_FAIL_STREAK)
        )).scalars().all()

        streak = len(recent_stops)
        if streak >= MARTINGALE_FAIL_STREAK:
            result.fail(
                f"Похоже на мартингейл: {streak}-й подряд {signal.action.value} "
                f"по {signal.ticker} после стопов за {MARTINGALE_WINDOW_HOURS} ч. "
                f"Серия доливок — не сетап, и её win rate ничего не измеряет"
            )
        elif streak >= 1:
            result.warn(
                f"Повтор {signal.action.value} по {signal.ticker} после "
                f"{streak} стоп{'а' if streak > 1 else 'а'} за "
                f"{MARTINGALE_WINDOW_HOURS} ч — проверьте, не усреднение ли это"
            )

    # 5c. Scheduled event inside the expected holding period.
    #
    # Warning only, deliberately. Nothing in this project has measured that a
    # rate decision or a CPI print changes a signal's outcome, and the same
    # session that added this refused to gate on "room to target" at r = -0.129.
    # Rejecting on an idea with no measurement at all would be worse. The reader
    # gets the fact; the decision stays theirs.
    try:
        from app.services.econ_calendar import (EVENT_HORIZON_DAYS,
                                                events_during_signal)
        events = await events_during_signal(signal.ticker)
        if events:
            nearest = events[0]
            # A multi-day event names its span. FRED lists one FOMC meeting as
            # four consecutive release dates, and "19 October (+3 more)" would
            # read as four separate risks.
            when = nearest.get("date")
            if nearest.get("date_end") and nearest["date_end"] != when:
                when = f"{when}–{nearest['date_end']}"
            extra = (f" (+{len(events) - 1} ещё)" if len(events) > 1 else "")
            result.warn(
                f"В ближайшие {EVENT_HORIZON_DAYS} дн. — "
                f"{nearest.get('title')} {when}{extra}. "
                f"Сделка может идти через публикацию"
            )
    except Exception as e:
        # A calendar outage must never block a signal.
        logger.debug(f"Event check skipped for {signal.ticker}: {e}")

    # 6. Price validation
    if signal.entry_price <= 0:
        result.fail("Entry price must be > 0")

    # 7. TP/SL direction check
    if signal.take_profit and signal.stop_loss and signal.entry_price > 0:
        if signal.action == SignalAction.BUY:
            if signal.take_profit <= signal.entry_price:
                result.fail("BUY signal: TP must be above entry price")
            if signal.stop_loss >= signal.entry_price:
                result.fail("BUY signal: SL must be below entry price")
        else:
            if signal.take_profit >= signal.entry_price:
                result.fail("SELL signal: TP must be below entry price")
            if signal.stop_loss <= signal.entry_price:
                result.fail("SELL signal: SL must be above entry price")

    result.finalize()
    return result


def format_quality_report(result: QualityResult) -> dict:
    """Format quality result for API response."""
    return {
        "passed": result.passed,
        "tier": result.tier,
        "score": result.score,
        "issues": result.issues,
        "warnings": result.warnings,
        "publish_recommendation": (
            "publish_all" if result.tier == "excellent"
            else "publish_signals" if result.tier in ("good", "average")
            else "do_not_publish" if result.tier == "rejected"
            else "publish_with_warning"
        ),
    }
