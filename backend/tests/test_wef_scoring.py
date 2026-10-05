"""Tests for the WEF Score after the coverage/renormalization rework.

Each case here corresponds to something measured on the real database, not to a
hypothetical:

  * five factors returned a constant 0.5 for all 153 real signals because the
    provider columns they read were NULL for all 15 providers. 63% of the score's
    weight carried no information and the whole score took 7 distinct values.
  * `risk_reward` was monotonic in R:R, which made the score anti-predictive:
    replaying 80 signals against real candles gave r = -0.35 between score and
    outcome, with average realised P&L falling from -0.41% in the lowest band to
    -7.04% in the highest, where average R:R was 7.1.
  * an inverted level pair (BUY with the target below entry) produced R:R == 1.0
    through abs() and was scored as an ordinary weak trade.
  * Sharpe was annualized with sqrt(252) over per-trade returns and reported
    -69.03 on four losing trades.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import Provider, ProviderSource
from app.models.signal import Signal, SignalAction, SignalStatus
from app.services.ai_rating import (MIN_CLOSED_FOR_RATIOS, MIN_CLOSED_FOR_WIN_RATE,
                                    WEIGHTS, AIRatingService)


async def _provider(db: AsyncSession) -> Provider:
    p = Provider(name=f"wef_{uuid.uuid4().hex[:6]}", source=ProviderSource.MANUAL)
    db.add(p)
    await db.flush()
    return p


async def _signal(db: AsyncSession, prov: Provider, entry: float,
                  tp: float | None, sl: float | None,
                  action: SignalAction = SignalAction.BUY) -> Signal:
    s = Signal(provider_id=prov.id, ticker="TESTUSDT", action=action,
               entry_price=entry, take_profit=tp, stop_loss=sl)
    db.add(s)
    await db.flush()
    return s


# ═══════════════════════════════════════════════════════════════════════
# Missing data must not become a neutral 0.5
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_unmeasurable_factors_are_none_not_half(db: AsyncSession):
    """A fresh provider has no history. Those factors must report nothing."""
    svc = AIRatingService()
    prov = await _provider(db)
    s = await _signal(db, prov, 100.0, 105.0, 98.0)

    b = await svc.rate_signal(db, s)
    for key in ("provider_history", "sharpe_ratio", "profit_factor",
                "max_drawdown"):
        assert b.scores[key] is None, f"{key} substituted a value it cannot know"
    assert b.coverage < 1.0
    assert b.scores["risk_management"] is not None


@pytest.mark.asyncio
async def test_coverage_reports_measured_weight(db: AsyncSession):
    """`coverage` must equal the share of weight that produced a number."""
    svc = AIRatingService()
    prov = await _provider(db)
    s = await _signal(db, prov, 100.0, 105.0, 98.0)

    b = await svc.rate_signal(db, s)
    measured = sum(WEIGHTS[k] for k, v in b.scores.items() if v is not None)
    assert b.coverage == pytest.approx(measured / sum(WEIGHTS.values()))


@pytest.mark.asyncio
async def test_confidence_is_renormalized_not_diluted(db: AsyncSession):
    """With every measured factor at 1.0, confidence must be 1.0.

    Under the old averaging it could not exceed the measured weight plus 0.5 of
    the rest, so a perfect signal from an unknown provider capped around 0.68 —
    indistinguishable from a mediocre one.
    """
    svc = AIRatingService()
    prov = await _provider(db)
    # R:R of 2.5 sits in the attainable band, so risk_reward scores 1.0.
    s = await _signal(db, prov, 100.0, 105.0, 98.0)
    s.timeframe = "1d"
    s.raw_message = "buy TESTUSDT 100 tp 105 sl 98"
    await db.flush()

    b = await svc.rate_signal(db, s)
    assert all(v == 1.0 for v in b.available().values()), b.scores
    assert b.final_confidence == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_signal_without_entry_price_is_not_scored(db: AsyncSession):
    """Every level is relative to entry, so a zero entry means nothing is known."""
    svc = AIRatingService()
    prov = await _provider(db)
    s = await _signal(db, prov, 0.0, 100.0, None)

    b = await svc.rate_signal(db, s)
    assert b.coverage == 0.0
    assert b.final_confidence == 0.0
    assert all(v is None for v in b.scores.values())
    assert "цена входа" in b.reasoning


# ═══════════════════════════════════════════════════════════════════════
# risk_reward: the factor that made the score anti-predictive
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_risk_reward_peaks_at_attainable_geometry(db: AsyncSession):
    """R:R must not be rewarded without limit.

    Measured: the top score band had average R:R 7.1 and average realised P&L
    of -7.04%, against -0.41% in the lowest band. A target seven stops away is
    a distant analyst figure paired with our own tight stop, not a good trade.
    """
    svc = AIRatingService()
    prov = await _provider(db)

    async def score_for(tp: float, sl: float) -> float:
        s = await _signal(db, prov, 100.0, tp, sl)
        v, _ = svc._score_risk_reward(s)
        return v

    rr_2_5 = await score_for(105.0, 98.0)     # R:R 2.5
    rr_4 = await score_for(108.0, 98.0)       # R:R 4.0
    rr_10 = await score_for(120.0, 98.0)      # R:R 10.0

    assert rr_2_5 == 1.0, "attainable geometry should score full marks"
    assert rr_4 < rr_2_5, "R:R 4 must score below R:R 2.5"
    assert rr_10 < rr_4, "R:R 10 must score below R:R 4"
    assert rr_10 <= 0.25, f"an R:R of 10 must be treated as a mismatch, got {rr_10}"


@pytest.mark.asyncio
async def test_risk_reward_still_penalises_negative_edge(db: AsyncSession):
    """The fix must not accidentally reward a stop wider than the target."""
    svc = AIRatingService()
    prov = await _provider(db)
    s = await _signal(db, prov, 100.0, 102.0, 95.0)      # R:R 0.4
    v, reason = svc._score_risk_reward(s)
    assert v <= 0.2
    assert "риск превышает" in reason


@pytest.mark.asyncio
async def test_inverted_levels_are_rejected_not_scored_as_weak(db: AsyncSession):
    """abs() hid a misread direction behind a plausible R:R of 1.0."""
    svc = AIRatingService()
    prov = await _provider(db)

    # BUY with target BELOW entry and stop ABOVE it — equal distances, so the
    # old code computed exactly 1.0 and scored it 0.4.
    s = await _signal(db, prov, 60_000.0, 55_000.0, 65_000.0)
    v, reason = svc._score_risk_reward(s)
    assert v <= 0.05, f"inverted pair scored {v}"
    assert "не с той стороны" in reason

    # And the mirror case for a sell.
    s2 = await _signal(db, prov, 60_000.0, 65_000.0, 55_000.0,
                       action=SignalAction.SELL)
    v2, reason2 = svc._score_risk_reward(s2)
    assert v2 <= 0.05
    assert "не с той стороны" in reason2


@pytest.mark.asyncio
async def test_missing_levels_do_not_count_as_average_rr(db: AsyncSession):
    """No TP/SL used to score risk_reward 0.5 — double-penalising and untrue."""
    svc = AIRatingService()
    prov = await _provider(db)
    s = await _signal(db, prov, 100.0, None, None)
    v, reason = svc._score_risk_reward(s)
    assert v is None
    assert "нет TP или SL" in reason


# ═══════════════════════════════════════════════════════════════════════
# Provider aggregates
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ratios_need_a_real_sample(db: AsyncSession):
    """Sharpe / PF / drawdown stay NULL below the floor.

    With the old floor of 3, four losing trades produced a Sharpe of -69.03 —
    the sqrt(252) annualization applied to per-trade returns — and that number
    fed 15% of every one of the provider's signals.
    """
    svc = AIRatingService()
    prov = await _provider(db)
    for i in range(MIN_CLOSED_FOR_RATIOS - 1):
        s = await _signal(db, prov, 100.0, 105.0, 98.0)
        s.status = SignalStatus.CLOSED_SL
        s.profit_pct = -2.0 - i * 0.1
    await db.commit()

    await svc.recalculate_provider_stats(db, prov.id)
    assert prov.sharpe_ratio is None
    assert prov.profit_factor is None
    assert prov.max_drawdown is None


@pytest.mark.asyncio
async def test_sharpe_is_per_trade_and_plausible(db: AsyncSession):
    """Above the floor, Sharpe must land in a range a human can read."""
    svc = AIRatingService()
    prov = await _provider(db)
    for i in range(MIN_CLOSED_FOR_RATIOS + 2):
        s = await _signal(db, prov, 100.0, 105.0, 98.0)
        s.status = (SignalStatus.CLOSED_TP if i % 2 else SignalStatus.CLOSED_SL)
        s.profit_pct = 5.0 if i % 2 else -2.0
    await db.commit()

    await svc.recalculate_provider_stats(db, prov.id)
    assert prov.sharpe_ratio is not None
    assert -5.0 < prov.sharpe_ratio < 5.0, \
        f"Sharpe {prov.sharpe_ratio} is outside any readable range"


@pytest.mark.asyncio
async def test_win_rate_gate_uses_closed_count_not_total(db: AsyncSession):
    """The gate read `total_signals`, the value came from closed ones.

    So a provider with many open signals and a single closed loss was scored
    "Poor win rate: 0%" on a sample of one.
    """
    svc = AIRatingService()
    prov = await _provider(db)
    for _ in range(40):
        await _signal(db, prov, 100.0, 105.0, 98.0)
    closed = await _signal(db, prov, 100.0, 105.0, 98.0)
    closed.status = SignalStatus.CLOSED_SL
    closed.profit_pct = -2.0
    await db.commit()
    await svc.recalculate_provider_stats(db, prov.id)

    assert prov.total_signals > MIN_CLOSED_FOR_WIN_RATE, "precondition"
    assert prov.win_rate == 0.0, "one closed loss gives a 0% rate"

    v, reason = await svc._score_provider_history(db, prov.id)
    assert v is None, "a win rate over one trade must not be scored"
    assert str(MIN_CLOSED_FOR_WIN_RATE) in reason


# ═══════════════════════════════════════════════════════════════════════
# Payload shape
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_payload_keeps_all_factors_and_flags_unavailable(db: AsyncSession):
    """The UI iterates every factor and multiplies score by 100 for a bar."""
    svc = AIRatingService()
    prov = await _provider(db)
    s = await _signal(db, prov, 100.0, 105.0, 98.0)

    d = (await svc.rate_signal(db, s)).to_dict()
    assert set(d["factors"]) == set(WEIGHTS), "a factor vanished from the payload"
    for key, f in d["factors"].items():
        assert isinstance(f["score"], float), f"{key} score must stay numeric"
        assert isinstance(f["available"], bool)
        if not f["available"]:
            assert f["effective_weight"] == 0.0
    assert 0.0 <= d["coverage"] <= 1.0
    assert d["measured_factors"] < d["total_factors"]
    # Effective weights of the measured factors must renormalize to 1.
    total = sum(f["effective_weight"] for f in d["factors"].values())
    assert total == pytest.approx(1.0, abs=0.01)


@pytest.mark.asyncio
async def test_payload_default_matches_the_computation(db: AsyncSession):
    """to_dict() defaulted a missing factor to 0 while the sum used 0.5, so the
    API could disagree with the score it was describing."""
    svc = AIRatingService()
    prov = await _provider(db)
    s = await _signal(db, prov, 100.0, 105.0, 98.0)
    b = await svc.rate_signal(db, s)
    d = b.to_dict()

    recomputed = sum(d["factors"][k]["score"] * d["factors"][k]["effective_weight"]
                     for k in WEIGHTS if d["factors"][k]["available"])
    assert recomputed == pytest.approx(d["final_confidence"], abs=0.005)


# ═══════════════════════════════════════════════════════════════════════
# Exclusions: one market outcome must count once
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_excluded_rows_leave_the_measured_record(db: AsyncSession):
    """`excluded_reason` marks a row instead of deleting it.

    A measured outcome is the scarcest thing the project owns, so a duplicate is
    flagged and kept — but everything that feeds a public number must skip it.
    """
    from app.services.measured_stats import measured_win_rate

    svc = AIRatingService()
    prov = await _provider(db)
    for i in range(4):
        s = await _signal(db, prov, 100.0 + i, 105.0 + i, 98.0 + i)
        s.status = SignalStatus.CLOSED_TP
        s.profit_pct = 5.0
        s.raw_message = f"real signal {i}"
    await db.commit()

    before = await measured_win_rate(db)
    assert before["closed"] == 4

    # Flag one and it must drop out of the sample.
    rows = (await db.execute(
        __import__("sqlalchemy").select(Signal).where(
            Signal.provider_id == prov.id)
    )).scalars().all()
    rows[0].excluded_reason = "duplicate"
    await db.commit()

    after = await measured_win_rate(db)
    assert after["closed"] == 3, "an excluded row still counted"
    assert rows[0].id is not None, "the row must survive, not be deleted"


@pytest.mark.asyncio
async def test_same_trade_in_two_channels_counts_once_platform_wide(db: AsyncSession):
    """Both BestStocks feeds published one HBAN loss.

    Each provider's own record is right to contain it; the platform-wide sample
    is not, because it is one observation of what the market did. Counting it
    twice overstates progress toward the MIN_SAMPLE gate.
    """
    from app.services.measured_stats import measured_win_rate

    a, b = await _provider(db), await _provider(db)
    for prov in (a, b):
        s = await _signal(db, prov, 17.91, 19.39, 17.17)
        s.status = SignalStatus.CLOSED_SL
        s.profit_pct = -4.13
        s.raw_message = "relayed idea"
    await db.commit()

    platform = await measured_win_rate(db)
    assert platform["closed"] == 1, "the relay was counted twice"
    assert platform["cross_channel_duplicates"] == 1

    # Per provider, both records stand.
    for prov in (a, b):
        one = await measured_win_rate(db, prov)
        assert one["closed"] == 1
        assert one["cross_channel_duplicates"] == 0


@pytest.mark.asyncio
async def test_provider_aggregates_skip_excluded_rows(db: AsyncSession):
    """The win rate a provider is scored on must not include a flagged row."""
    svc = AIRatingService()
    prov = await _provider(db)
    for i in range(6):
        s = await _signal(db, prov, 100.0, 105.0, 98.0)
        s.status = SignalStatus.CLOSED_TP if i else SignalStatus.CLOSED_SL
        s.profit_pct = 5.0 if i else -2.0
        if i == 0:
            s.excluded_reason = "duplicate"
    await db.commit()

    await svc.recalculate_provider_stats(db, prov.id)
    # Five wins, and the single loss was excluded.
    assert prov.win_rate == pytest.approx(1.0), \
        f"excluded loss leaked into win_rate ({prov.win_rate})"
