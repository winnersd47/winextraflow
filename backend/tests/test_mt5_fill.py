"""Execution feedback: what the terminal actually got, beside what was asked.

Every other number in the track record is computed. The entry is the level that
was published, the result is measured at the level that settled it — no spread,
no slippage, no rejected order. That makes every result an upper bound, and
until this existed nobody knew by how much.

`slippage_pct` is that gap, signed against the trader: positive means the fill
was worse than the request. On a forex scalping setup with a 0.12% target it
decides whether the setup is viable at all.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import PaperAccount, PaperTrade
from app.models.provider import Provider, ProviderSource
from app.models.signal import Signal, SignalAction, SignalStatus
from app.services.mt5_signals import record_fill


async def _signal(db: AsyncSession, ticker="EURUSD", entry=1.1180) -> Signal:
    p = Provider(name=f"mt5_{uuid.uuid4().hex[:6]}", source=ProviderSource.MANUAL)
    db.add(p)
    await db.flush()
    s = Signal(provider_id=p.id, ticker=ticker, action=SignalAction.BUY,
               entry_price=entry, take_profit=entry * 1.01,
               stop_loss=entry * 0.995, status=SignalStatus.ACTIVE,
               ai_confidence=0.86, raw_message="mt5")
    db.add(s)
    await db.flush()
    return s


@pytest.mark.asyncio
async def test_slippage_is_signed_against_the_trader(db: AsyncSession):
    """A buy filled higher is worse; a sell filled higher is better."""
    s = await _signal(db)
    await db.commit()

    worse = await record_fill(db, signal_id=str(s.id), ticker="EURUSD",
                              action="buy", requested_price=1.1180,
                              fill_price=1.1183, spread=0.00012, ticket=1)
    assert worse["recorded"]
    assert worse["slippage_pct"] > 0, "a buy filled higher must read as worse"

    better = await record_fill(db, signal_id=str(s.id), ticker="EURUSD",
                               action="sell", requested_price=1.1180,
                               fill_price=1.1183, spread=0.00012, ticket=2)
    assert better["slippage_pct"] < 0, "a sell filled higher must read as better"


@pytest.mark.asyncio
async def test_requested_price_is_preserved(db: AsyncSession):
    """Overwriting the entry with the fill would erase the very gap being
    measured."""
    s = await _signal(db)
    await db.commit()
    out = await record_fill(db, signal_id=str(s.id), ticker="EURUSD",
                            action="buy", requested_price=1.1180,
                            fill_price=1.1183, ticket=3)

    trade = (await db.execute(select(PaperTrade).where(
        PaperTrade.id == uuid.UUID(out["trade_id"])))).scalar_one()
    assert trade.entry_price == pytest.approx(1.1180)
    assert trade.fill_price == pytest.approx(1.1183)
    assert trade.entry_price != trade.fill_price


@pytest.mark.asyncio
async def test_one_row_per_ticket(db: AsyncSession):
    """The EA re-sends on reconnect; a duplicate would double-count a fill."""
    s = await _signal(db)
    await db.commit()
    first = await record_fill(db, signal_id=str(s.id), ticker="EURUSD",
                              action="buy", requested_price=1.1180,
                              fill_price=1.1183, ticket=99)
    again = await record_fill(db, signal_id=str(s.id), ticker="EURUSD",
                              action="buy", requested_price=1.1180,
                              fill_price=1.1183, ticket=99)
    assert first["recorded"] is True
    assert again["recorded"] is False
    assert again["trade_id"] == first["trade_id"]


@pytest.mark.asyncio
async def test_a_fill_without_a_price_is_refused(db: AsyncSession):
    out = await record_fill(db, signal_id=None, ticker="EURUSD", action="buy",
                            requested_price=1.1180, fill_price=0)
    assert out["recorded"] is False


@pytest.mark.asyncio
async def test_fills_stay_out_of_the_published_record(db: AsyncSession):
    """A demo fill is still a demo fill. It has its own scope so the platform's
    numbers never silently absorb it."""
    from app.services.paper_trading import (ensure_accounts, platform_accounts,
                                            platform_trades)

    await ensure_accounts(db)
    s = await _signal(db)
    await db.commit()
    out = await record_fill(db, signal_id=str(s.id), ticker="EURUSD",
                            action="buy", requested_price=1.1180,
                            fill_price=1.1183, ticket=7)

    plat_accs = {a.id for a in (await db.execute(
        platform_accounts(select(PaperAccount)))).scalars().all()}
    mt5 = (await db.execute(select(PaperAccount).where(
        PaperAccount.scope == "mt5_demo"))).scalars().first()
    assert mt5 is not None
    assert mt5.id not in plat_accs, "the MT5 account entered the published record"

    public = (await db.execute(platform_trades(select(PaperTrade)))).scalars().all()
    assert all(str(t.id) != out["trade_id"] for t in public)


@pytest.mark.asyncio
async def test_fill_without_a_known_signal_still_records(db: AsyncSession):
    """A bookkeeping gap must not cost the measurement."""
    out = await record_fill(db, signal_id=None, ticker="NOSIGNAL",
                            action="buy", requested_price=100.0,
                            fill_price=100.2, ticket=11)
    assert out["recorded"] is True
    assert out["slippage_pct"] == pytest.approx(0.2, abs=0.01)
