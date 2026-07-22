"""Phase 1 of Telegram auth — send login code to the user's Telegram app.

Usage: python scripts/tg_send_code.py +79123456789

Saves phone + phone_code_hash to .tg_auth_state.json for phase 2 (tg_signin.py).
"""

import asyncio
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient
from app.config import settings

STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".tg_auth_state.json")


def _proxy():
    if settings.socks5_host and settings.socks5_port:
        import socks
        return (socks.SOCKS5, settings.socks5_host, int(settings.socks5_port), True,
                settings.socks5_user or None, settings.socks5_pass or None)
    return None


async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/tg_send_code.py +79123456789 [session_name]")
        print("  session_name defaults to 'winextraflow_bot' (2nd account: e.g. 'winextraflow_bot2')")
        return

    phone = sys.argv[1].strip()
    session_name = sys.argv[2].strip() if len(sys.argv) > 2 else "winextraflow_bot"
    proxy = _proxy()
    print(f"API_ID: {settings.telegram_api_id} | session: {session_name}")
    if proxy:
        print(f"SOCKS5 proxy: {settings.socks5_host}:{settings.socks5_port}")

    client = TelegramClient(session_name, int(settings.telegram_api_id),
                            settings.telegram_api_hash, proxy=proxy)
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"Already authorized as: {me.first_name} (@{me.username})")
        await client.disconnect()
        return

    print(f"Sending code to {phone}...")
    sent = await client.send_code_request(phone)

    with open(STATE_FILE, "w") as f:
        json.dump({"phone": phone, "phone_code_hash": sent.phone_code_hash, "session": session_name}, f)

    print(f"\nCode sent! Check your Telegram app.")
    print(f"Then run: python scripts/tg_signin.py CODE")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
