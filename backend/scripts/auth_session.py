"""Authorize a Telethon session from the bot token (no phone, no SMS code).

What this session can do: act as the bot — send, edit, read updates addressed
to it. What it cannot do: read a channel's history the way a member does. For
reading channels use scripts/fetch_public.py (no auth at all) or the user
session under app/services/telethon_lock.py.

It writes `winextraflow_bot.session`, which is the filename the backfill used to
`shutil.copyfile` before the pipeline lost 37 days to a revoked auth key. That
path is gone, but never copy this file either — read telethon_lock.py first.
"""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from telethon import TelegramClient
from app.config import settings

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
session_path = os.path.join(base, "winextraflow_bot")

async def main():
    client = TelegramClient(session_path, int(settings.telegram_api_id), settings.telegram_api_hash)
    await client.start(bot_token=settings.telegram_bot_token)
    me = await client.get_me()
    print(f"\n✅ Authorized as bot: @{me.username} id={me.id}")
    await client.disconnect()

asyncio.run(main())
