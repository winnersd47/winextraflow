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

CHANNEL = "beststocksru"


def _proxy():
    if settings.socks5_host and settings.socks5_port:
        import socks
        return (socks.SOCKS5, settings.socks5_host, int(settings.socks5_port), True,
                settings.socks5_user or None, settings.socks5_pass or None)
    return None


async def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 30
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

    entity = await client.get_entity(CHANNEL)
    channel_id = str(entity.id)
    title = getattr(entity, "title", CHANNEL)
    msgs = await client.get_messages(entity, limit=limit)
    await client.disconnect()

    print(f"Fetched {len(msgs)} messages from @{CHANNEL}")

    saved = 0
    async with async_session() as db:
        # Find or create provider
        provider = (await db.execute(
            select(Provider).where(Provider.telegram_channel_id == channel_id).limit(1)
        )).scalar_one_or_none()
        if not provider:
            provider = (await db.execute(
                select(Provider).where(Provider.name == title).limit(1)
            )).scalar_one_or_none()
        if not provider:
            provider = Provider(name=title, source=ProviderSource.TELEGRAM,
                                description=f"Auto @{CHANNEL}", telegram_channel_id=channel_id, is_active=True)
            db.add(provider)
            await db.commit()
            await db.refresh(provider)

        for m in msgs:
            if not m.text:
                continue
            if not telegram_parser.is_signal_message(m.text):
                continue
            parsed = telegram_parser.parse_message(m.text)
            if not parsed:
                continue

            # Dedup: skip if same ticker+action already active from this provider
            dup = (await db.execute(
                select(Signal).where(
                    Signal.provider_id == provider.id,
                    Signal.ticker == parsed.ticker,
                    Signal.action == SignalAction(parsed.action),
                ).limit(1)
            )).scalar_one_or_none()
            if dup:
                print(f"  [skip dup] {parsed.action.upper()} {parsed.ticker}")
                continue

            signal = Signal(
                provider_id=provider.id,
                ticker=parsed.ticker,
                action=SignalAction(parsed.action),
                entry_price=parsed.entry_price,
                take_profit=parsed.take_profit,
                stop_loss=parsed.stop_loss,
                raw_message=m.text[:500],
            )
            db.add(signal)
            provider.total_signals = (provider.total_signals or 0) + 1
            await db.commit()
            await db.refresh(signal)

            # Full pipeline: rate -> evolutionary check + correction -> quality -> VIP
            from app.services.signal_pipeline import process_and_broadcast
            broadcast = "--vip" in sys.argv
            if broadcast:
                outcome = await process_and_broadcast(db, signal, provider, source="backfill")
                await db.refresh(signal)
                wef = f"{signal.ai_confidence:.0%}" if signal.ai_confidence else "N/A"
                bc = "VIP-SENT" if outcome.get("broadcast") else f"no-broadcast({outcome.get('reason')})"
                saved += 1
                print(f"  [SAVED] {parsed.action.upper()} {parsed.ticker} @ {signal.entry_price} "
                      f"TP:{signal.take_profit} SL:{signal.stop_loss} | WEF:{wef} | {outcome.get('verdict','')} | {bc}")
            else:
                # rate only (no broadcast) — safe default
                try:
                    await ai_rating_service.rate_and_update_signal(db, signal)
                    await db.refresh(signal)
                except Exception as e:
                    print(f"  (rating failed: {e})")
                wef = f"{signal.ai_confidence:.0%}" if signal.ai_confidence else "N/A"
                saved += 1
                print(f"  [SAVED] {parsed.action.upper()} {parsed.ticker} @ {parsed.entry_price} "
                      f"TP:{parsed.take_profit} SL:{parsed.stop_loss} | WEF: {wef}")

    print(f"\n{'='*55}")
    print(f"Backfill complete: {saved} new signals saved from @{CHANNEL}")
    print(f"{'='*55}")


if __name__ == "__main__":
    asyncio.run(main())
