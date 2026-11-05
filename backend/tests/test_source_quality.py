"""Comparing a source to chance is only meaningful on matched terms.

The first run of scripts/source_quality.py reported both real sources as far
worse than random — 9.2% against 33.8%. The sources were not that bad; the
comparison was rigged two ways at once:

  * it gave each signal 15 bars to resolve while the baseline gives its random
    entries 30, so trades that would have reached target in bar 20 were counted
    as failures on one side and never attempted on the other;
  * it divided wins by EVERY outcome, including expiries, while the baseline
    divides by resolved cases only. An expiry counted against the source and
    against nothing on the baseline.

Corrected, the same data reads 26.2% against 33.9% — still below chance, but by
a quarter of the gap first reported. Both tests below exist so the terms cannot
drift apart again.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import source_quality as sq  # noqa: E402


def _bar(c, h=None, l=None):
    return {"open": c, "high": h if h is not None else c,
            "low": l if l is not None else c, "close": c, "volume": 1.0,
            "begin": "2026-01-01 00:00"}


# ── matched terms ──────────────────────────────────────────────────────────

def test_the_horizon_matches_the_baseline():
    from app.services.signal_geometry import MAX_BARS_TO_RESOLVE
    assert sq.BASELINE_BARS == MAX_BARS_TO_RESOLVE, (
        "горизонт разошёлся с базовой линией — сравнение снова станет нечестным"
    )


def test_the_default_hold_is_the_baseline_horizon():
    """Argparse default, since that is what every unattended run uses."""
    import argparse
    import inspect
    src = inspect.getsource(sq.main)
    assert "default=BASELINE_BARS" in src
    assert isinstance(sq.BASELINE_BARS, int) and sq.BASELINE_BARS >= 15


def test_win_rate_counts_resolved_trades_only():
    """The baseline drops undecided cases, so this must too."""
    import inspect
    src = inspect.getsource(sq.main)
    assert "resolved = tp + sl" in src, \
        "win rate снова считается от всех исходов, включая истёкшие"
    assert "tp / resolved" in src


# ── outcome walking ────────────────────────────────────────────────────────

def test_target_reached_is_a_win():
    candles = [_bar(105.0, h=112.0, l=104.0)]
    reason, pct = sq._outcome(candles, 100.0, 108.0, 96.0, "buy", 30)
    assert reason == "tp" and pct == pytest.approx(8.0)


def test_stop_hit_is_a_loss_and_bounded_by_the_stop():
    candles = [_bar(95.0, h=99.0, l=90.0)]
    reason, pct = sq._outcome(candles, 100.0, 108.0, 96.0, "buy", 30)
    assert reason == "sl" and pct == pytest.approx(-4.0)


def test_a_bar_covering_both_levels_counts_as_a_stop():
    """Daily bars do not say which came first — the same rule as every other
    replay in this project."""
    candles = [_bar(100.0, h=120.0, l=80.0)]
    assert sq._outcome(candles, 100.0, 108.0, 96.0, "buy", 30)[0] == "sl"


def test_a_sell_is_scored_against_its_direction():
    candles = [_bar(92.0, h=94.0, l=91.0)]
    reason, pct = sq._outcome(candles, 100.0, 92.0, 104.0, "sell", 30)
    assert reason == "tp" and pct == pytest.approx(8.0)


def test_nothing_resolved_within_the_horizon_expires():
    candles = [_bar(100.5, h=101.0, l=100.0) for _ in range(40)]
    reason, pct = sq._outcome(candles, 100.0, 150.0, 50.0, "buy", 30)
    assert reason == "expired" and pct == pytest.approx(0.5)


def test_the_horizon_is_respected_not_the_whole_series():
    """A target reached after the horizon is not a win."""
    quiet = [_bar(100.0, h=101.0, l=99.0) for _ in range(30)]
    late_win = [_bar(110.0, h=115.0, l=109.0)]
    assert sq._outcome(quiet + late_win, 100.0, 108.0, 96.0, "buy", 30)[0] == "expired"


def test_no_candles_leaves_the_trade_open_rather_than_scoring_it():
    """Scoring it at entry would add a free 0% to the source's record."""
    assert sq._outcome([], 100.0, 108.0, 96.0, "buy", 30)[0] == "open"
