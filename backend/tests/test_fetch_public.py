"""A post must carry its own timestamp, not a neighbour's.

The first version of scripts/fetch_public.py collected every message body on
the page into one list and every `datetime=` attribute into another, then
zipped them by position. The two lists are not the same length: a photo-only
post has a date and no body, a forward or a reply quote adds an extra
`datetime`. Measured across eight monitored channels on 2026-10-29, four were
misaligned — ddluuxx_trading had 16 bodies against 18 dates.

That feeds the 48-hour freshness window in tg_backfill.py, whose only job is to
stop a year-old post becoming a signal card priced off a year-old quote.

The fixtures below are trimmed from real t.me/s/ markup.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fetch_public import ChannelUnavailable, _parse  # noqa: E402


def _post(mid: int, *, when: str | None, body: str | None,
          quoted: str | None = None) -> str:
    """One message block. `quoted` adds the extra <time> a reply preview brings."""
    reply = (f'<div class="tgme_widget_message_reply">'
             f'<time datetime="{quoted}" class="time">x</time></div>'
             if quoted else "")
    text = (f'<div class="tgme_widget_message_text js-message_text">{body}</div>'
            if body is not None else "")
    date = (f'<a class="tgme_widget_message_date" href="#">'
            f'<time datetime="{when}" class="time">00:00</time></a>'
            if when else "")
    return (f'<div class="tgme_widget_message" data-post="chan/{mid}">'
            f'{reply}{text}<span class="tgme_widget_message_meta">{date}</span>'
            f'</div>')


def test_photo_post_does_not_shift_the_dates():
    """The exact failure: a bodiless post between two real ones."""
    page = (
        _post(1, when="2026-10-29T10:00:00+00:00", body="BUY EURUSD") +
        _post(2, when="2026-10-29T11:00:00+00:00", body=None) +      # photo only
        _post(3, when="2026-10-29T12:00:00+00:00", body="SELL XAUUSD")
    )
    posts = _parse(page)
    assert [p["text"] for p in posts] == ["BUY EURUSD", "SELL XAUUSD"]
    assert posts[0]["date"].hour == 10
    assert posts[1]["date"].hour == 12, \
        "второй пост получил время соседа — даты снова сдвинуты"


def test_reply_quote_does_not_steal_the_timestamp():
    """A reply preview carries an older <time>; the message's own must win."""
    page = _post(7, when="2026-10-29T09:00:00+00:00", body="BUY GBPUSD",
                 quoted="2024-01-01T00:00:00+00:00")
    (post,) = _parse(page)
    assert post["date"] == datetime(2026, 10, 29, 9, tzinfo=timezone.utc)


def test_undated_post_is_reported_as_undated():
    """None, never "now" — the caller drops it rather than treating it as fresh."""
    page = _post(9, when=None, body="BUY SBER")
    (post,) = _parse(page)
    assert post["date"] is None


def test_post_id_comes_from_the_page():
    """The LLM ledger keys on this; a text hash re-charged for every edit."""
    page = _post(14571, when="2026-10-29T06:00:00+00:00", body="Ртс Лонг")
    (post,) = _parse(page)
    assert post["id"] == "chan/14571"


def test_entities_and_line_breaks_survive():
    page = _post(3, when="2026-10-29T06:00:00+00:00",
                 body="Buy &amp; hold<br/>Entry: 1.05")
    (post,) = _parse(page)
    assert post["text"] == "Buy & hold\nEntry: 1.05"


@pytest.mark.asyncio
async def test_channel_without_preview_raises_rather_than_looking_quiet():
    """t.me answers 200 with a landing page, so an empty list reads as "no posts
    today" forever. silver_fx_trading_signals_free sat in the monitored list in
    exactly that state."""
    import httpx

    import fetch_public

    class _Resp:
        status_code = 200
        text = "<html><body>no messages here</body></html>"

        def raise_for_status(self):
            return None

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, _url):
            return _Resp()

    original, httpx.AsyncClient = httpx.AsyncClient, _Client
    try:
        with pytest.raises(ChannelUnavailable):
            await fetch_public.fetch_channel("whatever")
    finally:
        httpx.AsyncClient = original
