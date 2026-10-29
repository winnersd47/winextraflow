"""Take a source off the paper track, or put it back.

`paper_only` is a provider's trial. While it is set, the pipeline parses, rates
and monitors that source's signals but never sends them to a channel — the
reasoning line reads "Paper-only source: measured, not published". That is how
a new channel earns its way in: on its own closed trades, at no cost to
subscribers.

Clearing the flag for everything at once undoes that. The first version of this
script did exactly that, with no argument and no confirmation, and it was run:
on 2026-10-29 all 36 real providers were off the paper track, including Silver
fx (whose XAUUSD setups needed 87–89% of trades to win just to break even) and
AltSignals, neither of which had a single closed trade behind it.

So: name the providers, and say --yes.

Usage:
  python scripts/fix_paper_only.py --list
  python scripts/fix_paper_only.py --off "Silver fx" "AltSignals" --yes   # trial ON
  python scripts/fix_paper_only.py --on  "DluxTrading" --yes              # publish
"""
import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.database import async_session, create_tables
from app.models.provider import Provider
from app.services.measured_stats import MIN_SAMPLE


async def _show(db) -> None:
    rows = (await db.execute(
        select(Provider).where(Provider.is_seed.is_(False))
        .order_by(Provider.total_signals.desc())
    )).scalars().all()
    on_trial = sum(1 for p in rows if p.paper_only)
    print(f"{'испытание':11}{'сигналов':>9}  провайдер")
    for p in rows:
        if not (p.total_signals or 0) and not p.paper_only:
            continue
        print(f"{'ИДЁТ' if p.paper_only else '—':11}{p.total_signals or 0:9}  {p.name}")
    print(f"\nвсего {len(rows)}, на испытании {on_trial}")
    if not on_trial:
        print(f"Ни один источник не на испытании. Порог измеренной истории — "
              f"{MIN_SAMPLE} закрытых сделок.")


async def main() -> int:
    args = sys.argv[1:]
    if not args or "--list" in args:
        await create_tables()
        async with async_session() as db:
            await _show(db)
        return 0

    turn_on = "--on" in args          # --on  = publish this source
    turn_off = "--off" in args        # --off = put it back on the paper track
    if turn_on == turn_off:
        print(__doc__)
        return 1

    flag = args.index("--on" if turn_on else "--off")
    names = [a for a in args[flag + 1:] if not a.startswith("--")]
    if not names:
        print("Укажите хотя бы одного провайдера (можно часть имени).")
        return 1

    await create_tables()
    async with async_session() as db:
        rows = (await db.execute(select(Provider))).scalars().all()
        hits = [p for p in rows
                if any(n.lower() in p.name.lower() for n in names)]
        if not hits:
            print(f"Ничего не найдено по {names}")
            return 1

        want = not turn_on            # --on -> paper_only False
        changes = [p for p in hits if bool(p.paper_only) != want]
        verb = "снять с испытания (начать публиковать)" if turn_on else "вернуть на испытание"
        print(f"Что будет сделано — {verb}:")
        for p in hits:
            mark = "изменится" if p in changes else "уже так"
            print(f"  {p.name}  (сигналов {p.total_signals or 0})  [{mark}]")

        if "--yes" not in args:
            print("\nНичего не изменено. Добавьте --yes, если это то, что нужно.")
            return 0
        if turn_on:
            thin = [p for p in changes if (p.total_signals or 0) < MIN_SAMPLE]
            if thin:
                print(f"\nВНИМАНИЕ: у этих источников меньше {MIN_SAMPLE} сигналов, "
                      f"их статистика ничего не измеряет:")
                for p in thin:
                    print(f"  {p.name} — {p.total_signals or 0}")

        for p in changes:
            p.paper_only = want
        await db.commit()
        print(f"\nИзменено провайдеров: {len(changes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
