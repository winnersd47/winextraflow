"""Fill `close_price` and `profit_pct` on closed signals that are missing them.

8 of the 11 closed real signals carry neither field. They were closed by a path
that only set the status, so the outcome is recorded as "this hit the stop" with
no number attached. Consequences:

  * `recalculate_provider_stats` collects `profit_pct` and needs >= 3 values per
    provider for Sharpe / Profit Factor / Max Drawdown. With 3 usable values
    across 4 providers, those three WEF factors stay NULL — 35% of the score's
    weight frozen at a constant 0.5.
  * the eval set has no magnitude to correlate against, only a win/lose label.

Nothing is invented here. The project's rule is that a closed signal realizes at
its closing LEVEL, not at some later market price: CLOSED_TP realizes at
`take_profit`, CLOSED_SL at `stop_loss`. That is the same formula
`ai_rating.close_signal` applies, and the same invariant `paper_trades` relies on.
Rows that already have a value are left alone.

Usage:
    python scripts/backfill_closed_pnl.py --check   # report, change nothing
    python scripts/backfill_closed_pnl.py           # write
"""
import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.database import async_session
from app.models.signal import Signal, SignalAction, SignalStatus
from app.services.signal_quality import is_seed_signal


def closing_level(s: Signal) -> float | None:
    """The level this signal settled at, by its own status."""
    if s.status == SignalStatus.CLOSED_TP:
        return s.take_profit
    if s.status == SignalStatus.CLOSED_SL:
        return s.stop_loss
    return None                      # CLOSED_MANUAL has no implied level


def pnl_pct(s: Signal, close: float) -> float:
    delta = (close - s.entry_price) / s.entry_price * 100
    return -delta if s.action == SignalAction.SELL else delta


async def main():
    check_only = "--check" in sys.argv
    async with async_session() as db:
        rows = [s for s in (await db.execute(select(Signal))).scalars().all()
                if not is_seed_signal(s)
                and s.status in (SignalStatus.CLOSED_TP, SignalStatus.CLOSED_SL,
                                 SignalStatus.CLOSED_MANUAL)]

        fixed, skipped = [], []
        for s in rows:
            if s.profit_pct is not None and s.close_price is not None:
                continue
            level = s.close_price if s.close_price is not None else closing_level(s)
            if level is None or not s.entry_price:
                skipped.append((s.ticker, s.status.value,
                                "нет уровня закрытия" if level is None
                                else "нет цены входа"))
                continue
            fixed.append((s.ticker, s.status.value, level, pnl_pct(s, level)))
            if not check_only:
                s.close_price = level
                s.profit_pct = round(pnl_pct(s, level), 4)

        print(f"Закрытых реальных сигналов: {len(rows)}")
        print(f"Требуют заполнения:         {len(fixed) + len(skipped)}")
        print(f"  восстановимо:             {len(fixed)}")
        print(f"  не восстановимо:          {len(skipped)}")

        if fixed:
            print(f"\n{'тикер':<12}{'статус':<12}{'уровень':>10}{'P&L':>9}")
            print("-" * 44)
            for tk, st, lv, p in fixed:
                print(f"{tk[:12]:<12}{st:<12}{lv:>10.2f}{p:>8.2f}%")
        for tk, st, why in skipped:
            print(f"  пропущен {tk} ({st}): {why}")

        if check_only:
            print("\n--check: изменений не вносил.")
            return
        if fixed:
            await db.commit()
            print(f"\nОбновлено сигналов: {len(fixed)}")
        else:
            print("\nНечего заполнять.")

        # Duplicates are visible from here but deliberately not touched: deleting
        # a measured outcome is a separate, deliberate decision.
        seen, dupes = {}, []
        for s in rows:
            key = (s.ticker, s.entry_price, s.status)
            if key in seen:
                dupes.append(s.ticker)
            seen[key] = True
        if dupes:
            print(f"\nВНИМАНИЕ: похожие дубликаты закрытых сделок: "
                  f"{sorted(set(dupes))}. Не удалял — это отдельное решение, "
                  f"но они искажают win rate и выборку.")


asyncio.run(main())
