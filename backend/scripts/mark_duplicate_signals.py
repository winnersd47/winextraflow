"""Mark exact duplicates among closed signals so one outcome is counted once.

Found while replaying the eval set: two identical HBAN rows — same ticker, same
entry, same close, same P&L — both counted as closed losses. On a sample of
eleven that is a nine-point shift in the win rate, and it also duplicates one row
in every band of `wef_validation.py`.

Marks rather than deletes. A measured outcome is the scarcest thing this project
owns; a DELETE leaves nothing to audit and cannot be undone if the duplicate
turns out to be two genuine signals that happened to match. The row keeps its
place in the table and every query behind a public number filters it out via
`signal_quality.not_excluded()`.

A duplicate here means: same provider, ticker, action, entry, take profit, stop
loss AND status. The oldest row by `created_at` is kept. Anything less strict
would risk excluding a source that legitimately re-posts the same setup — so
near-matches are reported for a human to look at, never marked automatically.

Usage:
    python scripts/mark_duplicate_signals.py --check   # report, change nothing
    python scripts/mark_duplicate_signals.py           # mark
    python scripts/mark_duplicate_signals.py --unmark   # clear every mark
"""
import asyncio
import os
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.database import async_session
from app.models.signal import Signal, SignalStatus
from app.services.signal_quality import is_seed_signal

CLOSED = (SignalStatus.CLOSED_TP, SignalStatus.CLOSED_SL,
          SignalStatus.CLOSED_MANUAL)
REASON = "duplicate"


def exact_key(s: Signal) -> tuple:
    return (s.provider_id, s.ticker, s.action, s.entry_price,
            s.take_profit, s.stop_loss, s.status)


def relay_key(s: Signal) -> tuple:
    """Everything except which provider published it.

    Two channels relaying one idea match here but not on `exact_key`. That is
    the real case in this database: both BestStocks channels published the same
    HBAN trade. It is not bad data — each provider did publish it — but the
    platform-wide sample counts one market outcome twice, while the per-provider
    win rates are correct as they stand. A single exclusion flag cannot express
    "count once here, twice there", so these are reported and left alone.
    """
    return (s.ticker, s.action, s.entry_price, s.take_profit, s.stop_loss,
            s.status)


def loose_key(s: Signal) -> tuple:
    """Same instrument, direction and entry, but levels or status may differ."""
    return (s.ticker, s.action, s.entry_price)


async def main():
    check_only = "--check" in sys.argv
    unmark = "--unmark" in sys.argv

    async with async_session() as db:
        rows = [s for s in (await db.execute(select(Signal))).scalars().all()
                if not is_seed_signal(s)]
        closed = [s for s in rows if s.status in CLOSED]

        if unmark:
            n = 0
            for s in rows:
                if s.excluded_reason:
                    s.excluded_reason = None
                    n += 1
            await db.commit()
            print(f"Снято отметок: {n}")
            return

        by_exact = defaultdict(list)
        for s in closed:
            by_exact[exact_key(s)].append(s)

        dupes = []           # (kept, extra)
        for group in by_exact.values():
            if len(group) < 2:
                continue
            group.sort(key=lambda x: (x.created_at or x.id.hex))
            for extra in group[1:]:
                dupes.append((group[0], extra))

        print(f"Закрытых реальных сигналов: {len(closed)}")
        print(f"Точных дубликатов найдено:  {len(dupes)}")
        already = sum(1 for s in rows if s.excluded_reason)
        print(f"Уже отмечено ранее:         {already}")

        if dupes:
            print(f"\n{'тикер':<12}{'статус':<14}{'вход':>10}{'P&L':>9}  оставляю от")
            print("-" * 62)
            for kept, extra in dupes:
                when = (kept.created_at.date().isoformat()
                        if kept.created_at else "?")
                print(f"{extra.ticker[:12]:<12}{extra.status.value:<14}"
                      f"{extra.entry_price:>10.2f}"
                      f"{(extra.profit_pct if extra.profit_pct is not None else 0):>8.2f}%"
                      f"  {when}")

        # Same trade, different channel. Reported, never marked — see relay_key.
        by_relay = defaultdict(list)
        for s in closed:
            by_relay[relay_key(s)].append(s)
        relays = [g for g in by_relay.values()
                  if len(g) > 1 and len({x.provider_id for x in g}) > 1]
        if relays:
            extra = sum(len(g) - 1 for g in relays)
            print(f"\nОДИН СИГНАЛ В РАЗНЫХ КАНАЛАХ: {len(relays)} групп, "
                  f"лишних строк {extra}")
            for g in relays:
                print(f"  {g[0].ticker} {g[0].action.value} вход {g[0].entry_price} "
                      f"{g[0].status.value}: {len(g)} канала")
            print(f"  Не отмечаю: по провайдерам это корректно, каждый "
                  f"действительно опубликовал сигнал.")
            print(f"  Но платформенная выборка из {len(closed)} содержит "
                  f"{extra} повторно посчитанных рыночных исхода — "
                  f"фактически независимых наблюдений {len(closed) - extra}.")

        # Near-matches on entry only: a provider re-posting a setup with a
        # different stop is a genuine second signal, not a duplicate.
        by_loose = defaultdict(list)
        for s in closed:
            by_loose[loose_key(s)].append(s)
        near = [g for g in by_loose.values()
                if len(g) > 1 and len({relay_key(x) for x in g}) > 1]
        if near:
            print(f"\nСовпадает только вход ({len(near)} групп) — "
                  f"скорее всего разные сигналы, посмотрите сами:")
            for g in near[:5]:
                print(f"  {g[0].ticker} {g[0].action.value} вход {g[0].entry_price}: "
                      f"{len(g)} строк с разными уровнями или статусом")

        if check_only:
            print("\n--check: изменений не вносил.")
            return
        if not dupes:
            print("\nНечего отмечать.")
            return

        for _, extra in dupes:
            extra.excluded_reason = REASON
        await db.commit()
        print(f"\nОтмечено как дубликаты: {len(dupes)}")
        print("Строки сохранены, но исключены из измеренного результата.")
        print("Дальше: python scripts/recalc_provider_stats.py")


asyncio.run(main())
