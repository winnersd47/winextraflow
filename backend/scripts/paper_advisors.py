"""Replay the seven advisors over real candles. No terminal, no money.

What this measures: how the rules in mt5/WEF_S1…S7 would have fared on actual
MEXC candles, bar by bar, with the EAs' own 4 ATR target and 2 ATR stop.

What it does NOT do, deliberately:

  * it does not touch the published track record. That counts only signals
    actually sent to a channel (signal_quality.was_published), and these were
    never sent to anyone. Advisor trades are evidence about the strategies, not
    about the platform's record, and mixing the two is the failure the record
    was just cleaned of;
  * it does not place an order anywhere, with or without keys;
  * it does not look at the next bar when deciding. The decision uses candles up
    to and including bar i; the outcome walks i+1 onward. A replay that peeks
    measures nothing but its own cheating.

S7 is reported as "not measured": it asks a model per bar, and substituting a
rule would publish a number under the name of a strategy that never produced it.

Usage:
  py -3.13 scripts/paper_advisors.py                       # BTC/ETH/SOL, 1d, 1 year
  py -3.13 scripts/paper_advisors.py --symbols BTCUSDT ETHUSDT
  py -3.13 scripts/paper_advisors.py --interval 4h --days 120
"""
import argparse
import asyncio
import os
import statistics
import sys
from datetime import datetime, timedelta, timezone

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.advisors import (ADVISORS, MIN_CANDLES, STOP_ATR_MULT,
                                   TARGET_ATR_MULT, atr, levels)
from app.services.backtesting_real import fetch_mexc_candles

DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
# How many bars a trade may stay open before it is written off unresolved. The
# platform holds a signal 15 trading days; the same shape in bars.
MAX_BARS_OPEN = 15


def _walk_forward(candles: list[dict], i: int, action: str,
                  entry: float, tp: float, sl: float) -> tuple[str, float, int]:
    """Outcome of a trade opened at bar i. Returns (reason, exit_price, bars).

    When a single bar's range covers both levels, the STOP is taken. Daily bars
    do not say which came first, and assuming the target is how a replay prints
    a win rate the market never paid.
    """
    for n, bar in enumerate(candles[i + 1:i + 1 + MAX_BARS_OPEN], start=1):
        hi, lo = float(bar["high"]), float(bar["low"])
        if action == "buy":
            if lo <= sl:
                return "sl", sl, n
            if hi >= tp:
                return "tp", tp, n
        else:
            if hi >= sl:
                return "sl", sl, n
            if lo <= tp:
                return "tp", tp, n
    tail = candles[i + 1:i + 1 + MAX_BARS_OPEN]
    if not tail:
        return "open", entry, 0
    return "expired", float(tail[-1]["close"]), len(tail)


def _pct(action: str, entry: float, exit_price: float) -> float:
    raw = (exit_price - entry) / entry * 100
    return raw if action == "buy" else -raw


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    ap.add_argument("--interval", default="1d")
    ap.add_argument("--days", type=int, default=365)
    args = ap.parse_args()

    to = datetime.now(timezone.utc)
    frm = to - timedelta(days=args.days)
    date_from, date_to = frm.strftime("%Y-%m-%d"), to.strftime("%Y-%m-%d")

    series: dict[str, list[dict]] = {}
    for sym in args.symbols:
        candles = await fetch_mexc_candles(sym, date_from, date_to, args.interval)
        if len(candles) < MIN_CANDLES + MAX_BARS_OPEN:
            print(f"@{sym}: свечей {len(candles)} — мало, пропускаю")
            continue
        series[sym] = candles
        print(f"{sym}: {len(candles)} свечей {args.interval} "
              f"({candles[0]['begin'][:10]} … {candles[-1]['begin'][:10]})")
    if not series:
        print("Нет данных.")
        return 1

    results: dict[str, list[dict]] = {a.id: [] for a in ADVISORS}
    # One open position per advisor per symbol, because that is what the EAs do:
    # every one of them opens with `if(!WefDue() || WefHasPosition(n)) return`.
    #
    # Without this the replay opens a fresh trade on every bar the condition
    # still holds, and a trend-follower holds for weeks — the first run counted
    # 646 trades for S1 where the EA would have taken a few dozen, all of them
    # overlapping slices of the same move. That inflates the sample and
    # correlates the outcomes, which is the pair of things a win rate assumes
    # are not happening.
    busy_until: dict[tuple[str, str], int] = {}

    for sym, candles in series.items():
        for i in range(MIN_CANDLES, len(candles) - 1):
            window = candles[:i + 1]
            a = atr(window)
            if a <= 0:
                continue
            entry = float(candles[i]["close"])
            for adv in ADVISORS:
                if not adv.replayable:
                    continue
                if i <= busy_until.get((adv.id, sym), -1):
                    continue
                action = adv.signal(window)
                if not action:
                    continue
                tp, sl = levels(action, entry, a)
                reason, exit_price, bars = _walk_forward(candles, i, action,
                                                         entry, tp, sl)
                if reason == "open":
                    continue
                busy_until[(adv.id, sym)] = i + bars
                results[adv.id].append({
                    "symbol": sym, "action": action, "reason": reason,
                    "pct": _pct(action, entry, exit_price), "bars": bars,
                    "date": candles[i]["begin"][:10],
                })

    print(f"\nУровни: цель {TARGET_ATR_MULT:g}·ATR, стоп {STOP_ATR_MULT:g}·ATR "
          f"(безубыток 33%). Держим максимум {MAX_BARS_OPEN} баров.")
    print("При касании обоих уровней в одном баре засчитывается СТОП.\n")

    header = (f"{'':4}{'советник':20}{'сделок':>8}{'TP':>5}{'SL':>5}{'ист':>5}"
              f"{'win%':>7}{'ожидание':>10}{'PF':>7}{'баров':>7}")
    print(header)
    print("-" * len(header))

    summary = []
    for adv in ADVISORS:
        if not adv.replayable:
            print(f"{adv.id:4}{adv.name:20}{'— не замерялся (модель на каждый бар)':>42}")
            continue
        rows = results[adv.id]
        if not rows:
            print(f"{adv.id:4}{adv.name:20}{0:>8}{'':>5}{'':>5}{'':>5}"
                  f"{'нет сигналов':>29}")
            continue
        tp = sum(1 for r in rows if r["reason"] == "tp")
        sl = sum(1 for r in rows if r["reason"] == "sl")
        exp = sum(1 for r in rows if r["reason"] == "expired")
        pcts = [r["pct"] for r in rows]
        wins = [p for p in pcts if p > 0]
        losses = [p for p in pcts if p <= 0]
        pf = (sum(wins) / abs(sum(losses))) if wins and losses else float("inf")
        wr = len(wins) / len(pcts) * 100
        bars = statistics.mean(r["bars"] for r in rows)
        print(f"{adv.id:4}{adv.name:20}{len(rows):>8}{tp:>5}{sl:>5}{exp:>5}"
              f"{wr:>6.1f}%{statistics.mean(pcts):>+9.2f}%"
              f"{pf:>7.2f}{bars:>7.1f}")
        summary.append((adv, len(rows), wr, statistics.mean(pcts), pf))

    print()
    if not summary:
        print("Ни один советник не дал сигналов на этих данных.")
        return 0

    best = max(summary, key=lambda s: s[3])
    worst = min(summary, key=lambda s: s[3])
    print(f"Лучшее ожидание: {best[0].id} {best[0].name} — {best[3]:+.2f}% на сделку "
          f"({best[1]} сделок)")
    print(f"Худшее:          {worst[0].id} {worst[0].name} — {worst[3]:+.2f}% "
          f"({worst[1]} сделок)")
    thin = [s for s in summary if s[1] < 30]
    if thin:
        print(f"\nМеньше 30 сделок — выборка ничего не измеряет: "
              f"{', '.join(s[0].id for s in thin)}")
    print("\nЭто замер стратегий, а не трек-рекорд платформы: ни один из этих "
          "сигналов\nникому не публиковался, поэтому в публичную статистику "
          "они не идут и не пойдут.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
