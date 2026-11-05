"""Test candidate channels before trusting any list that recommends them.

Every "top 10 forex signal channels" page ranks by subscriber count and
affiliate payout. None of them says whether a channel still posts, whether its
posts contain entry, target and stop, or whether those levels are geometrically
sane. The project already has one channel in its monitored list that was the
best-looking forex source it had — 20 parsed signals out of 20 posts — and had
been silent since April 2021.

So this takes names from anywhere and answers the only questions that matter:

  * does it exist and show a public preview;
  * when did it last post, and how often;
  * how many posts parse into a signal with all three levels;
  * what it trades;
  * does the geometry pass the quality gate, or does the channel publish
    setups that would need 80% of trades to win just to break even.

Nothing here is a recommendation: a channel that posts clean forex setups
daily has passed the entry exam, not the course. The edge still has to be
measured afterwards against random entry, on data the channel was not picked
from.

Usage:
  py -3.13 scripts/scout_channels.py name1 name2 ...
  py -3.13 scripts/scout_channels.py --file candidates.txt --min-signals 3
"""
import argparse
import asyncio
import os
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.instruments import asset_class
from app.services.signal_quality import BREAKEVEN_REJECT_PCT
from app.services.telegram import telegram_parser
from fetch_public import ChannelUnavailable, fetch_channel

FRESH_DAYS = 7


def _breakeven_pct(p) -> float | None:
    if not (p.entry_price and p.take_profit and p.stop_loss):
        return None
    risk = abs(p.entry_price - p.stop_loss)
    reward = abs(p.take_profit - p.entry_price)
    if risk + reward <= 0:
        return None
    return risk / (risk + reward) * 100


async def _scout(name: str, limit: int) -> dict:
    out = {"name": name, "state": "", "posts": 0, "age": None, "per_week": 0.0,
           "signals": 0, "full": 0, "classes": Counter(), "breakeven": None,
           "sane": 0}
    try:
        msgs = await fetch_channel(name, limit=limit)
    except ChannelUnavailable:
        out["state"] = "нет превью"
        return out
    except Exception as e:
        out["state"] = type(e).__name__
        return out

    out["posts"] = len(msgs)
    # Listing sites hand out their own slugs, and several resolve to the same
    # channel: goldsignals and xauhq returned byte-identical posts, as did
    # forexsignals and fxleaders. Counting them separately doubles the apparent
    # number of sources. The newest post identifies the channel well enough.
    out["fingerprint"] = (msgs[0]["text"] or "")[:160] if msgs else ""
    dated = [m["date"] for m in msgs if m["date"]]
    if dated:
        newest, oldest = max(dated), min(dated)
        out["age"] = (datetime.now(timezone.utc) - newest).days
        out["per_week"] = len(dated) / max((newest - oldest).days, 1) * 7

    bes = []
    for m in msgs:
        t = m["text"]
        if not (t and telegram_parser.is_signal_message(t)):
            continue
        p = telegram_parser.parse_message(t)
        if not p:
            continue
        out["signals"] += 1
        out["classes"][asset_class(p.ticker)] += 1
        be = _breakeven_pct(p)
        if be is not None:
            out["full"] += 1
            bes.append(be)
            if be <= BREAKEVEN_REJECT_PCT:
                out["sane"] += 1
    if bes:
        out["breakeven"] = statistics.fmean(bes)

    age = out["age"]
    if age is None:
        out["state"] = "без дат"
    elif age > 90:
        out["state"] = "мёртв"
    elif age > FRESH_DAYS:
        out["state"] = "молчит"
    elif out["full"] == 0:
        out["state"] = "без уровней"
    else:
        out["state"] = "ГОДЕН"
    return out


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--file", default=None, help="по имени в строке")
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--min-signals", type=int, default=1)
    args = ap.parse_args()

    names = list(args.names)
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            names += [ln.strip().lstrip("@") for ln in f
                      if ln.strip() and not ln.startswith("#")]
    names = list(dict.fromkeys(n.lstrip("@") for n in names if n))
    if not names:
        print(__doc__)
        return 1

    print(f"Проверяю {len(names)} кандидатов. «Годен» = постит не реже чем раз "
          f"в {FRESH_DAYS} дн.\nи даёт сетапы со всеми тремя уровнями.\n")
    header = (f"{'канал':30}{'состояние':>13}{'посл.':>7}{'пост/нед':>10}"
              f"{'сигн':>6}{'с уровн':>9}{'безубыт':>9}  классы")
    print(header)
    print("-" * len(header))

    rows = []
    for n in names:
        r = await _scout(n, args.limit)
        rows.append(r)
        age = f"{r['age']}д" if r["age"] is not None else "—"
        be = f"{r['breakeven']:.0f}%" if r["breakeven"] is not None else "—"
        cls = " ".join(f"{k}:{v}" for k, v in r["classes"].most_common(3)) or "—"
        print(f"{n[:29]:30}{r['state']:>13}{age:>7}{r['per_week']:>10.1f}"
              f"{r['signals']:>6}{r['full']:>9}{be:>9}  {cls}")

    good = [r for r in rows
            if r["state"] == "ГОДЕН" and r["full"] >= args.min_signals]

    # Collapse slugs that point at the same channel, keeping the first name.
    seen, unique, twins = {}, [], []
    for r in sorted(good, key=lambda x: -x["full"]):
        fp = r.get("fingerprint") or r["name"]
        if fp in seen:
            twins.append((r["name"], seen[fp]))
            continue
        seen[fp] = r["name"]
        unique.append(r)
    if twins:
        print("Один и тот же канал под разными именами:")
        for dup, keep in twins:
            print(f"   @{dup} = @{keep}")
        print()
    good = unique
    print()
    if not good:
        print("Ни один кандидат не прошёл вступительную проверку.")
        return 0

    print("Прошли проверку:\n")
    for r in good:
        share = r["sane"] / r["full"] * 100 if r["full"] else 0
        main_cls = r["classes"].most_common(1)[0][0] if r["classes"] else "—"
        print(f"  @{r['name']}")
        print(f"     {r['full']} сетапов с уровнями из {r['posts']} постов, "
              f"{r['per_week']:.0f} постов/нед, в основном {main_cls}")
        print(f"     средний безубыток {r['breakeven']:.0f}%, "
              f"{share:.0f}% сетапов проходят порог {BREAKEVEN_REJECT_PCT:.0f}%")
    print("\nЭто вступительная проверка, а не оценка качества: канал пишет "
          "исполнимые\nсетапы — и только. Преимущество меряется потом, против "
          "случайного входа,\nна данных, по которым канал не отбирался. "
          "Добавлять в мониторинг стоит\nсразу как paper_only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
