"""Report signal yield per configured channel.

For each channel in TELEGRAM_PARSE_CHANNELS: fetch recent messages, run the
parser, report total / signal-like / parsed. Answers "which channels
actually produce signals".

Usage: python scripts/tg_channels_report.py [limit_per_channel]
"""

import asyncio
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient
from app.config import settings
from app.services.telegram import telegram_parser


def _proxy():
    if settings.socks5_host and settings.socks5_port:
        import socks
        return (socks.SOCKS5, settings.socks5_host, int(settings.socks5_port), True,
                settings.socks5_user or None, settings.socks5_pass or None)
    return None


async def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    shutil.copyfile(os.path.join(base, "winextraflow_bot.session"), os.path.join(base, "wef_report.session"))

    client = TelegramClient(os.path.join(base, "wef_report"), int(settings.telegram_api_id),
                            settings.telegram_api_hash, proxy=_proxy())
    await client.connect()
    if not await client.is_user_authorized():
        print("Not authorized"); await client.disconnect(); return

    channels = [c.strip() for c in settings.telegram_parse_channels.split(",") if c.strip()]
    print(f"{'CHANNEL':<20} {'TITLE':<32} {'MSGS':>5} {'SIGNAL-LIKE':>12} {'PARSED':>7}")
    print("-" * 82)

    rows = []
    for ch in channels:
        try:
            entity = await client.get_entity(ch)
            title = getattr(entity, "title", ch)[:30]
            msgs = await client.get_messages(entity, limit=limit)
        except Exception as e:
            print(f"{ch:<20} ERROR: {str(e)[:40]}")
            continue

        siglike = parsed_n = total = 0
        samples = []
        for m in msgs:
            if not m.text:
                continue
            total += 1
            if telegram_parser.is_signal_message(m.text):
                siglike += 1
                p = telegram_parser.parse_message(m.text)
                if p:
                    parsed_n += 1
                    if len(samples) < 2:
                        samples.append(f"{p.action.upper()} {p.ticker} @ {p.entry_price}")
        rows.append((ch, title, total, siglike, parsed_n, samples))
        print(f"{ch:<20} {title:<32} {total:>5} {siglike:>12} {parsed_n:>7}")
        await asyncio.sleep(0.3)

    await client.disconnect()
    try:
        os.remove(os.path.join(base, "wef_report.session"))
    except OSError:
        pass

    print("\n=== Channels producing signals ===")
    for ch, title, total, siglike, parsed_n, samples in rows:
        if parsed_n > 0:
            print(f"  @{ch} ({title}): {parsed_n} signals — e.g. {'; '.join(samples)}")
    print("\n=== News/analytics (0 signals — market context only) ===")
    print("  " + ", ".join(f"@{ch}" for ch, _, _, _, p, _ in rows if p == 0))


if __name__ == "__main__":
    asyncio.run(main())
