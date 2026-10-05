"""Remove non-measurements from the closed-trade record.

18 closed real trades currently back the public track record. Auditing them:

  * 10 carry a stop at exactly -10.0% of entry — the parser's fabricated default,
    not a level any source published. Their "loss" measures our own constant.
  * 1 is the stale BTCUSDT signal (entry 43650 parsed from old channel history).
    It is recorded as CLOSED_TP and is the single win in the entire record.
  * 2 are an exact duplicate pair (AMD, same entry/TP/SL, same minute).

That leaves the honest sample far below anything publishable, which is the correct
answer — a track record has to be trades we actually measured.

Statuses used:
  EXPIRED  — never a real trade; excluded from every performance figure.

Usage: python scripts/fix_track_record_honesty.py [--apply]
"""
import asyncio, os, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import async_session
from app.models.signal import Signal, SignalStatus
from app.services.live_price import stale_tolerance
from app.services.signal_quality import is_seed_signal

CLOSED = (SignalStatus.CLOSED_TP, SignalStatus.CLOSED_SL)
SYNTHETIC_SL_PCT = 0.10
SYNTHETIC_TOL = 0.0005      # 10.00% +/- 0.05pp — the fabricated default's signature


def synthetic_stop(s: Signal) -> bool:
    if not (s.entry_price and s.stop_loss):
        return False
    dist = abs(s.stop_loss - s.entry_price) / s.entry_price
    return abs(dist - SYNTHETIC_SL_PCT) < SYNTHETIC_TOL


async def main():
    apply = "--apply" in sys.argv
    async with async_session() as db:
        rows = (await db.execute(select(Signal).where(Signal.status.in_(CLOSED)))).scalars().all()
        real = [s for s in rows if not is_seed_signal(s)]
        print(f"Закрытых реальных сделок: {len(real)}\n")

        # 1. Fabricated stops
        synth = [s for s in real if synthetic_stop(s)]

        # 2. Exact duplicates: same ticker+entry+tp, keep the earliest
        seen, dups = {}, []
        for s in sorted(real, key=lambda x: x.created_at):
            key = (s.ticker, round(s.entry_price or 0, 6), round(s.take_profit or 0, 6))
            if key in seen:
                dups.append(s)
            else:
                seen[key] = s

        # 3. Stale entries: the "win" that came from old channel history
        from app.services.live_price import get_live_price
        stale = []
        for s in real:
            if s.status != SignalStatus.CLOSED_TP:
                continue
            live = (await get_live_price(s.ticker) or {}).get("price") or 0
            if live > 0 and s.entry_price:
                dev = abs(s.entry_price - live) / live
                if dev > stale_tolerance(s.ticker):
                    stale.append((s, live, dev))

        to_expire = {}
        for s in synth:
            to_expire[s.id] = (s, "фиктивный стоп -10% (не публиковался источником)")
        for s in dups:
            to_expire[s.id] = (s, "точный дубликат более раннего сигнала")
        for s, live, dev in stale:
            to_expire[s.id] = (s, f"устаревший вход {s.entry_price:g} vs рынок {live:g} ({dev:.0%})")

        for s, why in to_expire.values():
            print(f"  {s.ticker:<10} {s.status.value:<10} -> expired : {why}")
            if apply:
                s.status = SignalStatus.EXPIRED

        if apply:
            await db.commit()

        left = [s for s in real if s.id not in to_expire]
        wins = sum(1 for s in left if s.status == SignalStatus.CLOSED_TP)
        print(f"\nИсключено: {len(to_expire)}  ({len(synth)} фиктивный стоп · "
              f"{len(dups)} дубликаты · {len(stale)} устаревшие)")
        print(f"Остаётся измеренных сделок: {len(left)} (из них в плюс: {wins})")
        if left:
            print("\nЧто осталось:")
            for s in sorted(left, key=lambda x: x.created_at):
                pct = ((s.take_profit if s.status == SignalStatus.CLOSED_TP else s.stop_loss)
                       - s.entry_price) / s.entry_price * 100
                if s.action.value == "sell":
                    pct = -pct
                print(f"  {s.ticker:<10} {s.status.value:<10} {pct:+6.1f}%  "
                      f"{s.created_at:%Y-%m-%d}")
        print(f"\n{'ПРИМЕНЕНО' if apply else 'ПРЕДПРОСМОТР — запустите с --apply'}")


asyncio.run(main())
