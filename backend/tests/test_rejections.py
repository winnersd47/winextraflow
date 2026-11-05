"""Rejections must be kept, deduplicated, and never cost a signal.

The pipeline used to `continue` past every candidate it refused, which left the
platform's central claim — that its filter is worth paying for — unmeasurable
in principle. Counted 2026-11-05: 194 real signals stored, one recorded
rejection.
"""
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import Provider, ProviderSource
from app.models.rejected import RejectedCandidate, RejectionStage

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.tg_backfill import record_rejection  # noqa: E402


class _Parsed:
    ticker, action = "EURUSD", "sell"
    entry_price, take_profit, stop_loss = 1.08, 1.07, 1.085


async def _provider(db):
    p = Provider(id=uuid.uuid4(), name="Rej Test",
                 source=ProviderSource.TELEGRAM, is_seed=False)
    db.add(p)
    await db.commit()
    return p


@pytest.mark.asyncio
async def test_a_rejected_candidate_is_kept_with_its_levels(db: AsyncSession):
    """Levels are what make the row replayable; without them it is a count."""
    p = await _provider(db)
    await record_rejection(db, channel="ch", provider=p, message_id="ch/1",
                           stage=RejectionStage.DUPLICATE, reason="повтор",
                           text="SELL EURUSD", parsed=_Parsed())

    (row,) = (await db.execute(select(RejectedCandidate))).scalars().all()
    assert row.stage == RejectionStage.DUPLICATE
    assert row.ticker == "EURUSD" and row.action == "sell"
    assert row.entry_price and row.take_profit and row.stop_loss


@pytest.mark.asyncio
async def test_the_same_post_is_not_recorded_twice(db: AsyncSession):
    """The backfill re-reads a post about 48 times before it ages out."""
    p = await _provider(db)
    for _ in range(3):
        await record_rejection(db, channel="ch", provider=p, message_id="ch/7",
                               stage=RejectionStage.PARSE, reason="x", text="t")
    rows = (await db.execute(select(RejectedCandidate))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_an_unparsed_candidate_is_kept_without_levels(db: AsyncSession):
    """Today's regexes miss most RU prose, so this is a record of our own limits."""
    p = await _provider(db)
    await record_rejection(db, channel="ch", provider=p, message_id="ch/2",
                           stage=RejectionStage.PARSE, reason="не разобрано",
                           text="Покупаем Сбер, цель выше")

    (row,) = (await db.execute(select(RejectedCandidate))).scalars().all()
    assert row.ticker is None and row.entry_price is None
    assert "Сбер" in row.raw_message


@pytest.mark.asyncio
async def test_recording_failure_never_costs_a_signal(db: AsyncSession):
    """The row is a measurement; the pipeline is the product."""
    class _Exploding:
        id = "not-a-uuid"

    await record_rejection(db, channel="ch", provider=_Exploding(),
                           message_id=None, stage="nonsense" * 500,
                           reason=None, text=None)   # must not raise


@pytest.mark.asyncio
async def test_long_text_and_reason_are_truncated_not_rejected(db: AsyncSession):
    p = await _provider(db)
    await record_rejection(db, channel="ch", provider=p, message_id="ch/3",
                           stage=RejectionStage.LEVELS, reason="x" * 1000,
                           text="y" * 5000, parsed=_Parsed())

    (row,) = (await db.execute(select(RejectedCandidate))).scalars().all()
    assert len(row.reason) <= 300 and len(row.raw_message) <= 500


def test_every_discard_point_records_something():
    """A `continue` with no record is how the evidence was lost before."""
    import inspect
    from scripts import tg_backfill
    src = inspect.getsource(tg_backfill.main)
    # The three places a candidate that LOOKED like a signal is dropped.
    for stage in ("RejectionStage.PARSE", "RejectionStage.DUPLICATE",
                  "RejectionStage.LEVELS"):
        assert stage in src, f"{stage} нигде не записывается"
