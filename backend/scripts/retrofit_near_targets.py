"""Give already-stored ACTIVE signals a tradable first target.

The 83 open signals were ingested before signal_levels grew a near target, so they
still carry the analyst's annual forecast: NTRA +21%, BANE +25%, ONTO +49%. Against
a ~5% volatility stop such a signal can realistically only resolve at the stop, and
until then it resolves at nothing — which is why the channel showed no results at
all.

This recomputes take_profit at TP_ATR_MULT x ATR and moves the analyst number to
long_target. Only ever moves the target closer; a signal whose target is already
within reach is left alone. Entry and stop are untouched — moving those on a signal
that was already published would rewrite history.

Usage: python scripts/retrofit_near_targets.py [--apply]
"""
import asyncio, os, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import async_session
from app.models.signal import Signal, SignalAction, SignalStatus
from app.services.signal_levels import atr_pct, TP_ATR_MULT
from app.services.signal_quality import MIN_RR_RATIO, is_seed_signal


async def main():
    apply = "--apply" in sys.argv
    async with async_session() as db:
        rows = (await db.execute(
            select(Signal).where(
                Signal.status == SignalStatus.ACTIVE,
                Signal.take_profit.isnot(None),
                Signal.stop_loss.isnot(None),
            )
        )).scalars().all()
        rows = [s for s in rows if not is_seed_signal(s)]
        print(f"Активных реальных сигналов: {len(rows)}\n")

        atr_cache: dict[str, float | None] = {}
        moved = skipped = no_atr = too_tight = 0

        for s in sorted(rows, key=lambda x: x.ticker):
            if s.ticker not in atr_cache:
                atr_cache[s.ticker] = await atr_pct(s.ticker)
            atr = atr_cache[s.ticker]
            if not atr:
                no_atr += 1
                continue

            is_buy = s.action == SignalAction.BUY
            entry, far = s.entry_price, s.take_profit
            near = entry * (1 + atr * TP_ATR_MULT) if is_buy else entry * (1 - atr * TP_ATR_MULT)
            if not ((is_buy and near < far) or (not is_buy and near > far)):
                skipped += 1
                continue

            # The near target must still clear the R:R gate, or we would be
            # publishing a setup the pipeline itself would have rejected.
            risk = abs(entry - s.stop_loss)
            rr = abs(near - entry) / risk if risk else 0
            if rr < MIN_RR_RATIO:
                too_tight += 1
                print(f"  {s.ticker:<10} пропуск: ближняя цель даёт R:R {rr:.2f} "
                      f"< {MIN_RR_RATIO} (стоп {abs(entry - s.stop_loss) / entry:.1%})")
                continue

            far_pct = abs(far - entry) / entry * 100
            near_pct = abs(near - entry) / entry * 100
            print(f"  {s.ticker:<10} цель {far:>9.4g} ({far_pct:+5.1f}%) -> "
                  f"{near:>9.4g} ({near_pct:+5.1f}%)  R:R 1:{rr:.1f}  ATR {atr:.1%}")
            if apply:
                if s.long_target is None:
                    s.long_target = far
                s.take_profit = round(near, 6)
            moved += 1

        if apply:
            await db.commit()

        print(f"\nПеренесено на ближнюю цель: {moved}")
        print(f"Цель уже достижима — не менялась: {skipped}")
        print(f"Ближняя цель не проходит R:R: {too_tight}")
        print(f"Нет данных ATR: {no_atr}")
        print(f"\n{'ПРИМЕНЕНО' if apply else 'ПРЕДПРОСМОТР — запустите с --apply'}")


asyncio.run(main())
