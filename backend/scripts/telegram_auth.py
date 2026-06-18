"""One-time Telegram authentication script.

Run this once to create a session file. After that, the worker
will use the saved session automatically without needing a code.

Usage:
    python scripts/telegram_auth.py

You will be prompted for:
1. Your phone number (e.g., +79123456789)
2. A code sent to your Telegram app
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient
from app.config import settings


async def main():
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        print("ERROR: TELEGRAM_API_ID and TELEGRAM_API_HASH not set in .env")
        return

    print(f"API_ID: {settings.telegram_api_id}")
    print(f"API_HASH: {settings.telegram_api_hash[:8]}...")
    print()

    phone = input("Enter your phone number (e.g., +79123456789): ").strip()
    if not phone:
        print("Phone number required")
        return

    # Proxy support: SOCKS5 → MTProxy → direct
    connect_kwargs = {}

    if settings.socks5_host and settings.socks5_port:
        import socks
        connect_kwargs["proxy"] = (
            socks.SOCKS5,
            settings.socks5_host,
            settings.socks5_port,
            True,
            settings.socks5_user or None,
            settings.socks5_pass or None,
        )
        print(f"SOCKS5 proxy: {settings.socks5_host}:{settings.socks5_port} (user: {settings.socks5_user or 'none'})")

    elif settings.mtproxy_host and settings.mtproxy_port and settings.mtproxy_secret:
        try:
            from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate
            connect_kwargs["connection"] = ConnectionTcpMTProxyRandomizedIntermediate
            connect_kwargs["proxy"] = (
                settings.mtproxy_host,
                settings.mtproxy_port,
                settings.mtproxy_secret,
            )
            print(f"MTProxy: {settings.mtproxy_host}:{settings.mtproxy_port}")
        except ImportError:
            print("WARNING: MTProxy not available in this Telethon version")

    else:
        print("No proxy configured. Connecting directly.")
        print("If blocked, add to .env:")
        print("  SOCKS5_HOST=tp.sds.kari.local")
        print("  SOCKS5_PORT=18001")
        print("  SOCKS5_USER=tg")
        print("  SOCKS5_PASS=your_password")

    client = TelegramClient(
        "winextraflow_bot",
        int(settings.telegram_api_id),
        settings.telegram_api_hash,
        **connect_kwargs,
    )

    await client.start(phone=phone)

    me = await client.get_me()
    print(f"\nAuthenticated as: {me.first_name} (@{me.username})")
    print(f"Session saved to: winextraflow_bot.session")

    # Test: resolve the channel
    channels = [c.strip() for c in settings.telegram_parse_channels.split(",") if c.strip()]
    if channels:
        print(f"\nTesting channel access...")
        for ch in channels:
            try:
                entity = await client.get_entity(ch)
                title = getattr(entity, "title", ch)
                print(f"  ✓ @{ch} → '{title}' (id: {entity.id})")
            except Exception as e:
                print(f"  ✗ @{ch} → Error: {e}")

    await client.disconnect()
    print("\nDone! Session file created. Restart the backend to start parsing.")


if __name__ == "__main__":
    asyncio.run(main())
