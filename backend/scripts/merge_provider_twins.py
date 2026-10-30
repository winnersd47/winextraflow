"""Merge provider rows that are the same Telegram channel under two keys.

One channel must be one row. Every flag that decides what happens to a signal —
`paper_only`, `is_active` — lives on the row, and so does the measured history
the WEF Score and the track record read. A twin splits both: a source on trial
gets published through its unmarked copy, and a win rate is computed over half
the trades.

The keys changed twice. Rows written under Telethon hold the numeric channel id
and the channel's real title ("BestStocks | Инвест-идеи США"); rows registered
by hand hold the username; rows written since the move to the public web
preview hold the username in both the key and the name. The first backfill run
after that move created 17 new rows on 2026-10-29, one per monitored channel.

What survives a merge: the row with the most signals, since that is the one the
history and the rating already point at. On a tie the OLDER row wins — it holds
the readable name a person gave the channel ("MarketTwits", "Web 3.0 :: Web3"),
and the new rows are named after the username. Its `telegram_channel_id` is set
to the username, the only key available now, and `paper_only` stays ON if ANY
twin had it: a trial must never be lost to a merge, which is the failure this
whole file exists to prevent.

Usage:
  py -3.13 scripts/merge_provider_twins.py            # показать, что будет
  py -3.13 scripts/merge_provider_twins.py --yes      # выполнить
"""
import asyncio
import os
import re
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func, select, update

from app.database import async_session, create_tables
from app.models.provider import Provider
from app.models.signal import Signal

_AT = re.compile(r"@([0-9A-Za-z_]{3,})")


def _username(p: Provider) -> str | None:
    """The channel this row belongs to, lower-cased for grouping."""
    key = (p.telegram_channel_id or "").strip()
    if key and not key.lstrip("-").isdigit():
        return key.lower()
    m = _AT.search(p.description or "")
    return m.group(1).lower() if m else None


async def _has_strategy(db, provider_id) -> bool:
    from app.models.strategy import Strategy
    return bool((await db.execute(select(Strategy.id).where(
        Strategy.provider_id == provider_id).limit(1))).scalar_one_or_none())


async def main() -> int:
    apply = "--yes" in sys.argv
    await create_tables()

    async with async_session() as db:
        providers = (await db.execute(
            select(Provider).where(Provider.is_seed.is_(False)))).scalars().all()

        counts = dict((pid, n) for pid, n in (await db.execute(
            select(Signal.provider_id, func.count())
            .group_by(Signal.provider_id))).all())

        groups: dict[str, list[Provider]] = defaultdict(list)
        for p in providers:
            u = _username(p)
            if u:
                groups[u].append(p)

        twins = {u: ps for u, ps in groups.items() if len(ps) > 1}
        if not twins:
            print("Дублей нет — у каждого канала одна строка.")
            return 0

        merged = moved = 0
        for u, ps in sorted(twins.items()):
            # Most signals first; then oldest, so a tie keeps the curated name
            # rather than the username-shaped row the backfill just made.
            oldest = min((p.created_at for p in ps if p.created_at), default=None)
            ps.sort(key=lambda p: (-counts.get(p.id, 0),
                                   p.created_at or oldest or 0))
            keep, drop = ps[0], ps[1:]
            trial = any(p.paper_only for p in ps)

            print(f"\n@{u}")
            print(f"  остаётся: {keep.name}  (сигналов {counts.get(keep.id, 0)}"
                  f"{', на испытании' if keep.paper_only else ''})")
            for p in drop:
                n = counts.get(p.id, 0)
                print(f"  сливается: {p.name}  (сигналов {n}"
                      f"{', на испытании' if p.paper_only else ''})")
                moved += n
            if trial and not keep.paper_only:
                print(f"  → испытание переносится на остающуюся строку")

            if not apply:
                continue

            for p in drop:
                await db.execute(update(Signal)
                                 .where(Signal.provider_id == p.id)
                                 .values(provider_id=keep.id))
                # strategies.provider_id is UNIQUE, so a twin that already has
                # a marketplace strategy cannot simply be pointed at `keep`.
                # Leave that row alone and say so rather than raise mid-merge.
                if await _has_strategy(db, p.id):
                    print(f"  ПРОПУЩЕН {p.name}: у строки есть стратегия в "
                          f"маркетплейсе, слияние сделало бы две на одного "
                          f"провайдера. Разберите вручную.")
                    continue
                await db.delete(p)
            keep.telegram_channel_id = u
            keep.paper_only = trial
            keep.total_signals = (await db.execute(
                select(func.count()).select_from(Signal)
                .where(Signal.provider_id == keep.id))).scalar() or 0
            merged += len(drop)

        if not apply:
            print(f"\nЭто предпросмотр: {sum(len(p) - 1 for p in twins.values())} "
                  f"строк под слияние. Выполнить: --yes")
            return 0

        await db.commit()
        print(f"\nСлито строк: {merged}. Перенесено сигналов: {moved}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
