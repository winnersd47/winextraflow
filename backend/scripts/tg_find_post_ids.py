"""Backfill message ids for feature posts that were sent before ids were kept.

Why
---
`feature_posts.py send` used to throw away the id Telegram returns. That was
fine until two posts went out stating a rule the quality gate had already
dropped ("R:R не ниже 1:1.5" — replaced by the breakeven share). Fixing the
template does nothing for the copy already sitting in the channel, and the Bot
API cannot list a bot's own past messages.

The user session can read the channel history, so it can find them. A bot may
edit its own channel message with no time limit, so once the id is written into
feature_post_state.json, `feature_posts.py edit N` repairs the live post without
deleting it — the views and the comment thread survive.

Matching is on the headline, which is the first line of every post and is unique
across the library. Body text is not compared: the whole point is that the body
has changed.

Usage:
    python scripts/tg_find_post_ids.py              # report only
    python scripts/tg_find_post_ids.py --write      # save into the state file
    python scripts/tg_find_post_ids.py --limit 500  # how deep to read (default 300)
"""
import asyncio
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.services.telethon_lock import telethon_session

import feature_posts as fp

TAGS = re.compile(r"<[^>]+>")


def _headline(text: str) -> str:
    """First line, tags and decoration stripped, collapsed for comparison.

    The sent message has HTML rendered away and may carry an emoji the
    accessibility layer renders differently, so compare on letters and digits
    only.
    """
    first = TAGS.sub("", text).strip().splitlines()[0]
    return re.sub(r"[^0-9a-zа-яё]+", "", first.lower())


async def main() -> int:
    write = "--write" in sys.argv
    limit = 300
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    channels = {
        "free": settings.telegram_free_channel_id,
        "vip": settings.telegram_vip_channel_id,
    }
    channels = {k: v for k, v in channels.items() if v}
    if not channels:
        print("Ни один канал не настроен в .env")
        return 1

    wanted = {_headline(p["text"]): p["key"] for p in fp.POSTS}
    found: dict[str, dict[str, int]] = {}

    # "wef_backfill" is the authorised login, not a label: telethon_session
    # opens the .session file of exactly that name, so any other string here
    # creates a fresh, unauthorised session and fails with
    # AuthKeyUnregisteredError. Sharing the name is also correct — the lock is
    # what keeps this script and the cron backfill off the wire together.
    async with telethon_session("wef_backfill") as client:
        if client is None:
            print("Сессия занята бэкфилом — попробуйте через пару минут.")
            return 1
        if not await client.is_user_authorized():
            print("Сессия не авторизована: python scripts/tg_signin.py")
            return 1

        # get_entity on a bare -100… id fails with "The key is not registered
        # in the system" whenever the session has no cached access_hash for the
        # channel. Walking the dialog list fills that cache and gives the
        # entity directly, which is what the ids in .env always refer to.
        from telethon import utils as tg_utils
        dialogs = {}
        async for d in client.iter_dialogs():
            try:
                dialogs[tg_utils.get_peer_id(d.entity)] = d.entity
            except Exception:
                continue

        for label, chat_id in channels.items():
            entity = dialogs.get(int(chat_id))
            if entity is None:
                try:
                    entity = await client.get_entity(int(chat_id))
                except Exception as e:
                    print(f"{label} ({chat_id}): не открыть — {e}")
                    continue
            seen = 0
            async for msg in client.iter_messages(entity, limit=limit):
                if not msg.text:
                    continue
                seen += 1
                key = wanted.get(_headline(msg.text))
                if not key:
                    continue
                # iter_messages walks newest first, so the first hit is the
                # most recent send of that post. A rotation that reposted it
                # should repair the copy people are actually looking at.
                found.setdefault(key, {}).setdefault(str(chat_id), msg.id)
            print(f"{label} ({chat_id}): прочитано {seen} сообщений")

    print()
    if not found:
        print("Совпадений нет. Посты либо глубже --limit, либо заголовки изменились.")
        return 1

    titles = {p["key"]: p["title"] for p in fp.POSTS}
    for key, targets in found.items():
        for chat_id, mid in targets.items():
            print(f"  {titles.get(key, key)} → {chat_id}#{mid}")

    if not write:
        print("\nЭто предпросмотр. Сохранить: --write")
        return 0

    st = fp._state()
    for key, targets in found.items():
        for chat_id, mid in targets.items():
            fp._remember(st, key, chat_id, mid)
    fp._save(st)
    print(f"\nЗаписано в {fp.STATE}")
    print("Теперь: python scripts/feature_posts.py edit <N>")
    return 0


raise SystemExit(asyncio.run(main()))
