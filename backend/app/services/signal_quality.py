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
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal import Signal, SignalAction, SignalStatus
from app.models.provider import Provider

logger = logging.getLogger(__name__)

# Thresholds
MIN_WEF_SCORE = 0.50
MIN_RR_RATIO = 1.5
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
            if rr < 1.0:
                result.fail(f"R:R ratio {rr:.1f} < 1.0 (risk exceeds reward)")
            elif rr > MAX_RR_RATIO or tp_pct > MAX_TP_PCT:
                # A +200% target against a -10% stop is a long-horizon analyst price
                # forecast, not a tradeable setup. Publishing it as a trade with
                # "R:R 1:22" is misleading.
                result.fail(
                    f"Unrealistic setup: target {tp_pct:.0f}%, R:R {rr:.1f} "
                    f"(analyst price forecast, not a trade signal)"
                )
            elif rr < MIN_RR_RATIO:
                result.warn(f"R:R ratio {rr:.1f} < {MIN_RR_RATIO} (marginal)")
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
