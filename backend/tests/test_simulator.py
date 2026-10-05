"""Tests for the practice simulator and the position-sizing figure it exposed.

The simulator shares `paper_accounts` / `paper_trades` with the platform's own
measured record, and that record is the one thing the project cannot regenerate.
Most of what follows guards the boundary between them: if a user practising with
deliberately bad entries could move the published win rate, the record would stop
meaning anything.

Building the simulator also surfaced a live bug in `position_size`: it reported
the risk *budget* as `risk_money` even when the 25%-share cap had cut the
position down. The worst stored row claimed 1000 RUB of risk against an actual
81 RUB, and the Telegram sizing block printed the same overstatement. The last
three tests pin the corrected behaviour.
"""

import uuid
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def _sim_user(db: AsyncSession):
    from app.models.user import User
    u = User(email=f"sim_{uuid.uuid4().hex[:6]}@test.com",
             username=f"sim_{uuid.uuid4().hex[:6]}",
             hashed_password="x", is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest.fixture
def fixed_price(monkeypatch):
    """Pin the price feed so no simulator test depends on the network."""
    state = {"price": 100.0}

    async def fake(ticker):
        if ticker == "НЕТТАКОГО":
            return None
        return {"ticker": ticker, "price": state["price"], "source": "test"}

    monkeypatch.setattr("app.services.simulator.get_live_price", fake)
    return state


# ═══════════════════════════════════════════════════════════════════════════
# The boundary with the measured record
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_simulator_trades_stay_out_of_platform_record(db: AsyncSession, fixed_price):
    """A user practising must not move the platform's numbers."""
    from app.models.paper import PaperAccount, PaperTrade
    from app.services import simulator
    from app.services.paper_trading import (ensure_accounts, platform_accounts,
                                            platform_trades)

    await ensure_accounts(db)
    plat_before = len((await db.execute(
        platform_accounts(select(PaperAccount)))).scalars().all())

    user = await _sim_user(db)
    acc = await simulator.ensure_user_account(db, user)
    await simulator.open_position(db, acc, "SBER", "buy", stop_loss=95.0)

    plat_accs = (await db.execute(platform_accounts(select(PaperAccount)))).scalars().all()
    plat_trds = (await db.execute(platform_trades(select(PaperTrade)))).scalars().all()

    assert len(plat_accs) == plat_before, "a user account counted as a platform one"
    assert acc.id not in {a.id for a in plat_accs}
    assert all(t.account_id != acc.id for t in plat_trds), \
        "a hand-opened trade reached the platform record"


@pytest.mark.asyncio
async def test_public_paper_endpoints_exclude_simulator(client, db: AsyncSession, fixed_price):
    """/api/v1/paper is public and must serve the platform's record only."""
    from app.services import simulator
    from app.services.paper_trading import ensure_accounts

    await ensure_accounts(db)
    user = await _sim_user(db)
    acc = await simulator.ensure_user_account(db, user)
    await simulator.open_position(db, acc, "MYSIM", "buy", stop_loss=95.0)

    r = await client.get("/api/v1/paper/accounts")
    assert r.status_code == 200
    assert acc.name not in [a["account"] for a in r.json()["accounts"]]

    r = await client.get("/api/v1/paper/trades?limit=200")
    assert r.status_code == 200
    tickers = [t["ticker"] for t in r.json().get("trades", [])]
    assert "MYSIM" not in tickers, "a simulator trade appeared in the public list"


@pytest.mark.asyncio
async def test_simulator_cannot_reach_another_account(db: AsyncSession, fixed_price):
    """`get_account` is scoped by user_id, so a guessed id resolves to nothing."""
    from app.services import simulator
    from app.services.paper_trading import ensure_accounts

    a, b = await _sim_user(db), await _sim_user(db)
    acc_a = await simulator.ensure_user_account(db, a)

    assert await simulator.get_account(db, b, acc_a.id) is None, \
        "one user resolved the account of another"

    plat = (await ensure_accounts(db))[0]
    assert await simulator.get_account(db, a, plat.id) is None, \
        "a user resolved a platform account"


def test_simulator_has_no_real_order_path():
    """The simulator must not grow an exchange adapter. Routing client orders is
    a licensing decision, not a refactor."""
    src = (Path(__file__).resolve().parents[1] / "app" / "services"
           / "simulator.py").read_text(encoding="utf-8")
    code = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))
    for bad in ("exchanges", "place_market_order", "place_limit_order",
                "ExchangeAccount", "api_key"):
        assert bad not in code, f"simulator references {bad}"


# ═══════════════════════════════════════════════════════════════════════════
# Order handling
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_simulator_rejects_levels_on_the_wrong_side(db: AsyncSession, fixed_price):
    """A long whose target sits below entry settles the instant it opens."""
    from app.services import simulator

    user = await _sim_user(db)
    acc = await simulator.ensure_user_account(db, user)

    with pytest.raises(ValueError, match="выше цены входа"):
        await simulator.open_position(db, acc, "SBER", "buy", units=1, take_profit=95.0)
    with pytest.raises(ValueError, match="ниже цены входа"):
        await simulator.open_position(db, acc, "SBER", "buy", units=1, stop_loss=105.0)
    with pytest.raises(ValueError, match="ниже цены входа"):
        await simulator.open_position(db, acc, "SBER", "sell", units=1, take_profit=105.0)
    with pytest.raises(ValueError, match="выше цены входа"):
        await simulator.open_position(db, acc, "SBER", "sell", units=1, stop_loss=95.0)


@pytest.mark.asyncio
async def test_simulator_refuses_unknown_ticker(db: AsyncSession, fixed_price):
    """No price means no fill — never a fabricated one."""
    from app.services import simulator

    user = await _sim_user(db)
    acc = await simulator.ensure_user_account(db, user)
    with pytest.raises(ValueError, match="Нет цены"):
        await simulator.open_position(db, acc, "НЕТТАКОГО", "buy", units=1)


@pytest.mark.asyncio
async def test_simulator_caps_position_share(db: AsyncSession, fixed_price):
    """One trade must not decide the fate of the account."""
    from app.services import simulator

    user = await _sim_user(db)
    acc = await simulator.ensure_user_account(db, user)
    with pytest.raises(ValueError, match="превышает лимит"):
        await simulator.open_position(db, acc, "SBER", "buy", units=1_000_000)


@pytest.mark.asyncio
async def test_simulator_charges_commission_both_ways(db: AsyncSession, fixed_price):
    """A simulator without commission teaches that a marginal strategy works.
    A round turn at an unchanged price must therefore lose money."""
    from app.models.paper import PaperTrade
    from app.services import simulator

    user = await _sim_user(db)
    acc = await simulator.ensure_user_account(db, user)
    start = acc.balance

    res = await simulator.open_position(db, acc, "SBER", "buy", units=10)
    trade = (await db.execute(select(PaperTrade).where(
        PaperTrade.id == uuid.UUID(res["trade"]["id"])))).scalar_one()
    out = await simulator.close_position(db, acc, trade)

    assert out["gross_pnl"] == pytest.approx(0.0, abs=0.01), "price did not move"
    assert out["net_pnl"] < 0, "a round turn at one price must cost money"
    assert out["commission"] > 0
    assert acc.balance < start


@pytest.mark.asyncio
async def test_simulator_pnl_direction_for_short(db: AsyncSession, fixed_price):
    """A short gains when price falls. Sign errors here would flatter or punish
    every short in the account."""
    from app.models.paper import PaperTrade
    from app.services import simulator

    user = await _sim_user(db)
    acc = await simulator.ensure_user_account(db, user)
    res = await simulator.open_position(db, acc, "SBER", "sell", units=10)

    fixed_price["price"] = 90.0
    trade = (await db.execute(select(PaperTrade).where(
        PaperTrade.id == uuid.UUID(res["trade"]["id"])))).scalar_one()
    out = await simulator.close_position(db, acc, trade)

    assert out["gross_pnl"] == pytest.approx(100.0), "short of 10 from 100 to 90"
    assert out["net_pnl"] > 0


@pytest.mark.asyncio
async def test_simulator_settles_at_the_frozen_level(db: AsyncSession, fixed_price):
    """Settlement uses the level, not the price that broke through it — the same
    invariant the platform record relies on."""
    from app.services import simulator

    user = await _sim_user(db)
    acc = await simulator.ensure_user_account(db, user)
    await simulator.open_position(db, acc, "SBER", "buy",
                                  units=10, take_profit=110.0, stop_loss=95.0)

    fixed_price["price"] = 94.0                       # gapped through the stop
    out = await simulator.settle_levels(db, acc)
    assert len(out["closed"]) == 1
    assert out["closed"][0]["kind"] == "stop"
    assert out["closed"][0]["level"] == 95.0, "settled away from the frozen level"


@pytest.mark.asyncio
async def test_simulator_reset_clears_only_that_account(db: AsyncSession, fixed_price):
    """Reset is destructive by design; it must not reach past its own account."""
    from app.models.paper import PaperTrade
    from app.services import simulator
    from app.services.paper_trading import ensure_accounts, platform_trades

    await ensure_accounts(db)
    plat_before = len((await db.execute(
        platform_trades(select(PaperTrade)))).scalars().all())

    user = await _sim_user(db)
    acc = await simulator.ensure_user_account(db, user)
    await simulator.open_position(db, acc, "SBER", "buy", units=1)

    out = await simulator.reset_account(db, acc)
    assert out["deleted_trades"] == 1
    assert acc.balance == acc.starting_balance

    plat_after = len((await db.execute(
        platform_trades(select(PaperTrade)))).scalars().all())
    assert plat_after == plat_before, "reset deleted platform trades"


# ═══════════════════════════════════════════════════════════════════════════
# Honesty of what the terminal shows
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_simulator_withholds_win_rate_below_sample_floor(db: AsyncSession, fixed_price):
    """Same floor the platform applies to itself. A rate over three practice
    trades is noise, and publishing it teaches the habit the lessons warn about."""
    from app.models.paper import PaperTrade
    from app.services import simulator

    user = await _sim_user(db)
    acc = await simulator.ensure_user_account(db, user)
    for _ in range(3):
        res = await simulator.open_position(db, acc, "SBER", "buy", units=1)
        t = (await db.execute(select(PaperTrade).where(
            PaperTrade.id == uuid.UUID(res["trade"]["id"])))).scalar_one()
        await simulator.close_position(db, acc, t)

    p = await simulator.portfolio(db, acc)
    assert p["closed_count"] == 3
    assert p["enough_data"] is False
    assert p["win_rate_pct"] is None, "a win rate over 3 trades was published"
    assert str(p["min_sample"]) in p["notice_ru"]


@pytest.mark.asyncio
async def test_simulator_discloses_what_it_cannot_model(db: AsyncSession, fixed_price):
    """The terminal looks real, so the response must say where it is not."""
    from app.services import simulator

    user = await _sim_user(db)
    acc = await simulator.ensure_user_account(db, user)
    p = await simulator.portfolio(db, acc)

    text = p["disclosure_ru"].lower()
    for term in ("спред", "проскальзыв", "запазд", "комисс"):
        assert term in text, f"disclosure omits {term}"
    assert "реальные заявки не отправляются" in text


@pytest.mark.asyncio
async def test_simulator_marks_a_position_whose_price_is_gone(db: AsyncSession, fixed_price,
                                                              monkeypatch):
    """A dead feed must not render as a zero P&L, which reads as break-even."""
    from app.services import simulator

    user = await _sim_user(db)
    acc = await simulator.ensure_user_account(db, user)
    await simulator.open_position(db, acc, "SBER", "buy", units=1)

    async def dead(ticker):
        return None
    monkeypatch.setattr("app.services.simulator.get_live_price", dead)

    p = await simulator.portfolio(db, acc)
    pos = p["positions"][0]
    assert pos["price_unavailable"] is True
    assert pos["unrealised_pnl"] is None, "an unpriceable position showed a P&L"


# ═══════════════════════════════════════════════════════════════════════════
# Position sizing: the risk figure must be what the stop actually costs
# ═══════════════════════════════════════════════════════════════════════════

def test_risk_money_reflects_the_capped_position():
    """`risk_money` used to report the budget even after the share cap cut the
    position down — a two-fold overstatement on a 2% stop."""
    from app.services.position_sizing import MAX_POSITION_SHARE, position_size

    s = position_size(100_000, 100.0, 98.0, 0.01)      # 2% stop -> cap bites
    assert s["position_capped"] is True
    assert s["position"] == pytest.approx(100_000 * MAX_POSITION_SHARE)
    assert s["risk_money"] == pytest.approx(s["position"] * s["stop_pct"]), \
        "risk_money must be what this position loses at its stop"
    assert s["risk_money"] < s["risk_money_budget"], \
        "a capped position risks less than the budget"


def test_risk_money_equals_budget_when_uncapped():
    """The fix must not disturb the ordinary case."""
    from app.services.position_sizing import position_size

    s = position_size(100_000, 100.0, 92.0, 0.01)      # 8% stop -> no cap
    assert s["position_capped"] is False
    assert s["risk_money"] == pytest.approx(s["risk_money_budget"])
    assert s["risk_money"] == pytest.approx(1_000.0)


def test_sizing_block_states_the_reduced_risk():
    """The post used to claim "1% = 1 000 RUB" and then say the position was
    capped, leaving the reader to spot the contradiction."""
    from app.services.position_sizing import sizing_block

    text = sizing_block("SBER", 100.0, 98.0)
    # Thousands are separated by a thin space (U+2009), not an ASCII one.
    assert "Риск на сделку: 500 ₽" in text, text
    assert "1 000 ₽" in text, "the budget belongs in the post for contrast"
    assert "а не" in text, "the post must name what the risk is NOT"
