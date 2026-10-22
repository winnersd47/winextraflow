"""The pinned-levels layout, and which of its targets the platform takes.

A channel audited on 2026-10-22 published 90 complete setups that the parser
read as nothing: the entry is marked with an emoji rather than "@", it is a
range rather than a price, and "Stop loss (SL):" puts a parenthetical between
the label and the number.

Which target to use was measured, not chosen. Replaying 25 of those setups
against candles:

    цель   дошло   win rate   ср. R:R   ожидание
    TP1      8/25       32%      0.49    -0.029%
    TP2      8/25       32%      1.07    +0.020%
    TP3      5/23       22%      1.67    +0.022%
    TP4      4/13       31%      2.34    +0.291%

The nearest target is the only losing one — reached no more often than the
second and paying half as much. It also needs 67% of trades to win, which the
quality gate rejects; the second needs 48% and passes.
"""

import pytest

from app.services.telegram import telegram_parser as P

SELL = """Ловите сделку🫡

SELL XAUUSD

📍4207-4209

✅Take profit 1: 4204
✅Take profit 2: 4200
✅Take profit 3: 4182
✅Take profit 4: 4163

❗️Stop loss (SL): 4226"""

BUY = """Доброго утра, бойцы! Ловите сделку🫡

BUY GBPUSD
📍1.33741-1.33770

✅Take profit 1: 1.33856
✅Take profit 2: 1.33908
✅Take profit 3: 1.34057
✅Take profit 4: 1.34384

❗️Stop loss (SL): 1.33456"""

SINGLE_ENTRY = """BUY EURUSD
📍1.18650

✅Take profit 1: 1.18700
✅Take profit 2: 1.18800

❗️Stop loss (SL): 1.18500"""


def test_reads_a_layout_the_generic_patterns_miss():
    s = P.parse_message(SELL)
    assert s is not None, "the pinned-levels layout still parses as nothing"
    assert s.ticker == "XAUUSD"
    assert s.action == "sell"


def test_entry_range_becomes_its_midpoint():
    """Taking the near edge would quietly assume the best fill in the range."""
    s = P.parse_message(SELL)
    assert s.entry_price == pytest.approx(4208.0)       # (4207 + 4209) / 2

    b = P.parse_message(BUY)
    assert b.entry_price == pytest.approx(1.337555, abs=1e-6)


def test_single_entry_is_not_broken_by_the_range_support():
    s = P.parse_message(SINGLE_ENTRY)
    assert s.entry_price == pytest.approx(1.18650)


def test_stop_survives_the_parenthetical():
    """"Stop loss (SL): 4226" — the brackets defeated the generic patterns."""
    assert P.parse_message(SELL).stop_loss == pytest.approx(4226.0)
    assert P.parse_message(BUY).stop_loss == pytest.approx(1.33456)


def test_takes_the_second_target_not_the_first():
    """Measured: the nearest target is the only losing choice."""
    s = P.parse_message(SELL)
    assert s.take_profit == pytest.approx(4200.0), \
        f"expected TP2 (4200), got {s.take_profit}"

    b = P.parse_message(BUY)
    assert b.take_profit == pytest.approx(1.33908), \
        f"expected TP2 (1.33908), got {b.take_profit}"


def test_second_target_clears_the_quality_gate():
    """TP1 needs 67% of trades to win and is rejected; TP2 needs 48%."""
    s = P.parse_message(SELL)
    reward = s.entry_price - s.take_profit        # a sell
    risk = s.stop_loss - s.entry_price
    breakeven = risk / (reward + risk) * 100

    from app.services.signal_quality import BREAKEVEN_REJECT_PCT
    assert breakeven < BREAKEVEN_REJECT_PCT, \
        f"the chosen target needs {breakeven:.0f}% wins — the gate rejects it"


def test_falls_back_to_the_only_target_when_there_is_one():
    text = """BUY EURUSD
📍1.18650

✅Take profit: 1.18900

❗️Stop loss (SL): 1.18500"""
    s = P.parse_message(text)
    assert s is not None
    assert s.take_profit == pytest.approx(1.18900)


def test_targets_on_the_wrong_side_are_refused():
    """A sell whose targets sit above entry is a misread, not a trade."""
    text = """SELL XAUUSD
📍4207-4209

✅Take profit 1: 4250
✅Take profit 2: 4280

❗️Stop loss (SL): 4190"""
    assert P.parse_message(text) is None


def test_commentary_about_trades_is_not_a_trade():
    """The channel also explains HOW to enter; that is prose, not a setup."""
    text = ("Как входить в сделки с нами? Для тех у кого не было опыта — "
            "BUY LIMIT это значит мы покупаем ровно по той цене, которую "
            "я указал. Take profit ставим заранее.")
    assert P.parse_message(text) is None
