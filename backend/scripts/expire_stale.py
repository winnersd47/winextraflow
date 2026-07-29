"""One-time cleanup: expire ACTIVE signals whose entry is far off the live market.

These came from ancient channel history (e.g. BTC entry 43650 from 2024) before
the message-age filter existed. Leaving them ACTIVE makes the monitor report
absurd P&L. Usage: python scripts/expire_stale.py
"""
import asyncio, os, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import select
from app.database import async_session
from app.models.signal import Signal, SignalStatus
from app.services.live_price import get_live_price

TOL = 0.10  # 10%


async def main():
    expired = checked = 0
    price_cache: dict[str, float] = {}
    async with async_session() as db:
        rows = (await db.execute(
            select(Signal).where(Signal.status == SignalStatus.ACTIVE)
            .order_by(Signal.created_at.desc()).limit(300)
        )).scalars().all()

        for s in rows:
            if not s.entry_price:
                continue
            t = s.ticker.upper()
            if t not in price_cache:
                live = await get_live_price(t)
                price_cache[t] = (live or {}).get("price") or 0
                await asyncio.sleep(0.05)
            lp = price_cache[t]
            if lp <= 0:
                continue
            checked += 1
            dev = abs(s.entry_price - lp) / lp
            if dev > TOL:
                s.status = SignalStatus.EXPIRED
                expired += 1
                if expired <= 25:
                    print(f"  {t}: entry {s.entry_price} vs live {lp} ({dev:.0%} off) -> EXPIRED")
        await db.commit()

    print(f"\nChecked {checked} signals with live prices; expired {expired} stale ones.")


asyncio.run(main())
