"""Broadcast pending (un-sent) signals to VIP with chart cards, throttled.

Runs saved-but-not-broadcast signals through the full pipeline (rate ->
evolutionary check+correction -> quality -> VIP chart card). Marks each with
"VIP-CARD" so re-runs skip. Throttled to avoid flooding.

Usage: python scripts/broadcast_pending.py [max] [delay_seconds]
"""

import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import async_session
from app.models.provider import Provider, ProviderSource
from app.models.signal import Signal, SignalStatus
from app.services.signal_pipeline import process_and_broadcast

MARKER = "VIP-CARD"


async def main():
    max_n = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    delay = float(sys.argv[2]) if len(sys.argv) > 2 else 4.0

    async with async_session() as db:
        # Telegram providers (beststocks / ricesignal / etc.)
        provs = (await db.execute(
            select(Provider).where(Provider.source == ProviderSource.TELEGRAM)
        )).scalars().all()
        prov_ids = [p.id for p in provs]
        if not prov_ids:
            print("No telegram providers"); return

        signals = (await db.execute(
            select(Signal).where(
                Signal.provider_id.in_(prov_ids),
                Signal.status == SignalStatus.ACTIVE,
            ).order_by(Signal.created_at.desc()).limit(120)
        )).scalars().all()

        pending = [s for s in signals if MARKER not in (s.ai_reasoning or "")]
        print(f"{len(pending)} pending signals (of {len(signals)} active). Broadcasting up to {max_n}...")

        sent = 0
        for s in pending:
            if sent >= max_n:
                break
            prov = next((p for p in provs if p.id == s.provider_id), None)
            outcome = await process_and_broadcast(db, s, prov, source="backlog")
            # mark to prevent re-send
            s.ai_reasoning = (s.ai_reasoning or "") + f" | {MARKER}"
            await db.commit()
            bc = "SENT" if outcome.get("broadcast") else f"skip({outcome.get('reason')})"
            print(f"  {s.action.value.upper()} {s.ticker} @ {s.entry_price} "
                  f"TP:{s.take_profit} SL:{s.stop_loss} | {outcome.get('verdict','')} | {bc}")
            if outcome.get("broadcast"):
                sent += 1
                await asyncio.sleep(delay)

        print(f"\nBroadcast {sent} chart cards to VIP.")


if __name__ == "__main__":
    asyncio.run(main())
