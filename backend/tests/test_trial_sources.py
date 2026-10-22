"""Sources on trial: measured, never published, never counted.

A new source cannot be judged before it has a record, and cannot get a record
without being traded. The forex channels this was built for need 67-87% of their
trades to win merely to break even — and the platform's own record is 0 wins in
10 closed trades, so neither figure predicts the other. Publishing them to find
out would be finding out with subscribers watching.

So a `paper_only` provider is parsed, scored and opened on the "evaluation"
paper account, and three things must hold:

  * nothing it produces is broadcast;
  * its trades never enter the platform's measured record, even though the
    evaluation account also has a NULL user_id and would otherwise pass the
    platform filter;
  * it cannot be promoted to publishing before MIN_SAMPLE closed trades, because
    a trial you can end early is not a trial.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import PaperAccount, PaperTrade, PaperTradeStatus
from app.models.provider import Provider, ProviderSource
from app.models.signal import Signal, SignalAction, SignalStatus
from app.services.paper_trading import (ensure_accounts, platform_accounts,
                                        platform_trades, sync_open)


async def _provider(db: AsyncSession, *, trial: bool) -> Provider:
    p = Provider(name=f"{'trial' if trial else 'live'}_{uuid.uuid4().hex[:6]}",
                 source=ProviderSource.TELEGRAM, paper_only=trial, is_active=True)
    db.add(p)
    await db.flush()
    return p


@pytest.fixture
def pinned_price(monkeypatch):
    """Pin the feed to the test signals' entry.

    These tests are about where a signal goes, not about the market. Letting the
    real price in made the staleness check fire whenever gold drifted a few
    percent from the fixture, and the pipeline returned "stale_entry" instead of
    the branch under test.
    """
    async def fake(ticker):
        return {"ticker": ticker, "price": 4000.0, "source": "test"}

    # signal_pipeline imports it inside the function, so patching the
    # importer would miss — the name is looked up on the source module.
    import app.services.live_price as lp
    monkeypatch.setattr(lp, "get_live_price", fake)
    return fake


async def _signal(db: AsyncSession, prov: Provider, ticker="XAUUSD") -> Signal:
    s = Signal(provider_id=prov.id, ticker=ticker, action=SignalAction.BUY,
               entry_price=4000.0, take_profit=4010.0, stop_loss=3980.0,
               status=SignalStatus.ACTIVE, ai_confidence=0.86,
               raw_message="trial signal")
    db.add(s)
    await db.flush()
    return s


# ═══════════════════════════════════════════════════════════════════════
# The boundary with the measured record
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_evaluation_account_is_not_part_of_the_platform_record(db: AsyncSession):
    """It has a NULL user_id like the platform accounts, so the user filter
    alone would have let it straight into the published numbers."""
    await ensure_accounts(db)

    evaluation = (await db.execute(
        select(PaperAccount).where(PaperAccount.scope == "evaluation")
    )).scalars().all()
    assert evaluation, "the evaluation account was not created"
    assert all(a.user_id is None for a in evaluation), "precondition"

    platform = (await db.execute(
        platform_accounts(select(PaperAccount)))).scalars().all()
    ids = {a.id for a in platform}
    for a in evaluation:
        assert a.id not in ids, \
            f"{a.name} counts as a platform account despite scope=evaluation"


@pytest.mark.asyncio
async def test_trial_signals_reach_only_the_evaluation_account(db: AsyncSession):
    """A platform account must not open a position on a source under trial, and
    the evaluation account must not open one on anything else."""
    accounts = await ensure_accounts(db)
    evaluation = (await db.execute(
        select(PaperAccount).where(PaperAccount.scope == "evaluation")
    )).scalar_one()

    trial, live = await _provider(db, trial=True), await _provider(db, trial=False)
    trial_sig = await _signal(db, trial, "XAUUSD")
    live_sig = await _signal(db, live, "SBER")
    await db.commit()

    for acc in accounts:
        await sync_open(db, acc)
    await sync_open(db, evaluation)

    for acc in accounts:
        if acc.scope != "platform":
            continue
        got = (await db.execute(select(PaperTrade).where(
            PaperTrade.account_id == acc.id))).scalars().all()
        assert all(t.signal_id != trial_sig.id for t in got), \
            f"{acc.name} traded a source that is still on trial"

    got = (await db.execute(select(PaperTrade).where(
        PaperTrade.account_id == evaluation.id))).scalars().all()
    assert any(t.signal_id == trial_sig.id for t in got), \
        "the evaluation account did not pick up the trial signal"
    assert all(t.signal_id != live_sig.id for t in got), \
        "the evaluation account took a signal from a published source"


@pytest.mark.asyncio
async def test_trial_trades_stay_out_of_the_public_trade_list(db: AsyncSession):
    await ensure_accounts(db)
    evaluation = (await db.execute(
        select(PaperAccount).where(PaperAccount.scope == "evaluation")
    )).scalar_one()
    trial = await _provider(db, trial=True)
    sig = await _signal(db, trial)
    await db.commit()
    await sync_open(db, evaluation)

    public = (await db.execute(platform_trades(select(PaperTrade)))).scalars().all()
    assert all(t.signal_id != sig.id for t in public), \
        "a trial trade appeared in the platform record"


# ═══════════════════════════════════════════════════════════════════════
# Nothing is published
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_pipeline_does_not_broadcast_a_trial_source(db: AsyncSession, monkeypatch,
                                                          pinned_price):
    """Scored and recorded, but no card, no teaser, no channel."""
    from app.services import signal_pipeline

    sent = []
    monkeypatch.setattr(signal_pipeline, "broadcast_card",
                        lambda *a, **k: sent.append(a) or 1, raising=False)

    trial = await _provider(db, trial=True)
    sig = await _signal(db, trial)
    await db.commit()

    result = await signal_pipeline.process_and_broadcast(db, sig, trial)
    assert result["broadcast"] is False
    assert result["reason"] == "paper_only"
    assert not sent, "a trial source reached a channel"
    assert sig.tg_vip_message_id is None


@pytest.mark.asyncio
async def test_trial_source_is_still_scored(db: AsyncSession, pinned_price):
    """The point is to measure it. A source with no score cannot be judged."""
    from app.services import signal_pipeline

    trial = await _provider(db, trial=True)
    sig = await _signal(db, trial)
    sig.ai_confidence = None
    await db.commit()

    result = await signal_pipeline.process_and_broadcast(db, sig, trial)
    assert result.get("wef") is not None, "trial signal was not scored"


# ═══════════════════════════════════════════════════════════════════════
# Promotion requires evidence
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_promotion_is_refused_without_a_sample(db: AsyncSession):
    """A trial that can be ended early is a formality, not a trial."""
    import subprocess
    import sys as _sys
    from pathlib import Path

    from app.services.measured_stats import MIN_SAMPLE

    trial = await _provider(db, trial=True)
    for _ in range(MIN_SAMPLE - 1):
        s = await _signal(db, trial)
        s.status = SignalStatus.CLOSED_TP
    await db.commit()

    # The guard lives in the script, so assert on the script rather than a copy.
    src = (Path(__file__).resolve().parents[1] / "scripts"
           / "add_trial_source.py").read_text(encoding="utf-8")
    assert "MIN_SAMPLE" in src and "Отказ" in src, \
        "promotion no longer checks the sample size"
    assert "prov.paper_only = False" in src.split("--promote")[-1], \
        "promotion path changed shape — re-check the guard"


@pytest.mark.asyncio
async def test_ensure_accounts_is_idempotent_across_scopes(db: AsyncSession):
    """Narrowing `platform_accounts` to scope="platform" was right for the
    published record and wrong here: the evaluation account was never seen as
    existing, so a fresh copy was created on every cron run. 171 duplicates
    accumulated in a week before anyone looked."""
    first = await ensure_accounts(db)
    for _ in range(3):
        await ensure_accounts(db)

    owned = (await db.execute(select(PaperAccount).where(
        PaperAccount.user_id.is_(None)))).scalars().all()
    assert len(owned) == len(first), (
        f"ensure_accounts created duplicates: {len(owned)} accounts after "
        f"four runs, expected {len(first)}")

    names = [a.name for a in owned]
    assert len(names) == len(set(names)), f"duplicate account names: {names}"
    assert sum(1 for a in owned if a.scope == "evaluation") == 1


def test_trial_registration_targets_the_list_the_poller_reads():
    """`load_monitored` reads monitored_channels.json and only falls back to
    TELEGRAM_PARSE_CHANNELS when that file is absent. The script used to tell
    the operator to edit .env — advice that silently did nothing, and three
    forex channels sat unread for a week because of it."""
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "scripts"
           / "add_trial_source.py").read_text(encoding="utf-8")
    code = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "save_monitored" in code, \
        "registration does not write to the list the poller actually reads"
    assert "TELEGRAM_PARSE_CHANNELS" not in code, \
        "the script still points the operator at .env"


def test_result_is_published_only_for_a_published_setup():
    """The monitor posted outcomes for signals nobody had seen.

    A source under evaluation is ingested deliberately without publishing, so
    its record can be built before subscribers are shown anything. The monitor
    announced its win in VIP regardless — a standalone post with nothing to
    reply to, claiming a result for a trade the channel never carried.
    """
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "scripts"
           / "monitor_signals.py").read_text(encoding="utf-8")
    code = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))

    close_at = code.index("SignalStatus.CLOSED_TP if won")
    post_at = code.index("_post(VIP_CHANNEL", close_at)
    between = code[close_at:post_at]
    assert "tg_vip_message_id" in between, \
        "nothing checks whether the setup was ever published"
    assert "continue" in between, \
        "the unpublished case does not skip the result post"


def test_provider_lookup_matches_a_hand_registered_row():
    """The poller keyed providers by numeric channel id while
    add_trial_source.py stored the username, so every trial channel got a second,
    unflagged row — and the signals landed on that one. A source marked
    paper_only was published to subscribers through its own twin."""
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "scripts"
           / "tg_backfill.py").read_text(encoding="utf-8")
    code = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))
    start = code.index("provider = (await db.execute(")
    lookup = code[start:code.index("for m in msgs", start)]
    assert lookup.count("Provider.telegram_channel_id ==") >= 2, \
        "provider lookup still matches on the numeric id alone"
