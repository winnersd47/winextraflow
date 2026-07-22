"""Automatic signal poller — runs the backfill+broadcast on an interval.

Every INTERVAL minutes: fetch recent channel messages -> parse -> evolutionary
check + correction -> quality gate -> VIP chart card. Dedup means only NEW
signals are ever broadcast, so re-running is safe.

This is the reliable "automatic" path on a machine where the persistent
real-time worker can't hold the session (stuck backend locks it).

Usage:
    python scripts/poller.py               # every 30 min, all channels
    python scripts/poller.py 15            # every 15 min
    python scripts/poller.py 30 60         # every 30 min, fetch last 60 msgs
"""

import asyncio
import logging
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("poller")

import tg_backfill  # noqa: E402  (same scripts/ dir)


async def main():
    interval_min = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    interval_s = interval_min * 60

    logger.info(f"Signal poller started — every {interval_min} min, last {limit} msgs, VIP broadcast ON")
    cycle = 0
    while True:
        cycle += 1
        logger.info(f"--- Poll cycle #{cycle} ---")
        try:
            await tg_backfill.main(limit=limit, broadcast=True)
        except Exception as e:
            logger.error(f"Poll cycle #{cycle} failed: {e}", exc_info=True)
        logger.info(f"Cycle #{cycle} done. Sleeping {interval_min} min...")
        await asyncio.sleep(interval_s)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Poller stopped by user")
