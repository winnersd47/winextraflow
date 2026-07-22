"""Backfill: fetch recent beststocks recommendations, parse, save + rate.

Full pipeline demo: fetch -> parse -> save to DB -> AI rating (WEF Score).
Usage: python scripts/tg_backfill.py [limit]
"""

import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from telethon import TelegramClient

from app.config import settings
from app.database import async_session, create_tables
from app.models.provider import Provider, ProviderSource
from app.models.signal import Signal, SignalAction
from app.services.telegram import telegram_parser
from app.services.ai_rating import ai_rating_service

# Channels proven to post parseable structured signals (analyst recommendations)
SIGNAL_CHANNELS = ["beststocksru", "ricesignal"]


def _proxy():
    if settings.socks5_host and settings.socks5_port:
        import socks
        return (socks.SOCKS5, settings.socks5_host, int(settings.socks5_port), True,
                settings.socks5_user or None, settings.socks5_pass or None)
    return None


async def main(limit: int | None = None, broadcast: bool | None = None):
    limit = limit if limit is not None else (int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 30)
    if broadcast is None:
        broadcast = "--vip" in sys.argv
    await create_tables()

    # Auto-copy the session so we never fight the live worker / stuck backend lock
    import shutil
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(base, "winextraflow_bot.session")
    dst = os.path.join(base, "wef_backfill.session")
    if os.path.exists(src):
        try:
            shutil.copyfile(src, dst)
        except Exception as e:
            print(f"(session copy warning: {e})")

    client = TelegramClient(os.path.join(base, "wef_backfill"), int(settings.telegram_api_id),
                            settings.telegram_api_hash, proxy=_proxy())
    await client.connect()
    if not await client.is_user_authorized():
        print("Not authorized")
        await client.disconnect()
        return

    # Fetch messages from all signal channels while connected
    fetched = []  # list of (username, entity_id, title, messages)
    for ch in SIGNAL_CHANNELS:
        try:
            entity = await client.get_entity(ch)
            msgs = await client.get_messages(entity, limit=limit)
            fetched.append((ch, str(entity.id), getattr(entity, "title", ch), msgs))
            print(f"Fetched {len(msgs)} messages from @{ch}")
        except Exception as e:
            print(f"@{ch}: fetch failed — {e}")
    await client.disconnect()

    from app.services.signal_pipeline import process_and_broadcast
    saved = 0
    async with async_session() as db:
        for ch, channel_id, title, msgs in fetched:
            # Find or create provider for this channel
            provider = (await db.execute(
                select(Provider).where(Provider.telegram_channel_id == channel_id).limit(1)
            )).scalar_one_or_none()
            if not provider:
                provider = (await db.execute(
                    select(Provider).where(Provider.name == title).limit(1)
                )).scalar_one_or_none()
            if not provider:
                provider = Provider(name=title, source=ProviderSource.TELEGRAM,
                                    description=f"Auto @{ch}", telegram_channel_id=channel_id, is_active=True)
                db.add(provider)
                await db.commit()
                await db.refresh(provider)

            for m in msgs:
                if not m.text or not telegram_parser.is_signal_message(m.text):
                    continue
                parsed = telegram_parser.parse_message(m.text)
                if not parsed:
                    continue

                # Dedup: same ticker+action from this provider
                dup = (await db.execute(
                    select(Signal).where(
                        Signal.provider_id == provider.id,
                        Signal.ticker == parsed.ticker,
                        Signal.action == SignalAction(parsed.action),
                    ).limit(1)
                )).scalar_one_or_none()
                if dup:
                    continue

                signal = Signal(
                    provider_id=provider.id, ticker=parsed.ticker,
                    action=SignalAction(parsed.action), entry_price=parsed.entry_price,
                    take_profit=parsed.take_profit, stop_loss=parsed.stop_loss,
                    raw_message=m.text[:500],
                )
                db.add(signal)
                provider.total_signals = (provider.total_signals or 0) + 1
                await db.commit()
                await db.refresh(signal)

                if broadcast:
                    outcome = await process_and_broadcast(db, signal, provider, source="backfill")
                    await db.refresh(signal)
                    wef = f"{signal.ai_confidence:.0%}" if signal.ai_confidence else "N/A"
                    bc = "VIP-SENT" if outcome.get("broadcast") else f"no-broadcast({outcome.get('reason')})"
                    print(f"  [{ch}] {parsed.action.upper()} {parsed.ticker} @ {signal.entry_price} "
                          f"TP:{signal.take_profit} SL:{signal.stop_loss} | WEF:{wef} | {outcome.get('verdict','')} | {bc}")
                else:
                    try:
                        await ai_rating_service.rate_and_update_signal(db, signal)
                        await db.refresh(signal)
                    except Exception as e:
                        print(f"  (rating failed: {e})")
                    wef = f"{signal.ai_confidence:.0%}" if signal.ai_confidence else "N/A"
                    print(f"  [{ch}] {parsed.action.upper()} {parsed.ticker} @ {parsed.entry_price} "
                          f"TP:{parsed.take_profit} SL:{parsed.stop_loss} | WEF: {wef}")
                saved += 1

    print(f"\n{'='*55}")
    print(f"Backfill complete: {saved} new signals from {len(fetched)} channels")
    print(f"{'='*55}")


if __name__ == "__main__":
    asyncio.run(main())
