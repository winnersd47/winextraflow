"""Probe candidate signal channels: resolve + fetch + parse yield.

Reports which candidates are accessible AND post parseable Entry/TP/SL signals.
Usage: python scripts/tg_find_signals.py
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

CANDIDATES = [
    # Crypto signal channels (public)
    "binancekillers", "fedrussians", "wallstreetqueenofficial", "rocketwalletsignals",
    "verifiedcryptotraders", "mycsignals", "universalcryptosignals", "learn2trade",
    "AltSignals", "wolfxsignals", "cryptopumpsignals", "onwardbtc", "klondikevipbot",
    "CoinSignalss", "CryptoClassics", "fatpigsignals", "TheCryptoTradez",
    # Forex signal channels
    "forexsignalsdaily", "freeforexsignalss", "forexgdp_official", "pipsalert",
    "forexstockssignal", "SignalFactoryFX", "goldsignalfx",
    # MOEX / RU
    "signaltrading_ru", "trading_signalov", "profit_signals_ru",
]


def _proxy():
    if settings.socks5_host and settings.socks5_port:
        import socks
        return (socks.SOCKS5, settings.socks5_host, int(settings.socks5_port), True,
                settings.socks5_user or None, settings.socks5_pass or None)
    return None


async def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # No copy. Duplicating a .session file duplicates the auth key, and
    # Telegram revokes a key it sees connect from two places — that is what
    # killed the pipeline for 37 days. Use the live session under the
    # cross-process lock instead; it waits for the poller rather than
    # cloning around it.
    from app.services.telethon_lock import acquire, release
    if not await acquire("wef_backfill"):
        print("Telethon занят другим процессом — попробуйте позже")
        return
    client = TelegramClient(os.path.join(base, "wef_backfill"), int(settings.telegram_api_id),
                            settings.telegram_api_hash, proxy=_proxy())
    await client.connect()
    if not await client.is_user_authorized():
        print("Not authorized"); await client.disconnect(); return

    producers = []
    for ch in CANDIDATES:
        try:
            entity = await client.get_entity(ch)
            title = getattr(entity, "title", ch)[:28]
            msgs = await client.get_messages(entity, limit=25)
        except Exception:
            continue  # skip unresolved silently

        siglike = parsed_n = 0
        samples = []
        for m in msgs:
            if not m.text:
                continue
            if telegram_parser.is_signal_message(m.text):
                siglike += 1
                p = telegram_parser.parse_message(m.text)
                if p:
                    parsed_n += 1
                    if len(samples) < 2:
                        tp = f" TP:{p.take_profit}" if p.take_profit else ""
                        samples.append(f"{p.action.upper()} {p.ticker} @ {p.entry_price}{tp}")
        subs = getattr(entity, "participants_count", None)
        sub_s = f"{subs//1000}k" if subs else "?"
        flag = "SIGNALS" if parsed_n > 0 else ("has-format" if siglike >= 3 else "news")
        print(f"  [{flag:9}] @{ch:<24} '{title}' | {sub_s} subs | siglike={siglike} parsed={parsed_n}")
        if parsed_n > 0:
            producers.append((ch, title, parsed_n, samples))
        await asyncio.sleep(0.4)

    await client.disconnect()
    try:
        release("wef_backfill")
    except OSError:
        pass

    print(f"\n{'='*60}\nPRODUCERS (parseable Entry/TP/SL signals):")
    if producers:
        for ch, title, n, samples in producers:
            print(f"  @{ch} ({title}): {n} — {'; '.join(samples)}")
        print(f"\nAdd to .env: {','.join(p[0] for p in producers)}")
    else:
        print("  (none of the candidates produced regex-parseable signals)")


if __name__ == "__main__":
    asyncio.run(main())
