"""Standalone Telegram signal worker.

Runs the Telethon channel monitor OUTSIDE the FastAPI process, writing
parsed signals to the same winextraflow.db. Use when port 8000 is blocked
by a stuck backend but you still want live parsing.

Usage: python scripts/run_worker.py
"""

import asyncio
import logging
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from app.database import create_tables
from app.workers.signal_fetcher import telegram_worker


async def main():
    # Ensure tables exist (shared winextraflow.db)
    try:
        await create_tables()
    except Exception as e:
        logging.warning(f"create_tables skipped: {e}")

    await telegram_worker.start()

    if not telegram_worker.client or not telegram_worker.client.is_connected():
        logging.error("Worker did not connect. Is the session authorized? Run tg_signin.py.")
        return

    logging.info("Worker running. Listening for signals... (Ctrl+C to stop)")
    await telegram_worker.client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Worker stopped by user")
