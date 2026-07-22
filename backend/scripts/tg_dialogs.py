"""List channels/groups a session is subscribed to + check for signal content.

Usage: python scripts/tg_dialogs.py [session_name]
  session_name defaults to winextraflow_bot2 (the 2nd account).
"""

import asyncio
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient
from telethon.tl.types import Channel, Chat
from app.config import settings
from app.services.telegram import telegram_parser


def _proxy():
    if settings.socks5_host and settings.socks5_port:
        import socks
        return (socks.SOCKS5, settings.socks5_host, int(settings.socks5_port), True,
                settings.socks5_user or None, settings.socks5_pass or None)
    return None


async def main():
    session = sys.argv[1] if len(sys.argv) > 1 else "winextraflow_bot2"
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(base, f"{session}.session")
    work = os.path.join(base, f"{session}_dlg.session")
    shutil.copyfile(src, work)

    client = TelegramClient(work, int(settings.telegram_api_id),
                            settings.telegram_api_hash, proxy=_proxy())
    await client.connect()
    if not await client.is_user_authorized():
        print(f"{session} not authorized"); await client.disconnect(); return

    me = await client.get_me()
    print(f"Account: {me.first_name} (@{me.username})\n")

    channels = []
    async for dialog in client.iter_dialogs():
        ent = dialog.entity
        # Only channels/supergroups (skip private chats)
        if isinstance(ent, Channel):
            channels.append(ent)

    print(f"Subscribed to {len(channels)} channels/groups. Scanning for signals...\n")

    signal_channels = []
    for ent in channels:
        title = getattr(ent, "title", "?")[:32]
        uname = getattr(ent, "username", None)
        try:
            msgs = await client.get_messages(ent, limit=20)
        except Exception:
            continue
        siglike = parsed = 0
        sample = ""
        for m in msgs:
            if m.text and telegram_parser.is_signal_message(m.text):
                siglike += 1
                p = telegram_parser.parse_message(m.text)
                if p:
                    parsed += 1
                    if not sample:
                        tp = f" TP:{p.take_profit}" if p.take_profit else ""
                        sample = f"{p.action.upper()} {p.ticker} @ {p.entry_price}{tp}"
        tag = "SIGNALS" if parsed else ("format?" if siglike >= 3 else "")
        uname_s = f"@{uname}" if uname else "(private)"
        mark = f" [{tag}]" if tag else ""
        print(f"  {title:<34} {uname_s:<26} siglike={siglike} parsed={parsed}{mark}")
        if parsed or siglike >= 3:
            signal_channels.append((title, uname, siglike, parsed, sample))
        await asyncio.sleep(0.25)

    await client.disconnect()
    try:
        os.remove(work)
    except OSError:
        pass

    print(f"\n{'='*60}\nCHANNELS WITH SIGNAL CONTENT:")
    if signal_channels:
        for title, uname, sl, pn, sample in signal_channels:
            u = f"@{uname}" if uname else "(private, no username)"
            extra = f" — e.g. {sample}" if sample else ""
            print(f"  {title} {u}: siglike={sl} parsed={pn}{extra}")
    else:
        print("  (no channels with signal-format content)")


if __name__ == "__main__":
    asyncio.run(main())
