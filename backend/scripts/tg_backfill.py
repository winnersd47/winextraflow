"""Backfill: read monitored channels, parse, save + rate.

fetch -> parse -> save to DB -> AI rating (WEF Score). Runs on cron every 30
minutes.

Reads channels over the public web preview (scripts/fetch_public.py) rather
than Telethon: the scheduled job then carries no user auth key, and cannot
repeat the revocation that cost the pipeline 37 days.

Usage: python scripts/tg_backfill.py [limit] [--vip]
"""

import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

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
from scripts.fetch_public import ChannelUnavailable, fetch_channel

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


async def main(limit: int | None = None, broadcast: bool | None = None):
    limit = limit if limit is not None else (int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 30)
    if broadcast is None:
        broadcast = "--vip" in sys.argv
    await create_tables()

    # Only RECENT messages: channels keep years of history and an old post (e.g.
    # BTC at 43650 from 2024) would otherwise be ingested as a fresh signal.
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_MESSAGE_AGE_HOURS)
    channels = load_monitored()
    # list of (username, channel_id_str, title, messages_dicts)
    fetched = []
    for ch in channels:
        try:
            msgs = await fetch_channel(ch, limit=limit)
            # A post with no timestamp is skipped, not kept. Treating an unknown
            # date as fresh defeats the window entirely — and the window is the
            # only thing standing between a year-old post and a signal card
            # priced off it.
            fresh = [m for m in msgs if m["date"] and m["date"] >= cutoff]
            undated = sum(1 for m in msgs if not m["date"])
            skipped = len(msgs) - len(fresh)
            # The web preview gives no numeric channel id, and nothing downstream
            # needs one — the username is the stable key.
            fetched.append((ch, ch, ch, fresh))
            note = f" ({skipped} too old, skipped)" if skipped else ""
            if undated:
                note += f" [{undated} без даты — пропущены]"
            print(f"Fetched {len(fresh)}/{len(msgs)} recent messages from @{ch}{note}")
        except ChannelUnavailable as e:
            # Distinct from a network error: this one needs the channel's owner
            # or a different source, and retrying will never fix it.
            print(f"{e}")
        except Exception as e:
            print(f"@{ch}: fetch failed — {e}")

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
                text = m["text"]
                if not text or not telegram_parser.is_signal_message(text):
                    continue
                parsed = telegram_parser.parse_message(text)
                if not parsed:
                    # The regex parsers cover the channels with a recognisable
                    # format. Everything else — most RU channels write the signal
                    # as prose — was silently dropped here, which is why the LLM
                    # parser existed but never ran on the path that runs on cron.
                    #
                    # Keyed by the post's own id ("channel/12345"), which the web
                    # preview carries. An earlier version hashed the message text
                    # instead: that made every edit to a post look like a new one
                    # and spent another LLM call on it.
                    msg_id = m["id"]
                    if ledger.should_try(ch, msg_id):
                        ledger.mark(ch, msg_id)
                        try:
                            parsed = await telegram_parser.parse_with_llm(text)
                        except Exception as e:
                            print(f"  [{ch}] LLM-парсер упал: {e}")
                            parsed = None
                        if parsed:
                            llm_parsed += 1
                            print(f"  [{ch}] LLM разобрал: {parsed.action.upper()} "
                                  f"{parsed.ticker} @ {parsed.entry_price}")
                if not parsed:
                    continue

                # Dedup: same ticker+action from this provider, within a window
                # rather than over all history. Unbounded, a source that calls
                # the same instrument again a month later is silently dropped —
                # which is a normal re-entry, not a duplicate. Seven days is
                # longer than the median 6-bar resolution and shorter than the
                # 21-day expiry, so a live signal is never double-counted.
                week_ago = datetime.now(timezone.utc) - timedelta(days=7)
                dup = (await db.execute(
                    select(Signal).where(
                        Signal.provider_id == provider.id,
                        Signal.ticker == parsed.ticker,
                        Signal.action == SignalAction(parsed.action),
                        Signal.created_at >= week_ago,
                    ).limit(1)
                )).scalar_one_or_none()
                if dup:
                    continue

                # Analyst formats give only direction + target: anchor the entry
                # to the live market and size the stop by ATR before storing.
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
                    raw_message=text[:500],
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
