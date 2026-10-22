"""Repeating a losing direction is not a setup, and its win rate measures nothing.

Taken from a channel analysed on 2026-10-16 ("Блог трейдера с умом", 6821
messages). Its own session reports marked each win with the number of stake
doublings that preceded it: 216 won first try, 93 after one loss, 44 after two,
24 after three. All of them were summed into a claimed 83.9% win rate.

Counting a recovered series as a single win is what makes that number
meaningless. A level-3 sequence stakes 1+2+4+8 units to win 0.8, so one failure
at the next level erases roughly thirty of those wins. The rate can be high and
the account can still go to zero — which is the opposite of what a win rate is
supposed to tell a reader.

The platform must therefore recognise the shape, not just the arithmetic.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import Provider, ProviderSource
from app.models.signal import Signal, SignalAction, SignalStatus
from app.services.signal_quality import (MARTINGALE_FAIL_STREAK,
                                         MARTINGALE_WINDOW_HOURS,
                                         check_signal_quality)


async def _provider(db: AsyncSession) -> Provider:
    p = Provider(name=f"mg_{uuid.uuid4().hex[:6]}", source=ProviderSource.TELEGRAM)
    db.add(p)
    await db.flush()
    return p


async def _stopped_out(db: AsyncSession, prov: Provider, *, hours_ago: float,
                       ticker="EURUSD", action=SignalAction.BUY) -> Signal:
    s = Signal(provider_id=prov.id, ticker=ticker, action=action,
               entry_price=1.10, take_profit=1.12, stop_loss=1.09,
               status=SignalStatus.CLOSED_SL, profit_pct=-0.9,
               closed_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
               raw_message="stopped out")
    db.add(s)
    await db.flush()
    return s


async def _fresh(db: AsyncSession, prov: Provider, ticker="EURUSD",
                 action=SignalAction.BUY) -> Signal:
    s = Signal(provider_id=prov.id, ticker=ticker, action=action,
               entry_price=1.10, take_profit=1.12, stop_loss=1.09,
               status=SignalStatus.ACTIVE, ai_confidence=0.86,
               raw_message="next in the series", timeframe="1h")
    db.add(s)
    await db.flush()
    return s


@pytest.mark.asyncio
async def test_a_single_reentry_only_warns(db: AsyncSession):
    """Re-entering once after a stop is a judgement call, not a system."""
    prov = await _provider(db)
    await _stopped_out(db, prov, hours_ago=2)
    s = await _fresh(db, prov)
    await db.commit()

    r = await check_signal_quality(db, s, prov)
    assert r.passed, f"a single re-entry was rejected: {r.issues}"
    assert any("усреднение" in w for w in r.warnings), r.warnings


@pytest.mark.asyncio
async def test_a_streak_is_rejected(db: AsyncSession):
    prov = await _provider(db)
    for i in range(MARTINGALE_FAIL_STREAK):
        await _stopped_out(db, prov, hours_ago=2 + i)
    s = await _fresh(db, prov)
    await db.commit()

    r = await check_signal_quality(db, s, prov)
    assert not r.passed, "a doubling series passed the gate"
    assert any("мартингейл" in i.lower() for i in r.issues), r.issues


@pytest.mark.asyncio
async def test_old_stops_do_not_count(db: AsyncSession):
    """A re-entry days later is a different decision; three in one day is one
    decision made three times."""
    prov = await _provider(db)
    for i in range(MARTINGALE_FAIL_STREAK):
        await _stopped_out(db, prov, hours_ago=MARTINGALE_WINDOW_HOURS + 10 + i)
    s = await _fresh(db, prov)
    await db.commit()

    r = await check_signal_quality(db, s, prov)
    assert r.passed, f"stops outside the window were counted: {r.issues}"


@pytest.mark.asyncio
async def test_opposite_direction_is_not_a_series(db: AsyncSession):
    """Reversing after a stop is a reversal, not a double-down."""
    prov = await _provider(db)
    for i in range(MARTINGALE_FAIL_STREAK):
        await _stopped_out(db, prov, hours_ago=2 + i, action=SignalAction.BUY)
    s = await _fresh(db, prov, action=SignalAction.SELL)
    s.take_profit, s.stop_loss = 1.08, 1.11      # valid geometry for a sell
    await db.commit()

    r = await check_signal_quality(db, s, prov)
    assert not any("мартингейл" in i.lower() for i in r.issues), r.issues


@pytest.mark.asyncio
async def test_another_instrument_is_not_a_series(db: AsyncSession):
    prov = await _provider(db)
    for i in range(MARTINGALE_FAIL_STREAK):
        await _stopped_out(db, prov, hours_ago=2 + i, ticker="EURUSD")
    s = await _fresh(db, prov, ticker="GBPUSD")
    await db.commit()

    r = await check_signal_quality(db, s, prov)
    assert not any("мартингейл" in i.lower() for i in r.issues), r.issues


@pytest.mark.asyncio
async def test_another_provider_is_not_a_series(db: AsyncSession):
    """Two sources independently liking the same pair is agreement, not a series."""
    a, b = await _provider(db), await _provider(db)
    for i in range(MARTINGALE_FAIL_STREAK):
        await _stopped_out(db, a, hours_ago=2 + i)
    s = await _fresh(db, b)
    await db.commit()

    r = await check_signal_quality(db, s, b)
    assert not any("мартингейл" in i.lower() for i in r.issues), r.issues
