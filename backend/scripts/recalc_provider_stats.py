"""Recompute provider aggregates for every provider that has closed signals.

Why this exists: `recalculate_provider_stats` was only ever called from
`ai_rating.close_signal` (the API path) and from seed data. The path that actually
closes signals in production is `monitor_signals.py`, which set the status and
committed directly. So `win_rate`, `sharpe_ratio`, `profit_factor` and
`max_drawdown` were NULL for all 15 real providers despite 11 closed signals
existing.

That is not a cosmetic gap. Five of the nine WEF factors read those columns and
return a neutral 0.5 when they are missing, which froze 55% of the score's weight
at a constant and left the score with 7 distinct values across 153 signals.

The monitor now calls the recalc itself; this backfills what it missed.

Usage:
    python scripts/recalc_provider_stats.py --check   # report, change nothing
    python scripts/recalc_provider_stats.py           # recompute
"""
import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.database import async_session
from app.models.provider import Provider
from app.models.signal import Signal, SignalStatus
from app.services.ai_rating import ai_rating_service
from app.services.signal_quality import is_seed_signal

CLOSED = (SignalStatus.CLOSED_TP, SignalStatus.CLOSED_SL, SignalStatus.CLOSED_MANUAL)


def _filled(p: Provider) -> int:
    return sum(x is not None for x in
               (p.win_rate, p.sharpe_ratio, p.profit_factor, p.max_drawdown))


async def main():
    check_only = "--check" in sys.argv
    async with async_session() as db:
        provs = (await db.execute(select(Provider))).scalars().all()
        real = [p for p in provs if not getattr(p, "is_seed", False)]

        # Only providers with real closed signals can produce aggregates at all.
        sigs = [s for s in (await db.execute(select(Signal))).scalars().all()
                if not is_seed_signal(s)]
        closed_by_provider: dict = {}
        for s in sigs:
            if s.status in CLOSED:
                closed_by_provider.setdefault(s.provider_id, 0)
                closed_by_provider[s.provider_id] += 1

        before = {p.id: _filled(p) for p in real}
        print(f"Реальных провайдеров: {len(real)}")
        print(f"Заполнено 4/4 полей до: "
              f"{sum(1 for v in before.values() if v == 4)}")
        print(f"Провайдеров с закрытыми сделками: {len(closed_by_provider)}")
        print(f"Закрытых реальных сделок всего: {sum(closed_by_provider.values())}")

        if check_only:
            print("\n--check: изменений не вносил.")
            return

        touched = 0
        for p in real:
            if p.id not in closed_by_provider:
                continue
            await ai_rating_service.recalculate_provider_stats(db, p.id)
            touched += 1

        # Re-read and report what actually became available. sharpe/pf/dd need
        # >= 3 closes for one provider, so most will legitimately stay NULL —
        # the point is to see which, not to assume.
        provs = (await db.execute(select(Provider))).scalars().all()
        real = [p for p in provs if not getattr(p, "is_seed", False)]

        print(f"\nПересчитано провайдеров: {touched}")
        print(f"\n{'провайдер':<28} {'закр':>5} {'WR':>7} {'Sharpe':>8} "
              f"{'PF':>7} {'DD':>8}")
        print("-" * 68)
        for p in sorted(real, key=lambda x: -closed_by_provider.get(x.id, 0)):
            n = closed_by_provider.get(p.id, 0)
            if not n:
                continue
            wr = f"{p.win_rate:.0%}" if p.win_rate is not None else "—"
            sh = f"{p.sharpe_ratio:.2f}" if p.sharpe_ratio is not None else "—"
            pf = f"{p.profit_factor:.2f}" if p.profit_factor is not None else "—"
            dd = f"{p.max_drawdown:.1f}" if p.max_drawdown is not None else "—"
            print(f"{p.name[:28]:<28} {n:>5} {wr:>7} {sh:>8} {pf:>7} {dd:>8}")

        filled_now = sum(1 for p in real if _filled(p) == 4)
        any_now = sum(1 for p in real if _filled(p) > 0)
        print("-" * 68)
        print(f"Хотя бы одно поле заполнено: {any_now}/{len(real)}")
        print(f"Все четыре заполнены:        {filled_now}/{len(real)}")
        from app.services.ai_rating import (MIN_CLOSED_FOR_RATIOS,
                                            MIN_CLOSED_FOR_WIN_RATE)
        print(f"\nsharpe/pf/dd требуют >={MIN_CLOSED_FOR_RATIOS} закрытых сделок "
              f"у ОДНОГО провайдера, win rate в скоринге — "
              f">={MIN_CLOSED_FOR_WIN_RATE}. Прочерк там честен, а не сломан: "
              f"на четырёх сделках Шарп давал -69.03.")


asyncio.run(main())
