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
from app.services.signal_levels import resolve_levels
from app.services.llm_parse_ledger import ParseLedger

# Channels to scan are loaded per-run from the UI-managed monitored list
# (monitored_channels.json, seeded from .env). See load_monitored().
from app.services.channel_discovery import load_monitored

# Ignore channel posts older than this — prevents ancient history being ingested
# as fresh signals (stale entry prices produce absurd P&L).
MAX_MESSAGE_AGE_HOURS = 48

# LLM fallback budget for one run. The job runs every 30 minutes (48 runs/day), so
# this is the daily ceiling divided by the number of runs, with headroom for the
# insight endpoints that share the same OpenRouter key.
#   free tier without credits: 50 requests/day in total  -> keep this at 1
#   free tier with $10 credit: 1000 requests/day         -> 10 is comfortable
# Override per environment with LLM_PARSE_PER_RUN.
MAX_LLM_PARSE_PER_RUN = int(os.getenv("LLM_PARSE_PER_RUN", "10"))


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

    # Fetch messages from all monitored channels while connected (fresh list per run).
    # Only RECENT messages: channels keep years of history and an old post (e.g. BTC at
    # 43650 from 2024) would otherwise be ingested as a fresh signal.
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_MESSAGE_AGE_HOURS)
    channels = load_monitored()
    fetched = []  # list of (username, entity_id, title, messages)
    for ch in channels:
        try:
            entity = await client.get_entity(ch)
            msgs = await client.get_messages(entity, limit=limit)
            fresh = [m for m in msgs if m.date and m.date >= cutoff]
            skipped = len(msgs) - len(fresh)
            fetched.append((ch, str(entity.id), getattr(entity, "title", ch), fresh))
            note = f" ({skipped} too old, skipped)" if skipped else ""
            print(f"Fetched {len(fresh)}/{len(msgs)} recent messages from @{ch}{note}")
        except Exception as e:
            print(f"@{ch}: fetch failed — {e}")
    await client.disconnect()

    from app.services.signal_pipeline import process_and_broadcast
    saved = 0
    llm_parsed = 0
    # One attempt per message, ever: the same post is re-read ~48 times before
    # it ages out of the window, and each re-read would otherwise be an LLM call.
    ledger = ParseLedger(max_per_run=MAX_LLM_PARSE_PER_RUN)
    async with async_session() as db:
        for ch, channel_id, title, msgs in fetched:
            # Find or create provider for this channel.
            #
            # Three lookups, and the middle one matters: a provider registered by
            # hand (scripts/add_trial_source.py) stores the USERNAME, while this
            # loop stores the numeric id. Matching only on the numeric id created
            # a second row per channel — and since the flags live on the row, a
            # source marked `paper_only` was ingested through its unmarked twin
            # and published to subscribers. The trial it was under did nothing.
            provider = (await db.execute(
                select(Provider).where(Provider.telegram_channel_id == channel_id).limit(1)
            )).scalar_one_or_none()
            if not provider and ch:
                provider = (await db.execute(
                    select(Provider).where(Provider.telegram_channel_id == ch).limit(1)
                )).scalar_one_or_none()
                if provider:
                    # Found by username: store the numeric id so the first lookup
                    # matches next time, and no twin is ever created.
                    provider.telegram_channel_id = channel_id
                    await db.commit()
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
                    # The regex parsers cover four channels with a recognisable
                    # format. Everything else — most RU channels write the signal as
                    # prose — was silently dropped here, which is why the LLM parser
                    # existed but never ran on the path that actually runs on cron.
                    if ledger.should_try(ch, m.id):
                        ledger.mark(ch, m.id)
                        try:
                            parsed = await telegram_parser.parse_with_llm(m.text)
                        except Exception as e:
                            print(f"  [{ch}] LLM-парсер упал: {e}")
                            parsed = None
                        if parsed:
                            llm_parsed += 1
                            print(f"  [{ch}] LLM разобрал: {parsed.action.upper()} "
                                  f"{parsed.ticker} @ {parsed.entry_price}")
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

                # Analyst formats give only direction + target: anchor the entry to
                # the live market and size the stop by ATR before storing.
                lv = await resolve_levels(
                    parsed.ticker, parsed.action, parsed.entry_price,
                    parsed.take_profit, parsed.stop_loss,
                    derived=getattr(parsed, "derived_levels", False),
                )
                if not lv["usable"]:
                    continue
                if lv["notes"]:
                    print(f"  [{ch}] {parsed.ticker}: " + "; ".join(lv["notes"]))

                signal = Signal(
                    provider_id=provider.id, ticker=parsed.ticker,
                    action=SignalAction(parsed.action), entry_price=lv["entry"],
                    take_profit=lv["take_profit"], stop_loss=lv["stop_loss"],
                    long_target=lv["long_target"],
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
