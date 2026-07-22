"""Phase 2 of Telegram auth — sign in with the code from the app.

Usage:
    python scripts/tg_signin.py 12345              # code only
    python scripts/tg_signin.py 12345 MyPassword   # code + 2FA password

Reads phone + phone_code_hash from .tg_auth_state.json (phase 1).
Creates winextraflow_bot.session on success.
"""

import asyncio
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
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
        print("Usage: python scripts/tg_signin.py CODE [2FA_PASSWORD]")
        return

    code = sys.argv[1].strip()
    password = sys.argv[2].strip() if len(sys.argv) > 2 else None

    if not os.path.exists(STATE_FILE):
        print("ERROR: No auth state. Run tg_send_code.py first.")
        return

    with open(STATE_FILE) as f:
        state = json.load(f)

    session_name = state.get("session", "winextraflow_bot")
    client = TelegramClient(session_name, int(settings.telegram_api_id),
                            settings.telegram_api_hash, proxy=_proxy())
    await client.connect()

    try:
        await client.sign_in(phone=state["phone"], code=code, phone_code_hash=state["phone_code_hash"])
    except SessionPasswordNeededError:
        if not password:
            print("2FA enabled — rerun: python scripts/tg_signin.py CODE YOUR_2FA_PASSWORD")
            await client.disconnect()
            return
        await client.sign_in(password=password)

    me = await client.get_me()
    print(f"\nAuthenticated as: {me.first_name} (@{me.username or 'no-username'})")
    print(f"Session saved: {session_name}.session")

    # Test channel access
    channels = [c.strip() for c in settings.telegram_parse_channels.split(",") if c.strip()]
    if channels:
        print(f"\nTesting channel access ({len(channels)} channels)...")
        for ch in channels:
            try:
                entity = await client.get_entity(ch)
                title = getattr(entity, "title", ch)
                print(f"  [OK] @{ch} -> '{title}' (id: {entity.id})")
            except Exception as e:
                print(f"  [FAIL] @{ch} -> {e}")

    await client.disconnect()

    # Clean up state file
    try:
        os.remove(STATE_FILE)
    except OSError:
        pass

    print("\nDone! Restart backend to start parsing.")


if __name__ == "__main__":
    asyncio.run(main())
