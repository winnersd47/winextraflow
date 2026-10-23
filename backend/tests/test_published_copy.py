"""The copy we publish must describe the gate the code actually runs.

Two posts and four lesson passages went out telling readers "мы не публикуем
сигналы с R:R ниже 1:1.5" — a rule the gate had already replaced with the
breakeven share. The texts were wrong for as long as nobody re-read them, which
is the failure mode of any rule written down in two places.

These tests do not check style. They check that every number the copy quotes is
the number in `signal_quality`, so changing a threshold fails here instead of
silently making the channel lie.
"""
import re
import sys
from pathlib import Path

import pytest

from app.services import signal_quality as sq
from app.services.lesson_seed import LESSONS

# scripts/ has no __init__.py; put it on the path the way the scripts
# themselves do. Importing feature_posts is safe only because its asyncio.run
# is behind a __main__ guard — without it, collecting this test would post to
# the channel.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import feature_posts  # noqa: E402


def _all_copy() -> dict[str, str]:
    """Every reader-facing text, keyed by something findable in a failure."""
    out = {f"post:{p['key']}": p["text"] for p in feature_posts.POSTS}
    for l in LESSONS:
        out[f"lesson:{l['slug']}:teaser"] = l["teaser"]
        out[f"lesson:{l['slug']}:body"] = l["body"]
        out[f"lesson:{l['slug']}:title"] = l["title"]
    return out


# Phrases that turn a mention of the breakeven share into a claim about when a
# signal is refused. A lesson may teach the metric without quoting the gate's
# threshold — only a paragraph that promises rejection has to be exact.
_REJECTION = ("не публикуется", "не публикуем", "сделки нет",
              "отклоняется", "отклоняют", "не выше")


def test_breakeven_threshold_matches_code():
    """A paragraph that promises rejection must name the real threshold."""
    expected = f"{sq.BREAKEVEN_REJECT_PCT:.0f}%"
    wrong = []
    for name, text in _all_copy().items():
        for block in text.split("\n\n"):
            low = block.lower()
            if "безубыт" not in low:
                continue
            if not any(p in low for p in _REJECTION):
                continue
            if expected not in block:
                wrong.append((name, block.strip()[:80]))
    assert not wrong, (
        f"Порог отклонения сейчас {expected}, но эти абзацы обещают отказ без "
        f"него: {wrong}. Поменяли BREAKEVEN_REJECT_PCT — поправьте и тексты."
    )


def test_old_rr_rule_is_not_presented_as_current():
    """"R:R не ниже 1:1.5" may be quoted as history, never stated as the rule."""
    offenders = []
    for name, text in _all_copy().items():
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            if "1:1.5" not in sentence and "1:1,5" not in sentence:
                continue
            # The lesson explains why the rule was dropped; that sentence names
            # it as the past. Anything else is the channel stating a dead rule.
            if "Раньше" in sentence or "раньше" in sentence:
                continue
            offenders.append((name, sentence.strip()[:90]))
    assert not offenders, (
        f"Эти тексты выдают отменённое правило за действующее: {offenders}"
    )


def test_upper_bounds_match_code():
    """The "цель не дальше N стопов / не выше M%" copy tracks the constants."""
    rr = f"{sq.MAX_RR_RATIO:.0f}"
    tp = f"{sq.MAX_TP_PCT:.0f}%"
    for name, text in _all_copy().items():
        if "не дальше" not in text:
            continue
        assert rr in text, f"{name}: верхняя граница R:R в коде {rr}, в тексте её нет"
        assert tp in text, f"{name}: предел цели в коде +{tp}, в тексте его нет"


def test_martingale_streak_matches_code():
    """"третья подряд доливка" is MARTINGALE_FAIL_STREAK spelled out."""
    words = {2: "втор", 3: "трет", 4: "четвёрт"}
    stem = words.get(sq.MARTINGALE_FAIL_STREAK)
    if stem is None:
        pytest.skip(f"нет склонения для {sq.MARTINGALE_FAIL_STREAK}")
    for name, text in _all_copy().items():
        if "доливк" not in text:
            continue
        low = text.lower()
        if "подряд" not in low:
            continue
        assert stem in low, (
            f"{name}: отклоняем на {sq.MARTINGALE_FAIL_STREAK}-й доливке, "
            f"а в тексте написано другое число"
        )


def test_wef_minimum_matches_code():
    expected = f"{sq.MIN_WEF_SCORE:.0%}".replace(" ", " ")
    for name, text in _all_copy().items():
        if "WEF Score не ниже" not in text:
            continue
        assert expected in text, (
            f"{name}: минимальный WEF Score в коде {expected}"
        )


def test_every_post_links_to_the_live_platform():
    """A post whose link stopped resolving is worse than a post without one."""
    from app.services.signal_chart import PLATFORM_URL

    missing = [p["key"] for p in feature_posts.POSTS if PLATFORM_URL not in p["text"]]
    assert not missing, f"Посты без ссылки на платформу: {missing}"
