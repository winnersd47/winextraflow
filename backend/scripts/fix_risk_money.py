"""Backfill `paper_trades.risk_money` with what each stop actually costs.

`position_size` used to return the risk *budget* (deposit x risk %) as
`risk_money`, even when the 25%-of-deposit share cap had cut the position down.
Where the cap fired, the stored figure overstates the loss — in the worst row on
record by 12x (1000 RUB claimed, 81 RUB actual).

The field is reporting-only: realised P&L is computed from `result_pct` and
`position_value`, so no outcome changes. But it is served by /api/v1/paper/trades
as a fact, and the fix in position_sizing.py only affects trades opened from now
on. This corrects the rows already written.

Usage:
    python scripts/fix_risk_money.py --check   # report, change nothing
    python scripts/fix_risk_money.py           # write
"""
import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.database import async_session
from app.models.paper import PaperTrade


async def main():
    check_only = "--check" in sys.argv
    async with async_session() as db:
        rows = (await db.execute(select(PaperTrade))).scalars().all()

        fixed = []
        for t in rows:
            if not t.entry_price or not t.stop_loss:
                continue
            actual = t.position_value * abs(t.entry_price - t.stop_loss) / t.entry_price
            if abs(actual - (t.risk_money or 0)) <= 0.01:
                continue
            fixed.append((t.ticker, t.risk_money, actual))
            if not check_only:
                t.risk_money = round(actual, 2)

        print(f"Сделок всего: {len(rows)}")
        print(f"С неверным risk_money: {len(fixed)}")
        if fixed:
            over = sum(old - new for _, old, new in fixed)
            print(f"Суммарное завышение: {over:,.0f} ₽".replace(",", " "))
            print("\nПервые 10:")
            for tk, old, new in fixed[:10]:
                print(f"  {tk:<12} {old:>8.0f} → {new:>8.0f} ₽")

        if check_only:
            print("\n--check: изменений не вносил.")
            return
        if fixed:
            await db.commit()
            print(f"\nОбновлено строк: {len(fixed)}")
        else:
            print("\nНечего исправлять.")


asyncio.run(main())
