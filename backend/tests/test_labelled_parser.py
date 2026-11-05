"""Signal channels publish levels; the parser has to read the labels.

Scouting 30 forex channels on 2026-11-05 found 18 posting several times a day
and yielding zero parseable setups. They were not short of levels — these are
real posts the parser could not read:

    🔥 EURCAD - SELL @ 1.56842 / SL: 1.57700 / TP: 1.55000
    #USDCAD LONG / Entry: 1.3963 / Stop Loss: 1.3942 / Take Profit: 1.3993
    AUDUSD SELL-LIMIT @0.70346 / SL: 0.70556 / TP1: 0.70147 / TP2: 0.69940
    GBPAUD BUY / Goal - 1.9274 / Recommended Stop Loss - 1.9173

Four channels, four layouts, one grammar. Two bugs found while building it are
pinned below: a regex that backtracked into its own label and reported a target
of 3.0, and a ticker search that took the channel's brand over the instrument.
"""
import pytest

from app.services.telegram import telegram_parser as T

EM = "\u2003"


def _be(p) -> float:
    risk = abs(p.entry_price - p.stop_loss)
    reward = abs(p.take_profit - p.entry_price)
    return risk / (risk + reward) * 100


@pytest.mark.parametrize("text,ticker,action", [
    ("🔥 EURCAD - SELL @ 1.56842\nSL: 1.57700\nTP: 1.55000", "EURCAD", "sell"),
    ("#USDCAD FREE SIGNAL LONG🚀\n⭐️Entry: 1.3963\n⭐️Stop Loss: 1.3942\n"
     "⭐️Take Profit: 1.3993", "USDCAD", "buy"),
    ("AUDUSD SELL-LIMIT @0.70346\nSL: 0.70556\nTP1: 0.70147\nTP2: 0.69940",
     "AUDUSD", "sell"),
    ("🔥 XAUUSD - BUY LIMIT @ 4035.00\nSL: 4022.00\nTP: 4055.00", "XAUUSD", "buy"),
])
def test_real_channel_layouts_parse(text, ticker, action):
    p = T.parse_message(text)
    assert p is not None, "канал с полными уровнями снова читается как пустой"
    assert p.ticker == ticker and p.action == action
    assert p.entry_price and p.take_profit and p.stop_loss


def test_multi_target_posts_do_not_read_the_index_as_the_price():
    """BUG: "TP3 → 3990" matched the label "TP", backtracked, and returned 3.0.

    It surfaced as a channel whose average breakeven share was 0% — a number
    that cannot exist, which is the only reason it was noticed.
    """
    p = T.parse_message(
        f"🏛️ XAUHQ | XAU SIGNAL 🟡 DIRECTION: 📉 SELL NOW ENTRY: 4033/47 "
        f"STOP LOSS: 4057🛡️ TAKE PROFIT: {EM}TP1 → 4020 {EM}TP2 → 4005 "
        f"{EM}TP3 → 3990")
    assert p is not None
    assert p.take_profit > 3000, f"цель {p.take_profit} — индекс прочитан как цена"
    assert 20 < _be(p) < 80


def test_the_instrument_wins_over_the_channel_brand():
    """BUG: "XAUHQ | XAU SIGNAL" parsed onto ticker XAUHQ, which nothing prices."""
    p = T.parse_message(
        f"🏛️ XAUHQ | XAU SIGNAL SELL NOW ENTRY: 4033 STOP LOSS: 4057 "
        f"TAKE PROFIT: {EM}TP1 → 4020 {EM}TP2 → 4005")
    assert p.ticker == "XAUUSD"


def test_bare_metal_codes_resolve():
    assert T.parse_message("GOLD BUY\nEntry: 4030\nSL: 4010\nTP: 4070").ticker == "XAUUSD"


def test_second_target_is_used_when_several_are_given():
    """TP1 is usually a few pips out; pricing off it makes every setup look
    like it needs a 90% win rate."""
    p = T.parse_message("AUDUSD SELL @0.70346\nSL: 0.70556\nTP1: 0.70300\n"
                        "TP2: 0.69940\nTP3: 0.69704")
    assert p.take_profit == pytest.approx(0.69940)


def test_a_results_recap_is_not_a_signal():
    """These posts name pairs, directions and numbers, and are history."""
    assert T.parse_message(
        "🔼Weekly Performance🔼\n⭕Gold sell +315 tp hit\n⭕Eurusd buy +80 tp hit\n"
        "🚫Usdchf sell -42 sl hit") is None


def test_direction_and_levels_must_agree():
    """A buy whose stop sits above its target is a misread, not a brave trade."""
    assert T.parse_labelled_levels(
        "#EURUSD BUY\nEntry: 1.10\nStop Loss: 1.12\nTake Profit: 1.08") is None


def test_analysis_without_an_entry_is_kept_as_derived():
    """Direction + target + stop, no entry — resolve_levels anchors it live.

    Without this a channel posting nine times a day reads as empty.
    """
    p = T.parse_message("✍️GBPAUD On The Rise! BUY!\nBias - Bullish\n"
                        "⭐️Goal - 1.9274\n⭐️Recommended Stop Loss - 1.9173\n#GBPAUD")
    assert p is not None and p.derived_levels is True
    assert p.stop_loss < p.take_profit


def test_a_label_without_a_number_yields_nothing():
    assert T.parse_labelled_levels("#EURUSD BUY\nEntry:\nStop Loss:\nTP:") is None
