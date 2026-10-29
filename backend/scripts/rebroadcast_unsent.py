"""Broadcast ACTIVE signals that were never sent to VIP (tg_vip_message_id is NULL)."""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import async_session, create_tables
from app.models.signal import Signal, SignalStatus
from app.models.provider import Provider
from app.services.signal_pipeline import process_and_broadcast


async def main():
    await create_tables()
    async with async_session() as db:
        rows = (await db.execute(
            select(Signal).where(
                Signal.status == SignalStatus.ACTIVE,
                Signal.tg_vip_message_id == None,
            )
        )).scalars().all()
        print(f"Unsent ACTIVE signals: {len(rows)}")
        sent = 0
        for sig in rows:
            provider = (await db.execute(
                select(Provider).where(Provider.id == sig.provider_id)
            )).scalar_one_or_none()
            if not provider:
                continue
            outcome = await process_and_broadcast(db, sig, provider, source="rebroadcast")
            await db.refresh(sig)
            bc = "VIP-SENT" if outcome.get("broadcast") else f"skip({outcome.get('reason','')})"
            wef = f"{sig.ai_confidence:.0%}" if sig.ai_confidence else "N/A"
            print(f"  {sig.action.upper()} {sig.ticker} @ {sig.entry_price} | WEF:{wef} | {bc}")
            if outcome.get("broadcast"):
                sent += 1
        print(f"\nSent: {sent}/{len(rows)}")

asyncio.run(main())
