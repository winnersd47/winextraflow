"""Which sources are worth relaying — measured against random entry, not zero.

The platform relays other people's signals. If it has an edge at all, the most
likely place for it is here: picking the channels that are right more often than
chance, and dropping the rest. That is measurable today, on the signals already
stored, without waiting for the forward record to reach any threshold.

Two things make the number mean something:

**The baseline.** "54% of trades won" is not a result until you know what a coin
flip pays at the same geometry. A 4 ATR target against a 2 ATR stop is hit by
chance roughly a third of the time, so a 33% win rate is nothing and a 55% one
is a lot. services/signal_geometry.py walks real candles from random entries to
get that number per instrument, and every row here is reported against it.

**A floor on the count.** MIN_SAMPLE closed trades before any rate is shown, the
same floor the public record uses — a source with four trades has no win rate,
it has four trades.

Replayed uniformly rather than read from stored outcomes, so an ACTIVE signal
whose levels were already resolved counts too, and so every source is scored the
same way.

Usage:
  py -3.13 scripts/source_quality.py
  py -3.13 scripts/source_quality.py --hold 15 --min-trades 10
"""
import argparse
import asyncio
import os
import statistics
import sys
from collections import defaultdict
from datetime import timedelta

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.database import async_session
from app.models.provider import Provider
from app.models.signal import Signal, SignalAction
from app.services.backtesting_real import fetch_candles
from app.services.measured_stats import MIN_SAMPLE
from app.services.signal_geometry import (MAX_BARS_TO_RESOLVE as BASELINE_BARS,
                                          geometry_hit_rate_cached)
from app.services.signal_quality import is_seed_signal


def _outcome(candles, entry, tp, sl, action, hold):
    """(reason, pct) walking forward. A bar covering both levels is a STOP."""
    buy = action == "buy"
    for bar in candles[:hold]:
        hi, lo = float(bar["high"]), float(bar["low"])
        if buy:
            if lo <= sl:
                return "sl", (sl - entry) / entry * 100
            if hi >= tp:
                return "tp", (tp - entry) / entry * 100
        else:
            if hi >= sl:
                return "sl", (entry - sl) / entry * 100
            if lo <= tp:
                return "tp", (entry - tp) / entry * 100
    if not candles[:hold]:
        return "open", 0.0
    last = float(candles[:hold][-1]["close"])
    return "expired", ((last - entry) if buy else (entry - last)) / entry * 100


async def main() -> int:
    ap = argparse.ArgumentParser()
    # Matches signal_geometry.MAX_BARS_TO_RESOLVE. The baseline gives a random
    # entry that many bars to reach its target; giving the source fewer and
    # then comparing the two rates charges it for trades the baseline never
    # had to resolve. The first run of this script did exactly that — 15 bars
    # against the baseline's 30 — and reported both sources as far worse than
    # chance.
    ap.add_argument("--hold", type=int, default=BASELINE_BARS,
                    help="баров удержания (по умолчанию как у базовой линии)")
    ap.add_argument("--min-trades", type=int, default=MIN_SAMPLE)
    args = ap.parse_args()

    async with async_session() as db:
        provs = {str(p.id): p.name
                 for p in (await db.execute(select(Provider))).scalars().all()}
        rows = [s for s in (await db.execute(select(Signal))).scalars().all()
                if not is_seed_signal(s) and s.excluded_reason is None
                and s.entry_price and s.take_profit and s.stop_loss]

    print(f"Сигналов с полной геометрией: {len(rows)}. Удержание {args.hold} баров.")
    print("Касание цели и стопа в одном баре считается стопом.\n")

    by_provider = defaultdict(list)
    skipped = 0
    for s in rows:
        if not s.created_at:
            continue
        frm = s.created_at.strftime("%Y-%m-%d")
        to = (s.created_at + timedelta(days=args.hold * 3 + 10)).strftime("%Y-%m-%d")
        try:
            candles = await fetch_candles(s.ticker, frm, to)
        except Exception:
            candles = []
        if len(candles) < 2:
            skipped += 1
            continue
        action = "buy" if s.action == SignalAction.BUY else "sell"
        reason, pct = _outcome(candles[1:], s.entry_price, s.take_profit,
                               s.stop_loss, action, args.hold)
        if reason == "open":
            skipped += 1
            continue
        by_provider[str(s.provider_id)].append((reason, pct, s, action))

    if skipped:
        print(f"({skipped} сигналов без свечей для переигровки — пропущены)\n")

    header = (f"{'источник':34}{'разреш.':>8}{'win%':>7}{'случайно':>10}"
              f"{'разница':>9}{'ожидание':>10}")
    print(header)
    print("-" * len(header))

    summary = []
    for pid, items in sorted(by_provider.items(), key=lambda kv: -len(kv[1])):
        name = provs.get(pid, "?")[:32]
        n = len(items)
        # Win rate over RESOLVED trades only — tp + sl — because that is the
        # baseline's denominator (signal_geometry drops its undecided cases).
        # Dividing by every outcome instead counts an expiry as a loss on our
        # side and as nothing on the baseline's.
        tp = sum(1 for r, *_ in items if r == "tp")
        sl = sum(1 for r, *_ in items if r == "sl")
        resolved = tp + sl
        wr = (tp / resolved * 100) if resolved else None
        exp = statistics.fmean(p for _, p, _, _ in items)

        # Baseline for the same instruments and the same geometry.
        bases = []
        for _, _, s, action in items:
            risk = abs(s.entry_price - s.stop_loss)
            reward = abs(s.take_profit - s.entry_price)
            if risk <= 0:
                continue
            ratio = reward / risk
            try:
                g = await geometry_hit_rate_cached(
                    s.ticker, action, tp_mult=round(2.0 * ratio, 2), sl_mult=2.0)
            except Exception:
                continue
            if g and g.get("hit_rate_pct") is not None:
                bases.append(float(g["hit_rate_pct"]))
        base = statistics.fmean(bases) if bases else None

        if resolved < args.min_trades:
            print(f"{name:34}{n:>8}{('разрешилось ' + str(resolved)):>36}")
            continue
        b = f"{base:>9.1f}%" if base is not None else f"{'—':>10}"
        d = f"{wr - base:>+8.1f}" if base is not None else f"{'—':>9}"
        print(f"{name:34}{resolved:>8}{wr:>6.1f}%{b}{d}{exp:>+9.2f}%")
        summary.append((name, resolved, wr, base, exp))

    print(f"\nПорог достоверности: {args.min_trades} сделок "
          f"(меньше — это не win rate, а несколько сделок).")
    print("«случайно» — доля срабатываний при случайном входе с той же "
          "геометрией\nпо реальным свечам того же инструмента.")

    beat = [s for s in summary if s[3] is not None and s[2] > s[3]]
    print()
    if beat:
        for name, n, wr, base, exp in sorted(beat, key=lambda x: -(x[2] - x[3])):
            print(f"Обгоняет случайный вход: {name} — {wr:.1f}% против "
                  f"{base:.1f}% ({n} сделок, {exp:+.2f}% на сделку)")
        print("\nЭто одна выборка и один период. Прежде чем на этом что-то "
              "строить,\nпроверьте на данных, по которым источник не отбирался.")
    elif summary:
        print("Ни один источник не обгоняет случайный вход на своей геометрии.")
    else:
        print(f"Ни у одного источника нет {args.min_trades} сделок — "
              f"измерять пока нечего.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
