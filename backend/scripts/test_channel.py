"""Test a public Telegram channel: show which messages parse as signals and their R:R.

Usage:
  python scripts/test_channel.py <@channel_username> [limit]

Example:
  python scripts/test_channel.py @beststocksru 30
"""
import asyncio, os, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone
from scripts.fetch_public import fetch_channel
from app.services.telegram import telegram_parser


def rr_str(entry, tp, sl):
    try:
        gain = abs(tp - entry)
        risk = abs(sl - entry)
        if risk == 0:
            return "∞"
        ratio = gain / risk
        ok = "✅" if ratio >= 1.5 else ("⚠️" if ratio >= 1.0 else "❌")
        return f"{ok} {ratio:.1f}:1"
    except Exception:
        return "?"


async def main():
    channel = sys.argv[1] if len(sys.argv) > 1 else "@beststocksru"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

    print(f"\nFetching {channel} via t.me/s/ ...")
    msgs = await fetch_channel(channel, limit=limit)
    fresh = [m for m in msgs if m["date"] is None or m["date"] >= cutoff]

    print(f"\n{'='*60}")
    print(f"Channel: {channel}  |  Messages: {len(msgs)} fetched, {len(fresh)} fresh (<48h)")
    print(f"{'='*60}\n")

    parsed_count = 0
    good_rr = 0

    for m in fresh:
        text = m["text"]
        if not telegram_parser.is_signal_message(text):
            continue

        parsed = telegram_parser.parse_message(text)
        if not parsed:
            preview = text[:80].replace("\n", " ")
            print(f"  🔍 Signal-like but not parsed: {preview!r}")
            continue

        rr = rr_str(parsed.entry_price, parsed.take_profit or 0, parsed.stop_loss or 0)
        parsed_count += 1
        if "✅" in rr:
            good_rr += 1

        print(f"  {parsed.action.upper()} {parsed.ticker} @ {parsed.entry_price}"
              f"  TP:{parsed.take_profit}  SL:{parsed.stop_loss}  R:R={rr}")
        preview = text[:60].replace("\n", " ")
        print(f"    └ {preview!r}")
        print()

    print(f"\n{'='*60}")
    print(f"Parsed signals: {parsed_count} | Good R:R (≥1.5:1): {good_rr}")
    print(f"{'='*60}\n")


asyncio.run(main())
