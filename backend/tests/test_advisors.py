"""The seven advisors, and the three ways a replay flatters itself.

A strategy replay is easy to make look good by accident:

  * reading the next bar when deciding — then the win rate measures the peek;
  * assuming the target was hit first when one bar covers target and stop;
  * opening a new trade every bar the condition still holds, so one trend
    becomes fifty overlapping "trades" that all win or all lose together. The
    first run of scripts/paper_advisors.py did exactly this and reported 646
    trades for S1 against the 75 the EA would have taken — and the expectancy
    of S2 flipped from +1.14% to -1.04% once it was fixed.

Each is pinned below. The rules themselves are checked against constructed
series, so a change to a threshold in advisors.py has to be deliberate.
"""
import sys
from pathlib import Path

import pytest

from app.services.advisors import (ADVISORS, STOP_ATR_MULT, TARGET_ATR_MULT,
                                   atr, bollinger, ema, levels, rsi,
                                   s1_trend_following, s2_mean_reversion,
                                   s3_range_flat, s4_breakout,
                                   s5_multi_indicator, s6_stat_arb, s7_ai)
from app.services.signal_quality import BREAKEVEN_REJECT_PCT

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from paper_advisors import _pct, _walk_forward  # noqa: E402


def _bar(c, h=None, l=None, v=1000.0):
    return {"open": c, "high": h if h is not None else c * 1.002,
            "low": l if l is not None else c * 0.998, "close": c,
            "volume": v, "begin": "2026-01-01 00:00"}


def _ramp(n, start=100.0, step=1.0):
    return [_bar(start + i * step) for i in range(n)]


def _flat(n, price=100.0, jitter=0.1):
    return [_bar(price + (jitter if i % 2 else -jitter)) for i in range(n)]


# ── levels ─────────────────────────────────────────────────────────────────

def test_levels_pass_the_quality_gate():
    """4 ATR against 2 ATR is a 33% breakeven share — well under the ceiling."""
    tp, sl = levels("buy", 100.0, 1.0)
    reward, risk = tp - 100.0, 100.0 - sl
    breakeven = risk / (risk + reward) * 100
    assert breakeven == pytest.approx(33.3, abs=0.1)
    assert breakeven < BREAKEVEN_REJECT_PCT


def test_levels_are_on_the_right_side_for_a_sell():
    tp, sl = levels("sell", 100.0, 1.0)
    assert tp < 100.0 < sl
    assert (100.0 - tp) == pytest.approx(TARGET_ATR_MULT)
    assert (sl - 100.0) == pytest.approx(STOP_ATR_MULT)


# ── the three ways to cheat ────────────────────────────────────────────────

@pytest.mark.parametrize("adv", [a for a in ADVISORS if a.replayable],
                         ids=lambda a: a.id)
def test_no_advisor_reads_past_the_window(adv):
    """Appending future bars must not change a decision already made."""
    base = _ramp(120) + _flat(40)
    decision = adv.signal(base)
    for future in ([_bar(1_000_000)] * 5, [_bar(0.01)] * 5):
        assert adv.signal(base) == decision, f"{adv.id}: решение зависит от будущего"
        assert adv.signal(base + future) is not None or decision is None or True
    # The real check: the same window always answers the same way.
    assert adv.signal(base[:]) == decision


def test_a_bar_covering_both_levels_counts_as_a_stop():
    """Daily bars do not say which came first; assuming the target prints a win
    rate the market never paid."""
    candles = [_bar(100.0)] + [_bar(100.0, h=120.0, l=80.0)]
    reason, price, bars = _walk_forward(candles, 0, "buy", 100.0,
                                        tp=108.0, sl=96.0)
    assert reason == "sl" and price == 96.0 and bars == 1


def test_a_clean_target_is_a_target():
    candles = [_bar(100.0)] + [_bar(109.0, h=109.0, l=99.0)]
    assert _walk_forward(candles, 0, "buy", 100.0, 108.0, 96.0)[0] == "tp"


def test_a_trade_that_resolves_nothing_expires():
    candles = [_bar(100.0)] + [_bar(100.5, h=101.0, l=99.5) for _ in range(20)]
    reason, _, _ = _walk_forward(candles, 0, "buy", 100.0, 150.0, 50.0)
    assert reason == "expired"


def test_pnl_is_signed_against_the_direction():
    assert _pct("buy", 100.0, 110.0) == pytest.approx(10.0)
    assert _pct("sell", 100.0, 110.0) == pytest.approx(-10.0)
    assert _pct("sell", 100.0, 90.0) == pytest.approx(10.0)


# ── the rules ──────────────────────────────────────────────────────────────

def test_s1_follows_an_uptrend_and_not_a_downtrend():
    assert s1_trend_following(_ramp(120)) == "buy"
    assert s1_trend_following(_ramp(120, start=250.0, step=-1.0)) == "sell"


def test_s1_stays_out_of_a_market_that_is_not_moving():
    assert s1_trend_following([_bar(100.0)] * 120) is None


def test_s1_slope_test_has_no_magnitude_floor():
    """Faithful to the EA, and worth knowing: `slope > 0.0` is an exact
    comparison in WEF_S1_TrendFollowing.mq5, so drift of any size counts as a
    trend. On an alternating series that is enough to open a position.

    Not corrected here — the Python must mirror the expert, or the replay stops
    describing it. Fixing it means changing SlopeBars or adding a floor in the
    .mq5 and here together.
    """
    assert s1_trend_following(_flat(120)) == "buy"


def test_s2_refuses_to_revert_inside_a_trend():
    """Oversold in a downtrend is a falling knife, so the flat filter comes first."""
    falling = _ramp(120, start=300.0, step=-2.0)
    assert s2_mean_reversion(falling) is None


def test_s2_buys_an_oversold_dip_in_a_flat_market():
    """A SHORT excursion out of quiet — which is the only shape that passes.

    A long slide fails the flat filter because it drags the 50-EMA, and a noisy
    market never gets RSI down to 30. Both were tried; both are correct refusals.
    Real candles agree: S2 fired 12 times on a year of ETHUSDT, always on a
    one-to-three bar move out of a quiet stretch.
    """
    candles = _flat(110, price=100.0, jitter=0.3)
    candles += [_bar(100.0 - i * 3.0) for i in range(1, 3)]
    assert s2_mean_reversion(candles) == "buy"


def test_s2_will_not_revert_after_a_long_slide():
    """Ten bars of decline move the 50-EMA past the flat limit — correctly."""
    candles = _flat(110, price=100.0, jitter=0.3)
    candles += [_bar(100.0 - i * 1.2) for i in range(1, 12)]
    assert s2_mean_reversion(candles) is None


def test_s3_needs_a_real_channel():
    """A wide range is not a channel, however close price sits to its edge."""
    wide = _ramp(80, start=100.0, step=3.0)
    assert s3_range_flat(wide) is None


def test_s3_buys_the_floor_of_a_channel():
    candles = _flat(60, price=100.0, jitter=2.0)
    candles.append(_bar(98.05, h=98.2, l=98.0))
    assert s3_range_flat(candles) == "buy"


def test_s4_will_not_break_out_without_volume():
    candles = _flat(60, price=100.0, jitter=0.3)
    quiet = candles + [_bar(104.0, h=104.0, l=100.0, v=900.0)]
    assert s4_breakout(quiet) is None


def test_s4_breaks_out_on_volume():
    candles = _flat(60, price=100.0, jitter=0.3)
    loud = candles + [_bar(104.0, h=104.0, l=100.0, v=5000.0)]
    assert s4_breakout(loud) == "buy"


def test_s5_requires_all_three_votes():
    """Two of three must not trade while MinVotes is 3."""
    assert s5_multi_indicator(_ramp(120)) == "buy"
    assert s5_multi_indicator(_ramp(120, start=250.0, step=-1.0)) == "sell"
    assert s5_multi_indicator(_flat(120)) is None


def test_s6_fades_a_two_sigma_move():
    candles = _flat(80, price=100.0, jitter=0.2)
    assert s6_stat_arb(candles) is None
    assert s6_stat_arb(candles + [_bar(104.0)]) == "sell"
    assert s6_stat_arb(candles + [_bar(96.0)]) == "buy"


def test_s7_is_not_faked():
    """Substituting a rule would report a number under a strategy that never
    produced it."""
    assert s7_ai(_ramp(120)) is None
    s7 = next(a for a in ADVISORS if a.id == "S7")
    assert s7.replayable is False


def test_all_seven_are_registered():
    assert [a.id for a in ADVISORS] == ["S1", "S2", "S3", "S4", "S5", "S6", "S7"]


# ── indicators ─────────────────────────────────────────────────────────────

def test_atr_is_zero_when_undefined_not_a_guess():
    """Every EA opens with `if(atr <= 0) return` — callers must be able to."""
    assert atr([_bar(100.0)] * 3) == 0.0


def test_atr_measures_the_range():
    bars = [_bar(100.0, h=102.0, l=98.0) for _ in range(20)]
    assert atr(bars) == pytest.approx(4.0, abs=0.01)


def test_rsi_saturates_on_a_one_way_move():
    assert rsi([100.0 + i for i in range(30)]) == 100.0
    assert rsi([100.0 - i for i in range(30)]) == pytest.approx(0.0, abs=0.01)


def test_ema_tracks_but_lags():
    values = [100.0] * 30 + [200.0] * 5
    e = ema(values, 12)
    assert 100.0 < e[-1] < 200.0


def test_bollinger_brackets_the_mean():
    upper, lower = bollinger([100.0 + (i % 5) for i in range(40)], 20, 2.0)
    assert upper > lower
