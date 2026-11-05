"""Does any advisor hold up across periods, or did one period flatter it?

Two single runs disagreed completely. On a year of daily BTC/ETH/SOL the best
was S5 at +2.79% a trade; on 120 days of 4h bars the same advisor lost 0.29%
and S3 led instead. A ranking that reverses when the window moves is not a
ranking, and acting on either run would have been acting on noise.

So this splits the history into non-overlapping windows and asks a different
question: not "which advisor won" but "which one wins in most windows, and is
that distinguishable from luck".

Three things it does that a single backtest cannot:

  * **Per-window results, printed.** An advisor that is +3% in one window and
    -2% in four is visibly not an edge, however good the pooled average looks.
  * **A bootstrap, not a t-test.** Trade returns are skewed — a 4 ATR target
    against a 2 ATR stop guarantees it — and a t-test assumes they are not.
    Resampling the trades makes no such assumption.
  * **The multiple-comparison correction.** Six advisors are tested, so the
    chance that at least one clears p < 0.05 by luck alone is about 26%, not
    5%. The threshold printed is Bonferroni's, and the uncorrected p is shown
    beside it so the difference is visible rather than taken on trust.

Warm-up comes from bars BEFORE each window, so a window is not charged 60 bars
of history, and no decision ever sees a bar after itself.

Usage:
  py -3.13 scripts/advisor_robustness.py
  py -3.13 scripts/advisor_robustness.py --windows 8 --days 1100
  py -3.13 scripts/advisor_robustness.py --interval 4h --days 400 --windows 4
"""
import argparse
import asyncio
import os
import random
import statistics
import sys
from datetime import datetime, timedelta, timezone

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.advisors import ADVISORS, MIN_CANDLES, atr, levels
from app.services.backtesting_real import fetch_mexc_candles

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
           "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT", "DOTUSDT", "TRXUSDT"]
MAX_BARS_OPEN = 15
BOOTSTRAP = 5000
ALPHA = 0.05
# A bootstrap cannot protect against a tiny sample on its own: if every observed
# trade won, every resample of them wins too, so three lucky trades return
# p = 0.000 exactly. The guard has to be a floor on the count, and it is the
# same floor the rest of the project uses before publishing any rate.
MIN_TRADES = 30


def _walk_forward(candles, i, action, entry, tp, sl):
    """Stop wins a bar that covers both levels — see scripts/paper_advisors.py."""
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


def _pct(action, entry, exit_price):
    raw = (exit_price - entry) / entry * 100
    return raw if action == "buy" else -raw


def _bootstrap_p(returns: list[float], draws: int = BOOTSTRAP) -> float:
    """One-sided: how often a resample of these trades fails to make money.

    The null is "this advisor's mean return is zero". Resampling the observed
    trades with replacement asks how fragile the measured mean is to which
    trades happened to occur, without assuming the returns are normal.
    """
    if len(returns) < 2:
        return 1.0
    rng = random.Random(20261104)      # fixed, so a rerun gives the same answer
    n = len(returns)
    worse = sum(1 for _ in range(draws)
                if statistics.fmean(rng.choices(returns, k=n)) <= 0)
    return worse / draws


async def _measure(symbols, interval, days, windows, end):
    """Replay every advisor over `windows` non-overlapping slices of a period.

    Returns (series_count, bars, size, trades) where trades[advisor][window] is
    the list of realised percentages. Warm-up always comes from bars BEFORE a
    window, so a window is not charged MIN_CANDLES of its own history.
    """
    to = (datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
          if end else datetime.now(timezone.utc))
    frm = to - timedelta(days=days)
    series = {}
    for sym in symbols:
        c = await fetch_mexc_candles(sym, frm.strftime("%Y-%m-%d"),
                                     to.strftime("%Y-%m-%d"), interval)
        if len(c) >= MIN_CANDLES + MAX_BARS_OPEN + windows * 20:
            series[sym] = c
    if not series:
        return 0, 0, 0, {}

    length = min(len(c) for c in series.values())
    size = (length - MIN_CANDLES - MAX_BARS_OPEN) // windows
    if size < 20:
        return len(series), length, size, {}

    trades = {a.id: {w: [] for w in range(windows)}
              for a in ADVISORS if a.replayable}

    for candles in series.values():
        busy_until = {}
        for w in range(windows):
            lo = MIN_CANDLES + w * size
            for i in range(lo, min(lo + size, len(candles) - 1)):
                window = candles[:i + 1]
                a = atr(window)
                if a <= 0:
                    continue
                entry = float(candles[i]["close"])
                for adv in ADVISORS:
                    if not adv.replayable or i <= busy_until.get(adv.id, -1):
                        continue
                    action = adv.signal(window)
                    if not action:
                        continue
                    tp, sl = levels(action, entry, a)
                    reason, exit_price, bars = _walk_forward(candles, i, action,
                                                             entry, tp, sl)
                    if reason == "open":
                        continue
                    busy_until[adv.id] = i + bars
                    trades[adv.id][w].append(_pct(action, entry, exit_price))

    return len(series), length, size, trades


def _report(trades, windows, *, quiet=False):
    """Print the tables and return the advisors that passed every test."""
    tested = sum(1 for a in ADVISORS if a.replayable)
    bonf = ALPHA / tested

    if not quiet:
        head = f"{'':4}{'советник':20}" + "".join(
            f"{'окно ' + str(w + 1):>12}" for w in range(windows))
        print(head)
        print("-" * len(head))
        for adv in ADVISORS:
            if not adv.replayable:
                continue
            cells = ""
            for w in range(windows):
                rows = trades[adv.id][w]
                cells += (f"{statistics.fmean(rows):>+9.2f}% " if len(rows) >= 5
                          else f"{'n=' + str(len(rows)):>11} ")
            print(f"{adv.id:4}{adv.name:20}{cells}")
        print("\n(окно показано только при 5+ сделках; иначе напечатано их число)")

        print(f"\n{'':4}{'советник':20}{'сделок':>8}{'ожидание':>11}{'окон +':>9}"
              f"{'p':>8}{'значимо':>20}")
        print("-" * 80)

    survivors = []
    for adv in ADVISORS:
        if not adv.replayable:
            if not quiet:
                print(f"{adv.id:4}{adv.name:20}{'— не замерялся':>30}")
            continue
        pooled = [r for w in trades[adv.id].values() for r in w]
        if len(pooled) < 10:
            if not quiet:
                print(f"{adv.id:4}{adv.name:20}{len(pooled):>8}{'мало данных':>38}")
            continue
        per_window = [statistics.fmean(trades[adv.id][w])
                      for w in range(windows) if trades[adv.id][w]]
        positive = sum(1 for m in per_window if m > 0)
        exp = statistics.fmean(pooled)
        p = _bootstrap_p(pooled)
        if len(pooled) < MIN_TRADES:
            mark = f"мало сделок (<{MIN_TRADES})"
        elif p < bonf:
            mark = "ДА"
        elif p < ALPHA:
            mark = "только без поправки"
        else:
            mark = "нет"
        if not quiet:
            share = f"{positive}/{len(per_window)}"
            print(f"{adv.id:4}{adv.name:20}{len(pooled):>8}{exp:>+10.2f}%"
                  f"{share:>9}{p:>8.3f}{mark:>20}")
        if (p < bonf and len(pooled) >= MIN_TRADES
                and positive > len(per_window) / 2):
            survivors.append((adv, len(pooled), exp, positive, len(per_window), p))

    if not quiet:
        print(f"\nПорог значимости с поправкой Бонферрони: p < {bonf:.4f} "
              f"(проверяем {tested} советников, поэтому не {ALPHA}).")
    return survivors


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=SYMBOLS)
    ap.add_argument("--interval", default="1d")
    ap.add_argument("--days", type=int, default=1100)
    ap.add_argument("--windows", type=int, default=6)
    # Needed for a genuine out-of-sample check: an advisor that looked good on
    # the period it was picked from has to be re-tested on a period it was not.
    ap.add_argument("--end", default=None, help="YYYY-MM-DD, по умолчанию сегодня")
    ap.add_argument("--oos", action="store_true",
                    help="два смежных периода: отбор на свежем, проверка на предыдущем")
    args = ap.parse_args()

    if not args.oos:
        n, bars, size, trades = await _measure(args.symbols, args.interval,
                                               args.days, args.windows, args.end)
        if not trades:
            print("Недостаточно данных." if not n else
                  f"Окна по {size} баров — слишком мелко. Уменьшите --windows.")
            return 1
        print(f"{n} инструментов, {args.interval}, {bars} баров, "
              f"{args.windows} непересекающихся окон по {size}")
        print("Прогрев берётся ДО окна, решения — только внутри него.\n")
        survivors = _report(trades, args.windows)
        print()
        if survivors:
            for adv, cnt, exp, pos, tot, p in survivors:
                print(f"Выдержал проверку: {adv.id} {adv.name} — {exp:+.2f}% "
                      f"на сделку, плюс в {pos} окнах из {tot}, p={p:.3f} "
                      f"({cnt} сделок)")
            print("\nЭто один период. Повторите с --oos: советник, прошедший "
                  "здесь,\nобязан пройти и на данных, по которым он не отбирался.")
        else:
            print("Ни один советник не прошёл: либо знак пляшет между окнами, "
                  "либо\nрезультат неотличим от случайного на этой выборке. Это "
                  "тоже\nответ — он означает «не торговать», а не «взять лучшего "
                  "из шести».")
        return 0

    # ── out of sample ──────────────────────────────────────────────────────
    #
    # The reason this mode exists. Three single runs produced three different
    # "winners": nobody on 3 years of daily, S2 on the recent 400 days of 4h,
    # S4 — the worst of that same run — on the 400 days before it. Testing six
    # advisors against enough periods will always surface one that clears any
    # threshold; only repetition on data it was not chosen from means anything.
    recent_end = args.end
    older_end = ((datetime.strptime(args.end, "%Y-%m-%d") if args.end
                  else datetime.now(timezone.utc).replace(tzinfo=None))
                 - timedelta(days=args.days)).strftime("%Y-%m-%d")

    print(f"=== ОТБОР: {args.days} дн. до {recent_end or 'сегодня'} ===")
    n1, b1, s1, t1 = await _measure(args.symbols, args.interval, args.days,
                                    args.windows, recent_end)
    if not t1:
        print("Недостаточно данных для периода отбора.")
        return 1
    print(f"{n1} инструментов, {args.interval}, {b1} баров, окна по {s1}\n")
    picked = _report(t1, args.windows)

    print(f"\n\n=== ПРОВЕРКА ВНЕ ВЫБОРКИ: {args.days} дн. до {older_end} ===")
    n2, b2, s2, t2 = await _measure(args.symbols, args.interval, args.days,
                                    args.windows, older_end)
    if not t2:
        print("Недостаточно данных для проверочного периода.")
        return 1
    print(f"{n2} инструментов, {args.interval}, {b2} баров, окна по {s2}\n")
    confirmed = _report(t2, args.windows)

    picked_ids = {a.id for a, *_ in picked}
    confirmed_ids = {a.id for a, *_ in confirmed}
    both = picked_ids & confirmed_ids

    print("\n\n=== ИТОГ ===")
    print(f"Прошли на периоде отбора:   {', '.join(sorted(picked_ids)) or '—'}")
    print(f"Прошли на проверочном:      {', '.join(sorted(confirmed_ids)) or '—'}")
    print()
    if both:
        print(f"Повторились на обоих: {', '.join(sorted(both))}. "
              f"Это единственный результат,\nкоторый стоит рассматривать — и его "
              f"всё равно надо подтвердить на реальном\nбумажном треке, прежде "
              f"чем публиковать сигналы.")
    else:
        print("Ни один советник не прошёл оба периода.\n")
        if picked_ids or confirmed_ids:
            print("Прошедшие в одном периоде и провалившиеся в другом — это не\n"
                  "преимущество, а подгонка: при шести советниках и достаточном\n"
                  "числе периодов кто-нибудь всегда перейдёт любой порог.")
        print("\nВывод: торговать по этим правилам оснований нет.")
    return 0

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
