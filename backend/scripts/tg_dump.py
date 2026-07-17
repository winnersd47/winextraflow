"""Dump raw text of signal-like messages to study real formats.

Usage: python scripts/tg_dump.py
"""

import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient
from app.config import settings
from app.services.telegram import telegram_parser

CHANNELS = ["beststocksru", "cbrstocks", "AK47pfl", "if_stocks"]


def _proxy():
    if settings.socks5_host and settings.socks5_port:
        import socks
        return (socks.SOCKS5, settings.socks5_host, int(settings.socks5_port), True,
                settings.socks5_user or None, settings.socks5_pass or None)
    return None


async def main():
    client = TelegramClient("wef_readonly", int(settings.telegram_api_id),
                            settings.telegram_api_hash, proxy=_proxy())
    await client.connect()
    if not await client.is_user_authorized():
        print("Not authorized")
        await client.disconnect()
        return

    for ch in CHANNELS:
        try:
            entity = await client.get_entity(ch)
            msgs = await client.get_messages(entity, limit=30)
        except Exception as e:
            print(f"@{ch}: ERROR {e}")
            continue

        print(f"\n{'='*60}\n@{ch}\n{'='*60}")
        shown = 0
        for m in msgs:
            if not m.text:
                continue
            if telegram_parser.is_signal_message(m.text) and shown < 4:
                shown += 1
                print(f"\n--- msg {shown} ---")
                print(m.text[:400])

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
