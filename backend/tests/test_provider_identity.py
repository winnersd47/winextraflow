"""One Telegram channel must resolve to exactly one provider row.

Every flag that decides a signal's fate lives on the row — `paper_only`,
`is_active` — and so does the history the WEF Score and the track record read.
A second row for the same channel splits both: a source on trial is published
through its unmarked twin, and a win rate is computed over half the trades.

The key has changed twice. Rows written under Telethon hold the numeric channel
id plus the channel's real title ("BestStocks | Инвест-идеи США"); rows
registered by hand hold the username; rows written since the move to the public
web preview hold the username. Matching on the current key alone created a
duplicate for every channel with history — the first run after that move made
17 of them, one per monitored channel.

`description` is the join that survives all three: every auto-created and every
hand-registered row carries "@username".
"""
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import Provider, ProviderSource

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.tg_backfill import find_provider  # noqa: E402


async def _add(db: AsyncSession, name: str, *, key: str | None = None,
               descr: str | None = None, signals: int = 0,
               paper: bool = False) -> Provider:
    p = Provider(id=uuid.uuid4(), name=name, source=ProviderSource.TELEGRAM,
                 telegram_channel_id=key, description=descr,
                 total_signals=signals, paper_only=paper, is_seed=False)
    db.add(p)
    await db.commit()
    return p


@pytest.mark.asyncio
async def test_numeric_row_is_found_by_username_in_its_description(db: AsyncSession):
    """The real shape: 98 signals under a numeric key, looked up by username."""
    old = await _add(db, "BestStocks | Инвест-идеи США", key="1787833823",
                     descr="Auto @ricesignal", signals=98)

    found = await find_provider(db, "ricesignal")
    assert found is not None and found.id == old.id, \
        "не нашли историческую строку — бэкфил создаст дубль"


@pytest.mark.asyncio
async def test_lookup_adopts_the_username_as_the_key(db: AsyncSession):
    """Found once by description, found by key from then on."""
    await _add(db, "DluxTrading", key="1704324604",
               descr="Auto @ddluuxx_trading", signals=11)

    found = await find_provider(db, "ddluuxx_trading")
    assert found.telegram_channel_id == "ddluuxx_trading"


@pytest.mark.asyncio
async def test_a_trial_row_is_not_bypassed(db: AsyncSession):
    """The failure this exists to prevent: ingesting through an unmarked twin."""
    await _add(db, "Silver fx Trading signals (free)", key="2917121507",
               descr="Auto @silver_fx_trading_signals_free", signals=4,
               paper=True)

    found = await find_provider(db, "silver_fx_trading_signals_free")
    assert found.paper_only is True


@pytest.mark.asyncio
async def test_a_longer_username_does_not_match_a_shorter_one(db: AsyncSession):
    """@silver_fx_trading_signal must not swallow @silver_fx_trading_signals_free.

    Both exist in this database — the short one is a typo'd registration.
    """
    short = await _add(db, "Silver FX Trading", key="silver_fx_trading_signal",
                       descr="На оценке: @silver_fx_trading_signal")
    full = await _add(db, "Silver fx (free)", key="2917121507",
                      descr="Auto @silver_fx_trading_signals_free", signals=4)

    assert (await find_provider(db, "silver_fx_trading_signal")).id == short.id
    assert (await find_provider(db, "silver_fx_trading_signals_free")).id == full.id


@pytest.mark.asyncio
async def test_the_row_with_the_history_wins(db: AsyncSession):
    """When both shapes exist, the signals decide — not insertion order."""
    await _add(db, "ddluuxx_trading", key="ddluuxx_trading_other",
               descr="Auto @shared_name", signals=0)
    rich = await _add(db, "DluxTrading", key="1704324604",
                      descr="Auto @shared_name", signals=11)

    assert (await find_provider(db, "shared_name")).id == rich.id


@pytest.mark.asyncio
async def test_unknown_channel_resolves_to_nothing(db: AsyncSession):
    """So the caller creates one row, deliberately, rather than guessing."""
    await _add(db, "BestStocks | Инвестиции", key="1787833823",
               descr="Auto @beststocksru", signals=55)

    assert await find_provider(db, "some_channel_never_seen") is None
    assert await find_provider(db, "") is None


@pytest.mark.asyncio
async def test_name_match_is_the_last_resort(db: AsyncSession):
    rec = await _add(db, "learn2tradenews")
    assert (await find_provider(db, "learn2tradenews")).id == rec.id
