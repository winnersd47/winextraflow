"""Tags must be plentiful, valid, and the first thing to give way.

Cards carried three tags — `#TICKER #market #WinExtraFlow` — so a reader could
find one instrument and nothing else. The list is much longer now, which
creates the opposite risk: a card goes out as a photo or video caption, where
Telegram allows 1024 characters rather than 4096, and this project has already
lost every geometry-carrying card to MEDIA_CAPTION_TOO_LONG without noticing.

So the tests below check both directions — that the tags are actually there,
and that they can never push the trading content out of the caption.
"""
import re

import pytest

from app.services.signal_chart import CAPTION_LIMIT, build_caption
from app.services.signal_clip import build_clip_caption
from app.services.signal_tags import build_tags, fit, tag_line

RICH = {"verdict": "GOOD", "regime_strategy": "Trend Following",
        "pyramid_levels": 3, "metrics_available": True,
        "ev_per_trade_pct": 1.2, "profit_factor": 2.1,
        "kelly_half_pct": 2.5, "edge_pct": 8.4}
GEOMETRY = {"tp_mult": 4.0, "sl_mult": 2.0, "hit_rate_pct": 31.0,
            "breakeven_pct": 33.3, "samples": 180}

SHAPES = [
    ("EURJPY", "sell", 176.116, 174.9, 177.443, 76),
    ("XAUUSD", "buy", 4010.0, 4060.0, 3985.0, 68),
    ("RTS-12.26", "buy", 96860.0, 97330.0, 96720.0, 79),
    ("BTCUSDT", "buy", 68000.0, 72000.0, 66000.0, 83),
    ("SBER", "buy", 300.0, 330.0, 285.0, 72),
    ("CVX", "buy", 150.0, 174.0, 145.0, 68),
]

# Telegram ends a hashtag at the first character outside this set.
_VALID = re.compile(r"^#[0-9A-Za-zА-Яа-яЁё_]+$")


@pytest.mark.parametrize("ticker,action,entry,tp,sl,wef", SHAPES)
def test_every_tag_is_a_tag_telegram_will_render(ticker, action, entry, tp, sl, wef):
    """`#RTS-12.26` renders as `#RTS` plus loose text `-12.26`."""
    for tag in build_tags(ticker, action, wef):
        assert _VALID.match(tag), f"{tag} — Telegram оборвёт этот тег"


@pytest.mark.parametrize("ticker,action,entry,tp,sl,wef", SHAPES)
def test_card_stays_inside_the_caption_limit(ticker, action, entry, tp, sl, wef):
    cap = build_caption(ticker, action, entry, tp, sl, wef, trend="up",
                        recent_change=1.2, expert=RICH, geometry=GEOMETRY)
    assert len(cap) <= CAPTION_LIMIT, (
        f"{ticker}: {len(cap)} символов — карточку отклонит "
        f"MEDIA_CAPTION_TOO_LONG, и сигнал не опубликуется"
    )


@pytest.mark.parametrize("teaser", [True, False])
@pytest.mark.parametrize("ticker,action,entry,tp,sl,wef", SHAPES)
def test_clip_caption_stays_inside_the_limit(ticker, action, entry, tp, sl, wef, teaser):
    cap = build_clip_caption(ticker, action, entry, tp, sl, wef, teaser=teaser)
    assert len(cap) <= CAPTION_LIMIT


@pytest.mark.parametrize("ticker,action,entry,tp,sl,wef", SHAPES)
def test_tags_give_way_before_the_analysis(ticker, action, entry, tp, sl, wef):
    """The conclusion is the card's point; "#investing" is not."""
    cap = build_caption(ticker, action, entry, tp, sl, wef, trend="up",
                        recent_change=1.2, expert=RICH, geometry=GEOMETRY)
    assert "Вывод:" in cap
    conclusion = cap.split("Вывод:", 1)[1].split("\n", 1)[0].strip()
    assert len(conclusion) > 20, (
        f"{ticker}: вывод ужался до «{conclusion}» — теги забрали бюджет"
    )
    # And the levels, which are never negotiable.
    for must in ("Вход:", "Цель:", "Стоп:"):
        assert must in cap


@pytest.mark.parametrize("ticker,action,entry,tp,sl,wef", SHAPES)
def test_a_card_carries_far_more_than_the_old_three_tags(ticker, action, entry, tp, sl, wef):
    cap = build_caption(ticker, action, entry, tp, sl, wef, trend="up",
                        recent_change=1.2, expert=RICH, geometry=GEOMETRY)
    line = cap.rsplit("\n", 1)[-1]
    assert line.count("#") >= 10, f"{ticker}: в карточке всего {line.count('#')} тегов"


def test_the_instrument_comes_first():
    """Trimming cuts from the end, so the ticker must never be what is cut."""
    for ticker, action, *_ , wef in SHAPES:
        assert build_tags(ticker, action, wef)[0].startswith("#"), ticker
        assert ticker.split("-")[0].upper() in build_tags(ticker, action, wef)[0].upper()


def test_brand_survives_a_budget_that_fits_almost_nothing():
    tags = build_tags("EURJPY", "sell", 76)
    assert fit(tags, 20).endswith("#WinExtraFlow")
    assert fit(tags, 0) == ""


def test_currency_pair_is_searchable_by_each_side():
    tags = build_tags("EURJPY", "sell", 76)
    assert "#EUR" in tags and "#JPY" in tags


def test_gold_is_findable_by_name():
    """Readers follow «золото», not XAUUSD."""
    tags = build_tags("XAUUSD", "buy", 70)
    assert "#золото" in tags and "#gold" in tags


def test_direction_is_tagged_in_both_languages():
    assert {"#шорт", "#short"} <= set(build_tags("EURJPY", "sell", 76))
    assert {"#лонг", "#long"} <= set(build_tags("EURJPY", "buy", 76))


def test_score_is_banded_not_exact():
    """`#WEF76` would be a tag with one post in it."""
    assert "#WEF80плюс" in build_tags("SBER", "buy", 83)
    assert "#WEF70плюс" in build_tags("SBER", "buy", 72)
    assert not any(re.fullmatch(r"#WEF\d+", t) for t in build_tags("SBER", "buy", 83))


def test_no_duplicate_tags():
    for ticker, action, *_, wef in SHAPES:
        tags = [t.lower() for t in build_tags(ticker, action, wef)]
        assert len(tags) == len(set(tags)), ticker


def test_tag_line_never_exceeds_its_budget():
    for budget in (0, 1, 15, 40, 120, 240, 1000):
        assert len(tag_line("BTCUSDT", "buy", 83, budget=budget)) <= budget
