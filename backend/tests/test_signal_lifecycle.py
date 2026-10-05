"""How a signal leaves ACTIVE — and why it could previously only leave as a loss.

The monitor checked three things in this order: staleness, then TP, then SL.
Staleness asks "is the live price far from entry?", but reaching a target
*requires* the price to move far from entry. Measured across 150 stored signals,
93% have a target further away than their own staleness tolerance — US stocks
average a 25.1% target against a 7% limit, MOEX 44% against 6%.

So every signal on its way to a target crossed the staleness line first and was
written off, while a stop — which sits close to entry, inside the tolerance —
always closed normally. The platform's record of 0 wins in 11 closed trades was
produced by that ordering, not by the quality of the signals.

Three rules now hold, and each has a test here:
  * resolution is checked before staleness;
  * staleness only applies in the signal's first day, because it is a property
    of ingest (a message parsed out of old channel history), not of a signal
    that is simply moving;
  * something still writes off signals that never resolve, or nothing would ever
    leave ACTIVE — `expire_old_signals`, which existed but was never called.
"""

import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.provider import Provider, ProviderSource
from app.models.signal import Signal, SignalAction, SignalStatus
from app.services.ai_rating import ai_rating_service

MONITOR = Path(__file__).resolve().parents[1] / "scripts" / "monitor_signals.py"


def _code() -> str:
    """Monitor source with comments stripped — an earlier test in this project
    passed by matching its own explanatory comment rather than the code."""
    src = MONITOR.read_text(encoding="utf-8")
    return "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))


async def _provider(db: AsyncSession) -> Provider:
    p = Provider(name=f"life_{uuid.uuid4().hex[:6]}", source=ProviderSource.MANUAL)
    db.add(p)
    await db.flush()
    return p


# ═══════════════════════════════════════════════════════════════════════
# Order of checks
# ═══════════════════════════════════════════════════════════════════════

def test_levels_are_checked_before_staleness():
    """If this order flips back, winners silently stop being recorded."""
    code = _code()
    i_hit = code.index('hit = status["status"]')
    i_stale = code.index("STALE entry")
    assert i_hit < i_stale, \
        "staleness is evaluated before resolution — targets will expire again"


def test_stale_branch_is_guarded_by_non_resolution():
    """Source order does not protect this — the guard does.

    The staleness branch sits before the close branch in the file, which is fine
    as long as it can only run when neither level was reached.
    """
    code = _code()
    guard = 'if hit not in ("tp_hit", "sl_hit"):'
    assert guard in code, "the staleness branch is no longer gated on resolution"

    # Everything between the guard and the stale write-off must stay inside it.
    body = code[code.index(guard):code.index("STALE entry")]
    assert "SignalStatus.CLOSED" not in body, \
        "a close was moved inside the not-resolved branch"
    assert body.count("if hit in") == 0, \
        "the resolution branch was nested inside the staleness guard"


def test_staleness_is_bounded_to_the_ingest_window():
    """Applied on every pass, the rule kills a healthy signal for moving."""
    code = _code()
    assert "STALE_CHECK_WINDOW_HOURS" in code
    i_window = code.index("STALE_CHECK_WINDOW_HOURS", code.index("def "))
    i_expire = code.index("SignalStatus.EXPIRED")
    assert i_window < i_expire, \
        "the age window must gate the staleness branch, not follow it"


def test_monitor_writes_off_unresolved_signals():
    """With staleness bounded, nothing else would ever leave ACTIVE."""
    assert "expire_old_signals(db)" in _code(), \
        "the monitor must call the age-based write-off"


# ═══════════════════════════════════════════════════════════════════════
# The geometry that made the bug inevitable
# ═══════════════════════════════════════════════════════════════════════

def test_targets_are_routinely_beyond_the_staleness_tolerance():
    """Documents the measurement, so the interaction is not rediscovered later.

    A 25% target on an instrument with a 7% tolerance cannot be reached without
    tripping the rule. That is not an edge case here — it is 93% of the corpus.
    """
    from app.services.live_price import stale_tolerance

    for ticker, target_pct in (("AAPL", 25.1), ("SBER", 44.0)):
        tol = stale_tolerance(ticker) * 100
        assert target_pct > tol, (
            f"{ticker}: a {target_pct}% target sits beyond the {tol}% staleness "
            f"limit, so resolution must be checked first")


# ═══════════════════════════════════════════════════════════════════════
# Age-based expiry
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_expire_uses_the_configured_window(db: AsyncSession):
    """It hardcoded 168 and ignored the setting — and was never called."""
    prov = await _provider(db)
    old = Signal(provider_id=prov.id, ticker="TESTUSDT", action=SignalAction.BUY,
                 entry_price=100.0, take_profit=105.0, stop_loss=98.0,
                 status=SignalStatus.ACTIVE)
    db.add(old)
    await db.flush()
    old.created_at = (datetime.now(timezone.utc)
                      - timedelta(hours=settings.signal_expiry_hours + 24))
    await db.commit()

    n = await ai_rating_service.expire_old_signals(db)
    assert n >= 1
    await db.refresh(old)
    assert old.status == SignalStatus.EXPIRED


@pytest.mark.asyncio
async def test_expire_leaves_signals_inside_the_window(db: AsyncSession):
    """A 7-day window caught only 26% of resolutions; the median takes 6 bars."""
    prov = await _provider(db)
    fresh = Signal(provider_id=prov.id, ticker="TESTUSDT", action=SignalAction.BUY,
                   entry_price=100.0, take_profit=105.0, stop_loss=98.0,
                   status=SignalStatus.ACTIVE)
    db.add(fresh)
    await db.flush()
    # Older than the previous 168h limit, comfortably inside the new one.
    fresh.created_at = datetime.now(timezone.utc) - timedelta(hours=200)
    await db.commit()

    await ai_rating_service.expire_old_signals(db)
    await db.refresh(fresh)
    assert fresh.status == SignalStatus.ACTIVE, \
        "a signal eight days old was written off before it could resolve"


def test_expiry_window_covers_the_measured_resolution_time():
    """15 trading days is where the resolution curve flattens (49% of signals).
    Anything near the old 5-day window discards most outcomes."""
    trading_days = settings.signal_expiry_hours / 24 / 7 * 5
    assert trading_days >= 14, (
        f"{trading_days:.0f} trading days is below the measured median "
        f"resolution plus spread")
