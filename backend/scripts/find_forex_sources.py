"""Search Telegram for channels that actually publish parseable forex signals.

The platform has none. Of 161 real signals, zero are forex or commodity: 81% are
US equities, 11% MOEX, the rest crypto and FORTS futures. The one forex-looking
channel in the config, @forexfactory ("GOLD EMPIRE"), posts results rather than
setups — "Target Hit", "+190 pips running", "Entry 1: +600 Pips Done" — with no
entry, target or stop in any readable form, and an invitation to a paid VIP. The
parser is right to reject it.

So this searches instead of guessing usernames. It asks Telegram for public
channels matching forex-related queries, reads their recent public history, and
reports what fraction of messages the project's own parser can turn into a
signal. A channel that scores zero is not a source, however large its audience.

Nothing is joined and nothing is written: this reads public history and prints a
report. Runs under the Telethon lock, because an unlocked second client is what
revoked the auth key and cost the project 37 days.

Usage:
    python scripts/find_forex_sources.py
    python scripts/find_forex_sources.py --limit 60   # messages per channel
    python scripts/find_forex_sources.py --json
"""
import asyncio
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.instruments import asset_class
from app.services.telegram import telegram_parser
from app.services.telethon_lock import telethon_session

QUERIES = [
    "forex signals", "forex vip signals", "xauusd signals", "gold signals",
    "форекс сигналы", "форекс трейдинг сигналы", "fx signals",
    "eurusd signals", "free forex signals", "сигналы форекс золото",
]

# Reading a lot of history from many channels in a row invites a flood wait.
PER_CHANNEL = 40
PAUSE = 1.2


def classify(parsed) -> str:
    return asset_class(parsed.ticker) if parsed else "?"


async def probe(client, entity, limit: int) -> dict | None:
    """Parse yield for one channel. None when it cannot be read at all."""
    try:
        msgs = [m async for m in client.iter_messages(entity, limit=limit)
                if m.text]
    except Exception as e:
        return {"error": f"{type(e).__name__}"}

    if not msgs:
        return {"error": "нет сообщений"}

    looks_like = parsed_ok = 0
    classes: dict[str, int] = {}
    samples: list[str] = []
    for m in msgs:
        if not telegram_parser.is_signal_message(m.text):
            continue
        looks_like += 1
        p = telegram_parser.parse_message(m.text)
        if not p:
            continue
        parsed_ok += 1
        cls = classify(p)
        classes[cls] = classes.get(cls, 0) + 1
        if len(samples) < 2:
            samples.append(f"{p.ticker} {p.action} @{p.entry_price} "
                           f"TP:{p.take_profit} SL:{p.stop_loss}")

    fx = classes.get("forex", 0) + classes.get("commodity", 0)
    return {
        "messages": len(msgs),
        "look_like_signals": looks_like,
        "parsed": parsed_ok,
        "forex_or_commodity": fx,
        "classes": classes,
        "samples": samples,
    }


async def main():
    limit = PER_CHANNEL
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    as_json = "--json" in sys.argv

    from telethon.tl.functions.contacts import SearchRequest

    async with telethon_session("wef_backfill", timeout=120) as client:
        if client is None:
            print("Telethon занят другим процессом — попробуйте позже")
            return 1

        found: dict[str, object] = {}
        for q in QUERIES:
            try:
                res = await client(SearchRequest(q=q, limit=30))
            except Exception as e:
                print(f"  поиск «{q}» не удался: {type(e).__name__}", file=sys.stderr)
                continue
            for ch in res.chats:
                uname = getattr(ch, "username", None)
                if not uname or getattr(ch, "broadcast", False) is False:
                    continue
                found.setdefault(uname, ch)
            await asyncio.sleep(PAUSE)

        print(f"Найдено публичных каналов: {len(found)}", file=sys.stderr)

        rows = []
        for i, (uname, ch) in enumerate(found.items(), 1):
            print(f"  [{i}/{len(found)}] @{uname}", file=sys.stderr)
            r = await probe(client, ch, limit)
            await asyncio.sleep(PAUSE)
            if not r or r.get("error"):
                continue
            rows.append({
                "username": uname,
                "title": getattr(ch, "title", ""),
                "subscribers": getattr(ch, "participants_count", None),
                **r,
            })

    # A source is only useful if the parser can read it. Rank on that, not size.
    rows.sort(key=lambda r: (r["forex_or_commodity"], r["parsed"]), reverse=True)

    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    print("=" * 74)
    print("КАНАЛЫ, ЧЬИ СООБЩЕНИЯ ПАРСЕР РЕАЛЬНО ПРЕВРАЩАЕТ В СИГНАЛ")
    print("=" * 74)
    print(f"{'канал':<26}{'похоже':>8}{'разобр':>8}{'FX':>5}  классы")
    print("-" * 74)
    usable = 0
    for r in rows:
        if r["parsed"] == 0:
            continue
        usable += 1
        cls = " ".join(f"{k}:{v}" for k, v in sorted(r["classes"].items(),
                                                     key=lambda x: -x[1]))
        print(f"@{r['username'][:24]:<25}{r['look_like_signals']:>8}"
              f"{r['parsed']:>8}{r['forex_or_commodity']:>5}  {cls}")
        for s in r["samples"]:
            print(f"      {s}")

    print("-" * 74)
    print(f"Просмотрено каналов: {len(rows)}   с разбираемыми сигналами: {usable}")
    fx_sources = [r for r in rows if r["forex_or_commodity"] > 0]
    print(f"Из них дают forex/сырьё: {len(fx_sources)}")
    if not fx_sources:
        print("\nНи один канал не даёт разбираемых валютных сигналов. Это говорит\n"
              "о рынке, а не о парсере: публичные forex-каналы в массе публикуют\n"
              "скриншоты и отчёты о прибыли, а конкретные уровни держат в платном\n"
              "доступе.")
    return 0


sys.exit(asyncio.run(main()))
