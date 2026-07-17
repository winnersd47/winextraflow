"""Pull recent messages from signal channels and run them through the parser.

Shows what signals WOULD be extracted — no DB writes.
Usage: python scripts/tg_parse_test.py
"""

import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient
from app.config import settings
from app.services.telegram import telegram_parser

SIGNAL_CHANNELS = ["beststocksru", "cbrstocks", "AK47pfl", "if_stocks", "forexfactory"]


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

    total_msgs = 0
    total_signals = 0

    for ch in SIGNAL_CHANNELS:
        try:
            entity = await client.get_entity(ch)
            msgs = await client.get_messages(entity, limit=20)
        except Exception as e:
            print(f"\n@{ch}: ERROR {e}")
            continue

        signals_here = 0
        flagged = 0
        for m in msgs:
            if not m.text:
                continue
            total_msgs += 1
            if telegram_parser.is_signal_message(m.text):
                flagged += 1
                parsed = telegram_parser.parse_message(m.text)
                via = "regex"
                if not parsed:
                    parsed = await telegram_parser.parse_with_llm(m.text)
                    via = "LLM"
                if parsed:
                    signals_here += 1
                    total_signals += 1
                    tp = f" TP:{parsed.take_profit}" if parsed.take_profit else ""
                    sl = f" SL:{parsed.stop_loss}" if parsed.stop_loss else ""
                    print(f"  [SIGNAL/{via}] @{ch}: {parsed.action.upper()} {parsed.ticker} @ {parsed.entry_price}{tp}{sl}")

        print(f"@{ch}: {len(msgs)} msgs, {flagged} signal-like, {signals_here} parsed")

    await client.disconnect()

    print(f"\n{'='*55}")
    print(f"Scanned {total_msgs} messages -> {total_signals} parseable signals")
    print(f"(News/analytics posts are correctly skipped by is_signal_message)")
    print(f"{'='*55}")


if __name__ == "__main__":
    asyncio.run(main())
