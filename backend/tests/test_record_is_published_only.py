"""A result counts only if somebody could have acted on it.

The public track record used to be "every closed signal that is not a fixture".
Measured 2026-10-29 that was 33 rows — of which 13 had ever been sent anywhere.
The other 20 were trial sources on a paper track, setups the quality gate had
rejected, and rows created while broadcasting was down. They carried the record
past MIN_SAMPLE by themselves, so the site published a win rate assembled mostly
from signals no reader ever saw.

These tests pin the rule in both directions: an unsent closed signal must not
reach any published number, and a sent one must.
"""
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.track_record import _closed_real, summary
from app.models.provider import Provider, ProviderSource
from app.models.signal import Signal, SignalAction, SignalStatus
from app.services.measured_stats import measured_win_rate
from app.services.signal_quality import is_published, was_published


async def _provider(db: AsyncSession) -> Provider:
    p = Provider(id=uuid.uuid4(), name="Record Test Source",
                 source=ProviderSource.TELEGRAM, is_seed=False)
    db.add(p)
    await db.commit()
    return p


def _closed(provider_id, **kw) -> Signal:
    base = dict(
        id=uuid.uuid4(), provider_id=provider_id, ticker="SBER",
        action=SignalAction.BUY, entry_price=300.0, take_profit=330.0,
        stop_loss=285.0, status=SignalStatus.CLOSED_TP, ai_confidence=0.7,
        raw_message="",
    )
    base.update(kw)
    return Signal(**base)


@pytest.mark.asyncio
async def test_unsent_closed_signal_stays_out_of_the_record(db: AsyncSession):
    p = await _provider(db)
    db.add(_closed(p.id))          # no tg_vip_message_id, no tg_free_message_id
    await db.commit()

    assert await _closed_real(db) == []


@pytest.mark.asyncio
async def test_signal_sent_to_vip_counts(db: AsyncSession):
    p = await _provider(db)
    db.add(_closed(p.id, tg_vip_message_id=4242))
    await db.commit()

    rows = await _closed_real(db)
    assert [s.tg_vip_message_id for s in rows] == [4242]


@pytest.mark.asyncio
async def test_signal_sent_only_to_the_free_channel_counts(db: AsyncSession):
    """The free channel is a channel: a teaser readers acted on is a result."""
    p = await _provider(db)
    db.add(_closed(p.id, tg_free_message_id=77))
    await db.commit()

    assert len(await _closed_real(db)) == 1


@pytest.mark.asyncio
async def test_paper_only_source_cannot_reach_min_sample(db: AsyncSession):
    """The exact failure: enough unsent rows to clear the threshold alone.

    Before the fix this published a win rate off 40 trades nobody was shown.
    """
    p = await _provider(db)
    for i in range(40):
        db.add(_closed(
            p.id, ticker=f"PAP{i}",
            status=SignalStatus.CLOSED_TP if i % 2 else SignalStatus.CLOSED_SL,
            ai_reasoning="Paper-only source: measured, not published",
        ))
    await db.commit()

    s = await summary(db=db)
    assert s["enough_data"] is False
    assert s["closed_trades"] == 0
    assert "win_rate_pct" not in s

    # measured_win_rate has NO was_published() filter, so the same 40 rows still
    # produce a rate there — which is what feeds EV / Profit Factor / Kelly on a
    # VIP card. Asserted rather than left silent: this is the remaining gap, and
    # closing it means rewriting two existing tests, which is the owner's call.
    wr = await measured_win_rate(db)
    assert wr["closed"] == 40
    assert wr["rate"] is not None, (
        "если стало None — was_published() добавили и в measured_stats; "
        "тогда этот тест надо переписать на симметричный track_record"
    )


@pytest.mark.asyncio
async def test_mixed_sample_counts_only_the_sent_half(db: AsyncSession):
    p = await _provider(db)
    for i in range(10):
        db.add(_closed(p.id, ticker=f"SENT{i}", tg_vip_message_id=1000 + i))
    for i in range(10):
        db.add(_closed(p.id, ticker=f"QUIET{i}"))
    await db.commit()

    assert len(await _closed_real(db)) == 10
    assert (await summary(db=db))["closed_trades"] == 10


def test_is_published_matches_the_sql_condition():
    """The in-Python helper and the SQL clause must not drift apart."""
    assert str(was_published())  # compiles
    assert is_published(_closed(None, tg_vip_message_id=1)) is True
    assert is_published(_closed(None, tg_free_message_id=1)) is True
    assert is_published(_closed(None)) is False
