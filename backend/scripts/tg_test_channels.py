"""Test which candidate Telegram channels are accessible + have recent posts.

Usage: python scripts/tg_test_channels.py

Prints a ready-to-paste TELEGRAM_PARSE_CHANNELS line with working channels.
"""

import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient
from app.config import settings

# Candidate channels by category (public, signal/analytics-focused)
CANDIDATES = {
    "MOEX / RU stocks": [
        "beststocksru", "investideas_ru", "if_stocks", "tinkoff_invest_official",
        "AK47pfl", "cbrstocks", "markettwits", "russianmacro", "rdvbanki",
    ],
    "Crypto": [
        "cryptostrike", "cryptodurdenofficial", "forklog", "if_market_news",
        "web3news", "incryptonews", "cryptoheadline",
    ],
    "Forex / Global": [
        "forexfactory", "financelab", "profinance_official", "marketpulse",
    ],
}


def _proxy():
    if settings.socks5_host and settings.socks5_port:
        import socks
        return (socks.SOCKS5, settings.socks5_host, int(settings.socks5_port), True,
                settings.socks5_user or None, settings.socks5_pass or None)
    return None


async def main():
    client = TelegramClient("winextraflow_bot", int(settings.telegram_api_id),
                            settings.telegram_api_hash, proxy=_proxy())
    await client.connect()

    if not await client.is_user_authorized():
        print("ERROR: Not authorized. Run tg_signin.py first.")
        await client.disconnect()
        return

    working = []
    for category, channels in CANDIDATES.items():
        print(f"\n=== {category} ===")
        for ch in channels:
            try:
                entity = await client.get_entity(ch)
                title = getattr(entity, "title", ch)
                # Check for recent messages
                msgs = await client.get_messages(entity, limit=1)
                last = msgs[0].date.strftime("%Y-%m-%d") if msgs else "no posts"
                subs = getattr(entity, "participants_count", None)
                sub_str = f"{subs:,} subs" if subs else "?"
                print(f"  [OK]   @{ch:28s} '{title[:35]}' | {sub_str} | last: {last}")
                working.append(ch)
            except Exception as e:
                err = str(e)[:50]
                print(f"  [SKIP] @{ch:28s} {err}")
            await asyncio.sleep(0.3)

    await client.disconnect()

    print(f"\n{'='*60}")
    print(f"WORKING CHANNELS ({len(working)}):")
    print(f"TELEGRAM_PARSE_CHANNELS={','.join(working)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
