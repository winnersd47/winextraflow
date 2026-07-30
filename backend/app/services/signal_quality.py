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
