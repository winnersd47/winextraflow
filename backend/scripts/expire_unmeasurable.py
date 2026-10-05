"""Expire active signals whose outcome cannot honestly be measured.

Four kinds, all of which would otherwise be recorded as real results:

  fabricated stop  the stop sits at exactly -10.0% of entry — the old parser's
                   default, never published by the source. Any outcome measures our
                   own constant, which is the error already removed from the closed
                   record. Repairing the stop instead is not an option: these were
                   published, and moving a published stop rewrites what subscribers
                   were told.
  expired contract FORTS futures past their last trade date (BR-8.26). No live
                   contract, no price, nothing to hit.
  no market data   no candles in the last 90 days, so TP/SL can never be observed
                   (illiquid BTC-quoted pairs like ZIL/BTC, MINA/BTC).
  test leftovers   TESTTICK / STRESST from load testing.

Expired, not deleted: the row stays for the audit trail, it just stops counting.

Usage: python scripts/expire_unmeasurable.py [--apply]
"""
import asyncio, os, sys
from datetime import datetime, timedelta, timezone

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import async_session
from app.models.signal import Signal, SignalStatus
from app.services.backtesting_real import fetch_candles
from app.services.signal_quality import is_seed_signal

FABRICATED_SL_PCT = 0.10
FABRICATED_TOL = 0.0005
TEST_TICKERS = {"TESTTICK", "STRESST", "TESTBTC"}


def fabricated_stop(s: Signal) -> bool:
    if not (s.entry_price and s.stop_loss):
        return False
    d = abs(s.stop_loss - s.entry_price) / s.entry_price
    return abs(d - FABRICATED_SL_PCT) < FABRICATED_TOL


async def main():
    apply = "--apply" in sys.argv
    date_from = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
    date_to = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    async with async_session() as db:
        rows = (await db.execute(
            select(Signal).where(Signal.status == SignalStatus.ACTIVE)
        )).scalars().all()
        rows = [s for s in rows if not is_seed_signal(s)]
        print(f"Активных реальных сигналов: {len(rows)}\n")

        data_ok: dict[str, bool] = {}
        buckets: dict[str, list[Signal]] = {
            "фиктивный стоп -10%": [], "контракт истёк / нет данных": [],
            "тестовые тикеры": [],
        }

        for s in sorted(rows, key=lambda x: x.ticker):
            if s.ticker.upper() in TEST_TICKERS:
                buckets["тестовые тикеры"].append(s)
                continue
            if s.ticker not in data_ok:
                c = await fetch_candles(s.ticker, date_from, date_to)
                data_ok[s.ticker] = bool(c and len(c) >= 5)
            if not data_ok[s.ticker]:
                buckets["контракт истёк / нет данных"].append(s)
                continue
            if fabricated_stop(s):
                buckets["фиктивный стоп -10%"].append(s)

        total = 0
        for why, items in buckets.items():
            if not items:
                continue
            print(f"── {why} ({len(items)}) ──")
            for s in items:
                print(f"   {s.ticker:<10} вход {s.entry_price:<10.4g} "
                      f"стоп {s.stop_loss or 0:<10.4g} {s.created_at:%m-%d}")
                if apply:
                    s.status = SignalStatus.EXPIRED
                total += 1
            print()

        if apply:
            await db.commit()

        left = len(rows) - total
        print(f"К исключению: {total}   останется активных: {left}")
        print(f"\n{'ПРИМЕНЕНО' if apply else 'ПРЕДПРОСМОТР — запустите с --apply'}")


asyncio.run(main())
