"""The statistics that decide whether an advisor is worth anything.

Two single backtests disagreed completely — S5 led one by +2.79% a trade and
lost 0.29% in the other, where S3 led. A harness built to settle that argument
can settle it wrongly in several quiet ways, so each is pinned here:

  * a bootstrap that is not reproducible turns "p = 0.099" into a number that
    changes when you rerun it;
  * a Bonferroni threshold that forgets how many advisors were tested calls a
    1-in-6 fluke a discovery;
  * windows that overlap, or that take their warm-up from inside themselves,
    stop being independent evidence.
"""
import statistics
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import advisor_robustness as rb  # noqa: E402


# ── the bootstrap ──────────────────────────────────────────────────────────

def test_bootstrap_is_reproducible():
    """A p-value that moves between runs is not a p-value."""
    returns = [1.0, -2.0, 3.0, -0.5, 0.2, 4.0, -1.1, 0.9]
    assert rb._bootstrap_p(returns) == rb._bootstrap_p(returns)


def test_bootstrap_rejects_a_clearly_losing_record():
    assert rb._bootstrap_p([-1.0] * 40) == pytest.approx(1.0)


def test_bootstrap_accepts_a_clearly_winning_record():
    assert rb._bootstrap_p([2.0] * 40) == pytest.approx(0.0)


def test_bootstrap_is_unconvinced_by_a_coin_flip():
    """Symmetric returns must not look like an edge in either direction."""
    p = rb._bootstrap_p([1.0, -1.0] * 30)
    assert 0.2 < p < 0.8, f"p={p} — симметричные доходности выдаются за сигнал"


def test_bootstrap_needs_more_than_one_trade():
    assert rb._bootstrap_p([5.0]) == 1.0
    assert rb._bootstrap_p([]) == 1.0


def test_the_bootstrap_alone_cannot_see_a_tiny_sample():
    """Its blind spot, stated rather than hoped away.

    If every observed trade won, every resample of them wins too, so three
    lucky trades return p = 0.000 — the same p as three hundred. Resampling
    measures how fragile the mean is to WHICH trades occurred, not how few
    there were. Hence MIN_TRADES.
    """
    assert rb._bootstrap_p([9.0, 8.0, 7.0]) == 0.0
    assert rb._bootstrap_p([9.0, 8.0, 7.0] * 100) == 0.0


def test_a_floor_on_the_trade_count_is_what_stops_it():
    assert rb.MIN_TRADES >= 30, (
        "порог ниже 30 пустил бы случайную серию выигрышей за преимущество"
    )
    from app.services.measured_stats import MIN_SAMPLE
    assert rb.MIN_TRADES == MIN_SAMPLE, (
        "порог достоверности должен быть один на весь проект"
    )


# ── the multiple-comparison correction ─────────────────────────────────────

def test_the_threshold_is_divided_by_the_number_of_advisors():
    """Six advisors mean ~26% odds that one clears 0.05 by luck."""
    from app.services.advisors import ADVISORS
    tested = sum(1 for a in ADVISORS if a.replayable)
    assert tested == 6
    assert rb.ALPHA / tested == pytest.approx(0.00833, abs=0.0001)


def test_s7_is_not_counted_among_the_tested():
    """Counting an advisor that was never measured loosens the threshold."""
    from app.services.advisors import ADVISORS
    assert not next(a for a in ADVISORS if a.id == "S7").replayable


# ── the replay rules, same as the single-period run ────────────────────────

def _bar(c, h=None, l=None):
    return {"open": c, "high": h if h is not None else c,
            "low": l if l is not None else c, "close": c, "volume": 1000.0,
            "begin": "2026-01-01 00:00"}


def test_a_bar_covering_both_levels_counts_as_a_stop():
    candles = [_bar(100.0), _bar(100.0, h=120.0, l=80.0)]
    assert rb._walk_forward(candles, 0, "buy", 100.0, 108.0, 96.0)[0] == "sl"


def test_pnl_is_signed_against_the_direction():
    assert rb._pct("sell", 100.0, 90.0) == pytest.approx(10.0)
    assert rb._pct("buy", 100.0, 90.0) == pytest.approx(-10.0)


def test_an_unresolved_trade_expires_rather_than_counting_as_open():
    candles = [_bar(100.0)] + [_bar(100.0) for _ in range(30)]
    reason, _, bars = rb._walk_forward(candles, 0, "buy", 100.0, 200.0, 50.0)
    assert reason == "expired" and bars == rb.MAX_BARS_OPEN


def test_a_trade_with_no_future_bars_is_left_open_not_scored():
    """Scoring it at entry would add a free 0% to the record."""
    assert rb._walk_forward([_bar(100.0)], 0, "buy", 100.0, 110.0, 90.0)[0] == "open"


# ── window arithmetic ──────────────────────────────────────────────────────

def test_windows_are_non_overlapping_and_leave_room_for_warm_up():
    """The slicing in main(), stated as arithmetic so it cannot drift."""
    length, windows = 1101, 6
    usable = length - rb.MIN_CANDLES - rb.MAX_BARS_OPEN
    size = usable // windows

    spans = []
    for w in range(windows):
        lo = rb.MIN_CANDLES + w * size
        spans.append((lo, lo + size))

    assert spans[0][0] >= rb.MIN_CANDLES, "первое окно начинается до прогрева"
    for (a_lo, a_hi), (b_lo, b_hi) in zip(spans, spans[1:]):
        assert a_hi <= b_lo, "окна пересекаются — это не независимые замеры"
    assert spans[-1][1] <= length - rb.MAX_BARS_OPEN, \
        "последнее окно уходит за данные, нужные для доигрывания сделок"


# ── out-of-sample mode ─────────────────────────────────────────────────────

def _fake_trades(per_advisor: dict[str, list[list[float]]]) -> dict:
    """trades[id][window] -> returns, for advisors named in `per_advisor`."""
    from app.services.advisors import ADVISORS
    windows = max(len(v) for v in per_advisor.values())
    out = {}
    for a in ADVISORS:
        if not a.replayable:
            continue
        rows = per_advisor.get(a.id, [[] for _ in range(windows)])
        out[a.id] = {w: list(rows[w]) if w < len(rows) else []
                     for w in range(windows)}
    return out


def test_report_passes_a_consistent_winner(capsys):
    winner = [[2.0] * 20, [1.5] * 20, [2.5] * 20, [1.0] * 20]
    survivors = _report_quiet(_fake_trades({"S5": winner}), 4)
    capsys.readouterr()
    assert [a.id for a, *_ in survivors] == ["S5"]


def test_report_rejects_an_advisor_that_wins_only_one_window():
    """Four windows, one huge win and three losses — pooled mean can still be
    positive, and that is exactly what must not pass."""
    streaky = [[30.0] * 20, [-2.0] * 20, [-2.0] * 20, [-2.0] * 20]
    assert _report_quiet(_fake_trades({"S1": streaky}), 4) == []


def test_report_rejects_a_small_sample_however_good():
    tiny = [[5.0] * 5, [5.0] * 5, [5.0] * 5, [5.0] * 5]   # 20 trades < MIN_TRADES
    assert _report_quiet(_fake_trades({"S4": tiny}), 4) == []


def test_report_rejects_a_result_that_only_clears_the_uncorrected_alpha():
    """Six advisors are tested, so 0.05 is the wrong bar — 0.0083 is."""
    import random
    rng = random.Random(7)
    marginal = [[rng.gauss(0.35, 3.0) for _ in range(25)] for _ in range(4)]
    survivors = _report_quiet(_fake_trades({"S3": marginal}), 4)
    p = rb._bootstrap_p([r for w in marginal for r in w])
    if rb.ALPHA / 6 <= p < rb.ALPHA:
        assert survivors == [], "прошёл по нескорректированному порогу"


def _report_quiet(trades, windows):
    return rb._report(trades, windows, quiet=True)
