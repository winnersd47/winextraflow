"""Show raw messages from a public channel to debug parsing."""
import asyncio, sys, os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.fetch_public import fetch_channel
from app.services.telegram import telegram_parser

async def main():
    channel = sys.argv[1] if len(sys.argv) > 1 else "beststocksru"
    msgs = await fetch_channel(channel, 20)
    print(f"Fetched {len(msgs)} messages from @{channel}\n")
    for i, m in enumerate(msgs[:10]):
        is_sig = telegram_parser.is_signal_message(m["text"])
        tag = "🟢 SIGNAL" if is_sig else "⚪ skip"
        print(f"--- [{i+1}] {tag} ---")
        print(m["text"][:300])
        print()

asyncio.run(main())
