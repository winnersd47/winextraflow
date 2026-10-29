"""The evolutionary verdict must not re-impose a rule the gate dropped.

`should_trade` required `rr >= 1.5`, and that one clause was the platform's
real publishing rule. Between 2026-10-05 and 10-29 every signal at R:R >= 1.68
reached the channel and every signal at R:R <= 1.16 was dropped with
"Evolution: SKIP" — so when the incoming flow turned to forex and futures with
modest targets, publishing stopped for two weeks and nobody was told.

It also pointed the wrong way. The quality gate replaced its ratio floor with
the breakeven share after replaying 80 signals showed the worst outcomes came
from the farthest targets. A floor on R:R therefore selects for the failure
mode: CVX at R:R 5.80 needs 15% of trades to win and sailed through, SILV at
1.08 needs 48% and was blocked.

These tests pin the direction, not the exact numbers — thresholds live in
`signal_quality` and these read them from there.
"""
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import Provider, ProviderSource
from app.models.signal import Signal, SignalAction, SignalStatus
from app.services.expert_trading import expected_value
from app.services.quant.recommendations import recommendation_engine
from app.services.signal_quality import BREAKEVEN_REJECT_PCT


def _breakeven_pct(rr: float) -> float:
    return expected_value(0.55, rr, 1.0)["breakeven_win_rate"] * 100


async def _setup(db: AsyncSession, *, entry: float, tp: float, sl: float,
                 conf: float = 0.76) -> tuple[Signal, Provider]:
    p = Provider(id=uuid.uuid4(), name=f"Verdict {uuid.uuid4().hex[:6]}",
                 source=ProviderSource.TELEGRAM, is_seed=False)
    db.add(p)
    await db.flush()
    s = Signal(id=uuid.uuid4(), provider_id=p.id, ticker="EURJPY",
               action=SignalAction.BUY, entry_price=entry, take_profit=tp,
               stop_loss=sl, status=SignalStatus.ACTIVE, ai_confidence=conf,
               raw_message="")
    db.add(s)
    await db.commit()
    return s, p


@pytest.mark.asyncio
async def test_modest_ratio_is_not_skipped_for_its_ratio(db: AsyncSession):
    """R:R 1.08 — the real SILV/EURJPY shape that stalled publishing."""
    # risk 1.00, reward 1.08 -> breakeven 48%, far below the gate's threshold
    s, p = await _setup(db, entry=100.0, tp=101.08, sl=99.0)
    assert _breakeven_pct(1.08) < BREAKEVEN_REJECT_PCT

    rec = await recommendation_engine.recommend(db, s, p)
    expert = rec.get("expert", {}) or {}
    assert expert.get("verdict") != "SKIP", (
        f"сетап с безубытком {_breakeven_pct(1.08):.0f}% отклонён — "
        f"похоже, вернулся порог по отношению R:R"
    )
    assert expert.get("should_trade") is not False


@pytest.mark.asyncio
async def test_setup_needing_most_trades_to_win_is_skipped(db: AsyncSession):
    """R:R 0.11 — the VTBR futures shape, 90% of trades must be right."""
    s, p = await _setup(db, entry=100.0, tp=100.11, sl=99.0)
    assert _breakeven_pct(0.11) > BREAKEVEN_REJECT_PCT

    rec = await recommendation_engine.recommend(db, s, p)
    expert = rec.get("expert", {}) or {}
    assert expert.get("verdict") == "SKIP" or expert.get("should_trade") is False


@pytest.mark.asyncio
async def test_far_target_is_not_graded_stronger_than_a_near_one(db: AsyncSession):
    """STRONG used to mean "target far away" — the measured failure mode.

    Replaying 80 signals put the farthest-target band at -7.04% per trade
    against -0.41% for the nearest, so distance must not be what earns the top
    grade. Both setups here clear the gate; the far one must not outrank the
    near one on distance alone.
    """
    near, p1 = await _setup(db, entry=100.0, tp=102.0, sl=99.0, conf=0.86)   # R:R 2.0
    far, p2 = await _setup(db, entry=100.0, tp=105.8, sl=99.0, conf=0.86)    # R:R 5.8

    grades = {"SKIP": 0, "MARGINAL": 1, "GOOD": 2, "STRONG": 3}
    g_near = grades[(await recommendation_engine.recommend(db, near, p1))
                    .get("expert", {}).get("verdict", "SKIP")]
    g_far = grades[(await recommendation_engine.recommend(db, far, p2))
                   .get("expert", {}).get("verdict", "SKIP")]

    assert g_near > 0 and g_far > 0, "оба сетапа проходят фильтр качества"
    assert g_far <= g_near, (
        "дальняя цель получила оценку выше ближней — это ровно тот перекос, "
        "из-за которого R:R убрали из WEF Score"
    )
