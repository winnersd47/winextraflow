"""What each monitored channel actually is: alive, silent, or not a signal source.

The monitored list is fetched every 30 minutes and nothing reports what comes
back. Measured 2026-11-05 it held 17 channels, of which:

  * `forex_vip_signals` looked like the best forex source in the project —
    20 parseable signals out of 20 posts. Its newest post is from 6 April 2021.
    The 48-hour window rejected every one, correctly, and silently, so the
    channel sat in the list for months being polled 48 times a day;
  * ten channels produced zero signals from twenty posts each, because they are
    news feeds, not signal channels. They cost LLM parse attempts and fill the
    rejection log with "4 ноября — выходной";
  * three answer nothing at all: no public web preview.

None of that is visible from the backfill's own output, which prints how many
messages it fetched and nothing about whether they were worth fetching.

Usage:
  py -3.13 scripts/channel_health.py
  py -3.13 scripts/channel_health.py --limit 60
"""
import argparse
import asyncio
import os
import sys
from collections import Counter
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.channel_discovery import load_monitored
from app.services.instruments import asset_class
from app.services.telegram import telegram_parser
from fetch_public import ChannelUnavailable, fetch_channel

# A channel whose newest post is older than this is not a source, it is an
# archive. tg_backfill only looks 48 hours back, so anything beyond a few days
# of silence contributes nothing and costs a request every half hour.
STALE_DAYS = 14
DEAD_DAYS = 90


async def _inspect(channel: str, limit: int) -> dict:
    out = {"channel": channel, "state": "", "posts": 0, "age_days": None,
           "signals": 0, "classes": Counter(), "per_week": 0.0}
    try:
        msgs = await fetch_channel(channel, limit=limit)
    except ChannelUnavailable:
        out["state"] = "нет превью"
        return out
    except Exception as e:
        out["state"] = f"сбой: {type(e).__name__}"
        return out

    out["posts"] = len(msgs)
    dated = [m["date"] for m in msgs if m["date"]]
    now = datetime.now(timezone.utc)
    if dated:
        newest, oldest = max(dated), min(dated)
        out["age_days"] = (now - newest).days
        span = max((newest - oldest).days, 1)
        out["per_week"] = len(dated) / span * 7

    for m in msgs:
        t = m["text"]
        if not (t and telegram_parser.is_signal_message(t)):
            continue
        p = telegram_parser.parse_message(t)
        if p:
            out["signals"] += 1
            out["classes"][asset_class(p.ticker)] += 1

    age = out["age_days"]
    if age is None:
        out["state"] = "без дат"
    elif age >= DEAD_DAYS:
        out["state"] = "МЁРТВ"
    elif age >= STALE_DAYS:
        out["state"] = "молчит"
    elif out["signals"] == 0:
        out["state"] = "не сигнальный"
    else:
        out["state"] = "живой"
    return out


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--class", dest="cls", default=None,
                    help="показать только каналы с этим классом (forex, crypto…)")
    ap.add_argument("--drop-dead", action="store_true",
                    help="убрать недостижимые и молчащие годами; новостные "
                         "каналы не трогает")
    args = ap.parse_args()

    channels = load_monitored()
    print(f"Каналов в списке: {len(channels)}. "
          f"Молчит — свежему посту ≥{STALE_DAYS} дн., мёртв — ≥{DEAD_DAYS}.\n")

    header = (f"{'канал':32}{'состояние':>15}{'посл.пост':>11}"
              f"{'постов/нед':>12}{'сигналов':>10}  классы")
    print(header)
    print("-" * len(header))

    rows = []
    for ch in channels:
        r = await _inspect(ch, args.limit)
        rows.append(r)
        if args.cls and args.cls not in r["classes"]:
            continue
        age = f"{r['age_days']} дн." if r["age_days"] is not None else "—"
        cls = " ".join(f"{k}:{v}" for k, v in r["classes"].most_common()) or "—"
        print(f"{ch[:31]:32}{r['state']:>15}{age:>11}"
              f"{r['per_week']:>12.1f}{r['signals']:>10}  {cls}")

    alive = [r for r in rows if r["state"] == "живой"]
    useless = [r for r in rows if r["state"] in ("МЁРТВ", "нет превью", "не сигнальный")]
    print(f"\nЖивых источников сигналов: {len(alive)} из {len(channels)}.")

    if useless:
        print(f"\nНе дают ничего и опрашиваются каждые 30 минут "
              f"({len(useless)}):")
        for r in useless:
            print(f"   {r['channel']:32} {r['state']}")
        print("   Их стоит убрать из monitored_channels.json: каждый — это "
              "запрос\n   48 раз в сутки и строки в журнале отказов.")

    by_class = Counter()
    for r in alive:
        by_class.update(r["classes"])
    if by_class:
        print(f"\nЧто реально приходит от живых каналов:")
        for k, v in by_class.most_common():
            print(f"   {k:10} {v}")
    forex = by_class.get("forex", 0) + by_class.get("commodity", 0)
    if forex == 0:
        print("\nФорекса живые каналы не дают вообще. Чтобы работать по форексу,"
              "\nисточники нужно заводить — фильтровать здесь нечего.")

    if args.drop_dead:
        # Only the ones that CANNOT produce anything: silent for years, or with
        # no public preview at all. A news channel posts rarely in signal terms
        # but it does post, and dropping it is a product decision, not hygiene.
        doomed = {r["channel"] for r in rows
                  if r["state"] in ("МЁРТВ", "нет превью")}
        if not doomed:
            print("\nУбирать нечего.")
            return 0
        import shutil

        from app.services.channel_discovery import (MONITORED_FILE,
                                                    save_monitored)
        if os.path.exists(MONITORED_FILE):
            shutil.copyfile(MONITORED_FILE, MONITORED_FILE + ".bak")
            print(f"\nРезервная копия: {MONITORED_FILE}.bak")
        kept = [c for c in channels if c not in doomed]
        save_monitored(kept)
        print(f"Убрано {len(doomed)}: {', '.join(sorted(doomed))}")
        print(f"Осталось каналов: {len(kept)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
