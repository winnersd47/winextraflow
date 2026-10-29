"""Recent posts from a public Telegram channel over plain HTTP (t.me/s/).

Why this exists
---------------
The cron backfill used to read channels through Telethon, which meant it held a
user auth key — and the project already lost 37 days of pipeline to a revoked
key (see services/telethon_lock.py). A public channel's web preview needs no
auth at all, so the scheduled job does not have to carry an identity it can get
banned for.

What it cannot do
-----------------
Only channels whose owner left the web preview on. A private channel, or one
with preview disabled, returns nothing — `fetch_channel` raises rather than
returning an empty list, because "no posts" and "cannot see this channel" lead
to very different fixes and the caller was treating both as "quiet today".

Pairing text with its timestamp
-------------------------------
The first version collected every message body on the page into one list and
every `datetime=` attribute into another, then zipped them by position. Those
two lists are not the same length: a photo-only post has a date and no body, a
forwarded or reply-quoted message carries an extra `datetime`. Measured across
eight monitored channels on 2026-10-29, four were misaligned —
`ddluuxx_trading` had 16 bodies against 18 dates — so posts were being stamped
with a neighbour's time. That feeds the 48-hour freshness filter in
tg_backfill.py, whose entire job is to keep year-old posts from being ingested
as fresh signals with absurd entry prices.

So parse per message instead: split the page on the message wrapper, and inside
each one take the body and the date from that same block.
"""
import asyncio
import html as _html
import os
import re
import sys
from datetime import datetime

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# Each post is one `data-post="channel/12345"` block. Splitting on it keeps a
# body and its own metadata together, which zipping two page-wide lists did not.
_POST = re.compile(r'data-post="([^"/]+)/(\d+)"')

# The message's own timestamp sits in the footer link. Any other `datetime` on
# the page — a reply preview, a forward header — is some other message's.
_DATE = re.compile(
    r'class="tgme_widget_message_date"[^>]*>\s*<time\s+datetime="([^"]+)"',
    re.IGNORECASE,
)

_TEXT = re.compile(
    r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', re.DOTALL)


class ChannelUnavailable(RuntimeError):
    """The channel has no public web preview, or does not exist."""


def _plain(fragment: str) -> str:
    """Message body as text: <br> and block ends become newlines, tags go."""
    s = re.sub(r"<br\s*/?>", "\n", fragment)
    s = re.sub(r"</(?:p|div)>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    return _html.unescape(s).strip()


def _parse(page: str) -> list[dict]:
    posts: list[dict] = []
    marks = list(_POST.finditer(page))
    for i, m in enumerate(marks):
        chunk = page[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(page)]

        body = _TEXT.search(chunk)
        text = _plain(body.group(1)) if body else ""
        if not text:
            continue        # photo/video/service post — nothing to parse

        when = None
        d = _DATE.search(chunk)
        if d:
            try:
                when = datetime.fromisoformat(d.group(1).replace("Z", "+00:00"))
            except ValueError:
                pass        # left as None; the caller must not treat it as fresh

        posts.append({"id": f"{m.group(1)}/{m.group(2)}", "text": text,
                      "date": when})
    return posts


async def fetch_channel(channel: str, limit: int = 30) -> list[dict]:
    """Newest-first list of {id, text, date} for a public channel.

    `date` is None only when the page did not carry one; callers decide what to
    do with that and must not assume it means "recent".
    """
    name = channel.lstrip("@")
    async with httpx.AsyncClient(timeout=20, follow_redirects=True,
                                 headers={"User-Agent": _UA}) as client:
        r = await client.get(f"https://t.me/s/{name}")
    if r.status_code == 404:
        raise ChannelUnavailable(f"@{name}: канала нет")
    r.raise_for_status()

    posts = _parse(r.text)
    if not posts:
        # t.me answers 200 with a landing page for a private channel or one with
        # the preview switched off, so the status code cannot tell these apart.
        raise ChannelUnavailable(
            f"@{name}: публичного превью нет — приватный канал или превью "
            f"выключено владельцем")
    return posts[-limit:][::-1] if limit else posts[::-1]


if __name__ == "__main__":
    async def _main() -> int:
        if len(sys.argv) < 2:
            print(__doc__)
            return 1
        sys.stdout.reconfigure(encoding="utf-8")
        for ch in sys.argv[1:]:
            try:
                msgs = await fetch_channel(ch, limit=10)
            except ChannelUnavailable as e:
                print(f"{e}")
                continue
            print(f"\n@{ch}: {len(msgs)} постов")
            for m in msgs[:5]:
                head = m["text"].splitlines()[0][:64]
                print(f"  {m['id']:28} {str(m['date'])[:19]:20} {head}")
        return 0

    raise SystemExit(asyncio.run(_main()))
