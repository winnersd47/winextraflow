"""What Telegram will actually accept.

The signal card is sent as a photo or video caption, where the limit is 1024 —
not the 4096 a plain message gets. Measured: the card ran 954-989 characters
without the geometry baseline and 1123-1158 with it, so every card carrying that
block was rejected with MEDIA_CAPTION_TOO_LONG. `broadcast_card` logged the
failure and returned None, which the pipeline read as "not published" — the
signal was dropped and nobody saw an error outside the log.

That is the failure mode these tests exist for: sending does not raise, it just
quietly does not happen. The other one is `parse_mode: HTML`, which rejects the
whole message over a single unescaped `&` or `<`.
"""

import re

import pytest

from app.services.signal_chart import CAPTION_LIMIT, build_caption

# Telegram's HTML parse mode accepts only these tags.
ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del",
                "span", "tg-spoiler", "a", "code", "pre", "blockquote", "tg-emoji"}

GEOMETRY = {"enough_data": True, "hit_rate_pct": 36.3, "breakeven_pct": 33.3,
            "occurrences": 412, "reached_target": 150,
            "tp_mult": 4.0, "sl_mult": 2.0}
# The longest phrasing the geometry block can produce.
GEOMETRY_LOSING = {**GEOMETRY, "hit_rate_pct": 28.0}
EXPERT = {"metrics_available": True, "ev_per_trade_pct": 1.84,
          "profit_factor": 1.62, "edge_pct": 12.4, "kelly_half_pct": 3.1,
          "win_rate_used": 41.2}
NO_METRICS = {"metrics_available": False, "metrics_reason":
              "Мат. ожидание не рассчитано: измеренных сделок 10, нужно 30. "
              "Считать его от предполагаемого win rate значит выдавать "
              "допущение за расчёт."}

# Ticker, action, entry, tp, sl, wef — chosen to stretch the caption: long
# symbols, six-figure prices, and eight-decimal crypto all widen the number
# formatting that pushed earlier versions over the limit.
SHAPES = [
    ("SBER", "buy", 278.07, 289.0, 272.5, 89),
    ("GAZR-9.26", "sell", 123456.78, 118000.0, 126500.0, 96),
    ("1000PEPEUSDT", "buy", 0.00001234, 0.00001456, 0.00001180, 96),
    ("BTCUSDT", "buy", 123456.78, 148148.14, 111111.10, 96),
    ("SBER", "sell", 278.07, 265.0, 284.0, 89),
]


def _captions():
    for shape in SHAPES:
        for geom in (GEOMETRY, GEOMETRY_LOSING, None):
            for expert in (EXPERT, NO_METRICS, None):
                yield shape, build_caption(*shape, trend="вверх",
                                           recent_change=2.4,
                                           expert=expert, geometry=geom)


@pytest.mark.parametrize("trend", ["uptrend", "downtrend", "ranging", "unknown"])
def test_caption_fits_the_photo_limit(trend):
    """Every combination must fit, including the longest geometry wording."""
    for shape in SHAPES:
        for geom in (GEOMETRY, GEOMETRY_LOSING, None):
            cap = build_caption(*shape, trend=trend, recent_change=2.4,
                                expert=EXPERT, geometry=geom)
            assert len(cap) <= CAPTION_LIMIT, (
                f"{shape[0]} {trend} geom={bool(geom)}: {len(cap)} > "
                f"{CAPTION_LIMIT} — Telegram rejects this as "
                f"MEDIA_CAPTION_TOO_LONG and the signal is never published")


def test_trimming_never_drops_the_levels():
    """A card that loses its stop to a length limit is worse than no card."""
    for shape, cap in _captions():
        for required in ("Вход:", "Цель:", "Стоп:", "R:R"):
            assert required in cap, f"{shape[0]}: {required} was trimmed away"


def test_trimming_never_drops_the_disclaimer():
    for shape, cap in _captions():
        assert "Не является инвестиционной рекомендацией" in cap, \
            f"{shape[0]}: legal disclaimer was trimmed"


def test_caption_html_is_valid():
    """One unescaped & or < makes Telegram reject the whole message."""
    for shape, cap in _captions():
        for closing, name, _ in re.findall(r"<\s*(/?)\s*([a-zA-Z0-9-]+)([^>]*)>", cap):
            assert name.lower() in ALLOWED_TAGS, \
                f"{shape[0]}: <{name}> is not accepted by Telegram HTML"
        stray = re.search(r"&(?!(amp|lt|gt|quot|#\d+);)", cap)
        assert stray is None, \
            f"{shape[0]}: unescaped & at {stray.start() if stray else 0}"


def test_geometry_fits_in_the_ordinary_case():
    """The trim exists as a safety net, not as the normal path.

    If a plain card cannot carry the measured baseline, the caption has grown
    too big again and something else should be cut instead.
    """
    cap = build_caption("SBER", "buy", 278.07, 289.0, 272.5, 89,
                        trend="вверх", recent_change=2.4,
                        expert=EXPERT, geometry=GEOMETRY)
    assert "История инструмента" in cap, \
        "the geometry baseline no longer fits a normal card"


def test_score_is_not_described_as_confirming_quality():
    """The card used to state "WEF N% подтверждает качество сигнала".

    Replaying 80 signals against candles put the correlation between score and
    outcome at -0.35 before the risk_reward fix and +0.07 after — no
    relationship. The score measures how complete the input is, not whether the
    trade works, and the card must not claim otherwise.
    """
    for shape, cap in _captions():
        assert "подтверждает качество" not in cap, \
            f"{shape[0]}: card asserts the score confirms quality"


def test_card_sender_falls_back_to_text():
    """A photo send can fail for reasons a text send does not share. Without a
    fallback the whole signal was dropped on a caption or upload error."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "app" / "services"
           / "signal_chart.py").read_text(encoding="utf-8")
    code = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))
    body = code[code.index("async def broadcast_card"):]
    assert "text fallback" in body, "no text fallback after a failed photo send"


def test_card_sender_accepts_geometry():
    """The clip path passed geometry and the card path did not, so the same
    signal got a different card depending on whether a video rendered."""
    import inspect

    from app.services.signal_chart import broadcast_card
    assert "geometry" in inspect.signature(broadcast_card).parameters


def test_trimming_drops_generic_advice_before_measured_evidence():
    """The first version of the trim cut from the end regardless of content.

    That removed "сама геометрия здесь убыточна" — the one sentence telling the
    reader this setup loses money at its own hit rate — while keeping
    "Рекомендуется вход 50% от обычного размера с узким стопом", which appears
    on every other card. Measured evidence and risk warnings outrank technique.
    """
    losing = {**GEOMETRY, "hit_rate_pct": 28.0}   # below the 33.3% breakeven
    for shape in SHAPES:
        for trend in ("uptrend", "downtrend", "ranging", "unknown"):
            cap = build_caption(*shape, trend=trend, recent_change=2.4,
                                expert=EXPERT, geometry=losing)
            assert len(cap) <= CAPTION_LIMIT, f"{shape[0]} {trend}: {len(cap)}"
            assert "История инструмента" in cap, \
                f"{shape[0]} {trend}: the measured baseline was trimmed"
            assert "убыточна" in cap, \
                f"{shape[0]} {trend}: the unprofitable-geometry warning was trimmed"


def test_reason_for_absent_metrics_is_never_trimmed():
    """Without it the reader assumes EV and Kelly were simply forgotten."""
    for shape in SHAPES:
        cap = build_caption(*shape, trend="ranging", recent_change=2.4,
                            expert=NO_METRICS, geometry=GEOMETRY_LOSING)
        assert "не рассчитано" in cap or "не рассчитаны" in cap, \
            f"{shape[0]}: the explanation for missing metrics was trimmed"
