"""One-time repair: fix stored signals with absurd R:R (broken tight SL).

Earlier scheduled runs (before the long-horizon guard) overwrote analyst-target
SLs with intraday-scale stops, producing R:R up to 1:20. This resets SL to a
sane +/-10% of entry for any active signal whose R:R > 6.

Usage: python scripts/repair_signals.py
"""

import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import async_session
from app.models.signal import Signal, SignalStatus, SignalAction


async def main():
    fixed = 0
    async with async_session() as db:
        signals = (await db.execute(
            select(Signal).where(Signal.status == SignalStatus.ACTIVE)
        )).scalars().all()

        for s in signals:
            if not s.take_profit or not s.stop_loss or not s.entry_price:
                continue
            if s.action == SignalAction.BUY:
                reward = s.take_profit - s.entry_price
                risk = s.entry_price - s.stop_loss
            else:
                reward = s.entry_price - s.take_profit
                risk = s.stop_loss - s.entry_price
            if risk <= 0:
                continue
            rr = reward / risk
            if rr > 6:
                # Reset SL to a sane 10% adverse move
                if s.action == SignalAction.BUY:
                    s.stop_loss = round(s.entry_price * 0.90, 6)
                else:
                    s.stop_loss = round(s.entry_price * 1.10, 6)
                new_rr = abs(s.take_profit - s.entry_price) / abs(s.entry_price - s.stop_loss)
                fixed += 1
                if fixed <= 20:
                    print(f"  {s.ticker}: R:R 1:{rr:.1f} -> 1:{new_rr:.1f} (SL={s.stop_loss})")
        await db.commit()

    print(f"\nRepaired {fixed} signals with absurd R:R.")


if __name__ == "__main__":
    asyncio.run(main())
