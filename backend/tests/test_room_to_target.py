"""Obstacles between entry and target — measured, deliberately not gated on.

The idea ("запас хода") comes from a channel analysed on 2026-10-16: before
asking whether a target is attractive, ask whether price has anywhere to go, or
whether it must first break levels it has already failed at.

Measured over the 77 replayed signals that had usable history:

    препятствий   N   win rate   ср. P&L
    0            11        36%     +1.52%
    1-2          18        11%     -6.34%
    3-5          34        21%     -3.51%
    6+           14        14%     -3.78%

Correlation with outcome was r = -0.129 — the right sign, but weak, and the
bands are not monotonic. The only firm result is that the zero-obstacle band was
the one profitable group. That is not enough to reject a signal on, so the
metric is reported by the eval harness and does not appear in signal_quality.
These tests pin the measurement, not a threshold.
"""

import pytest

from app.services.room_to_target import SWING_LOOKBACK, room, swing_levels


def _candles(highs_lows):
    return [{"high": h, "low": lo} for h, lo in highs_lows]


def test_swing_high_needs_neighbours_on_both_sides():
    """A bar at the edge of the series has no neighbourhood to dominate."""
    bars = _candles([(10, 9)] * SWING_LOOKBACK
                    + [(20, 19)]                       # the peak
                    + [(10, 9)] * SWING_LOOKBACK)
    highs, _ = swing_levels(bars)
    assert 20 in highs

    rising = _candles([(i, i - 1) for i in range(10, 20)])
    highs, _ = swing_levels(rising)
    assert 19 not in highs, "the final bar cannot be confirmed as a swing"


def test_counts_only_levels_between_entry_and_target():
    bars = _candles([(10, 9)] * SWING_LOOKBACK + [(105, 104)]
                    + [(10, 9)] * SWING_LOOKBACK + [(115, 114)]
                    + [(10, 9)] * SWING_LOOKBACK + [(130, 129)]
                    + [(10, 9)] * SWING_LOOKBACK)
    r = room(entry=100.0, target=120.0, action="buy", candles=bars)
    assert r["available"]
    assert r["obstacles"] == 2, f"expected 105 and 115, got {r}"
    assert r["first_obstacle"] == 105.0
    # 105 sits a quarter of the way from 100 to 120.
    assert r["first_obstacle_share"] == pytest.approx(0.25, abs=0.01)


def test_a_sell_looks_at_prior_lows():
    """A sell falls through prior lows, not prior highs.

    A swing LOW is a bar whose low is below its neighbours', so the surrounding
    bars here sit at 99 and the swing at 95 — one obstacle on the way from 100
    down to 90.
    """
    bars = _candles([(101, 99)] * (SWING_LOOKBACK + 1) + [(101, 95)]
                    + [(101, 99)] * (SWING_LOOKBACK + 1))
    r = room(entry=100.0, target=90.0, action="sell", candles=bars)
    assert r["available"], r
    assert r["obstacles"] == 1, r
    assert r["first_obstacle"] == 95.0


def test_clear_path_is_reported_as_such():
    bars = _candles([(10, 9)] * (SWING_LOOKBACK * 2 + 2))
    r = room(entry=100.0, target=120.0, action="buy", candles=bars)
    assert r["available"]
    assert r["obstacles"] == 0
    assert r["first_obstacle_share"] == 1.0
    assert "нет прежних экстремумов" in r["reason"]


def test_too_little_history_is_not_a_zero():
    """Absent data must not read as "clear path" — that would invert it."""
    r = room(entry=100.0, target=120.0, action="buy", candles=[{"high": 1, "low": 1}])
    assert r["available"] is False
    assert r["obstacles"] is None


def test_metric_does_not_gate_the_quality_check():
    """r = -0.129 over 77 signals is too weak to reject anything on.

    If this ever becomes a gate, it should be because the correlation held at a
    larger sample — not because the idea sounded right. R:R sounded right too,
    and measured -0.35 against outcome.
    """
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "app" / "services"
           / "signal_quality.py").read_text(encoding="utf-8")
    assert "room_to_target" not in src, \
        "room-to-target became a gate without the evidence to support one"
