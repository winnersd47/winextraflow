"""Does the WEF Score actually predict outcomes?

The score is presented to users as a 9-factor quality rating, but nothing has ever
checked whether a 68 wins more often than a 58. This groups closed real trades by
WEF band and reports the realized outcome per band, with a Wilson interval so the
sample size is visible instead of implied.

It deliberately refuses to declare the score validated on a handful of trades: the
output says "недостаточно данных" until each band has MIN_PER_BUCKET closes.

It also prints the WEF distribution and percentile cut-offs, which is what the
free/VIP teaser threshold should be derived from — the current fixed 70 sends a
teaser for ~94% of signals, so "the strongest signals are VIP-only" rests on a
handful of them.

Usage:
  python scripts/wef_validation.py
  python scripts/wef_validation.py --json      # machine-readable
"""
import asyncio, json, math, os, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.config import settings
from app.database import async_session
from app.models.signal import Signal, SignalAction, SignalStatus
from app.services.signal_quality import is_seed_signal

# Bands are 5 points wide because that is the resolution the score actually has:
# real signals span roughly 43-71, so wider bands would collapse to two groups.
BANDS = [(0, 55), (55, 60), (60, 65), (65, 70), (70, 101)]
MIN_PER_BUCKET = 20        # below this a band's win rate is noise
MIN_TOTAL = 100            # below this the whole comparison is indicative only
CLOSED = (SignalStatus.CLOSED_TP, SignalStatus.CLOSED_SL)


def wilson(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% CI for a win rate. Narrow interval = the number means something."""
    if n == 0:
        return (0.0, 1.0)
    p = wins / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def realized_pct(s: Signal) -> float | None:
    """P&L at the level that closed the trade — never the live price."""
    if not s.entry_price:
        return None
    if s.status == SignalStatus.CLOSED_TP and s.take_profit:
        raw = (s.take_profit - s.entry_price) / s.entry_price * 100
    elif s.status == SignalStatus.CLOSED_SL and s.stop_loss:
        raw = (s.stop_loss - s.entry_price) / s.entry_price * 100
    else:
        return None
    return -raw if s.action == SignalAction.SELL else raw


async def collect() -> tuple[list[Signal], list[Signal]]:
    async with async_session() as db:
        rows = (await db.execute(select(Signal))).scalars().all()
    real = [s for s in rows if not is_seed_signal(s)]
    closed = [s for s in real if s.status in CLOSED and s.ai_confidence and realized_pct(s) is not None]
    scored = [s for s in real if s.ai_confidence]
    return scored, closed


def band_of(wef: int) -> tuple[int, int]:
    for lo, hi in BANDS:
        if lo <= wef < hi:
            return (lo, hi)
    return BANDS[-1]


def analyse(closed: list[Signal], score=lambda s: s.ai_confidence) -> list[dict]:
    """Win rate per score band, with a Wilson interval.

    `score` selects which number is being validated. Passing
    `lambda s: s.source_confidence` validates the MT5 model's self-assessment
    instead of our WEF Score — the two are separate on purpose, so that a number
    only enters the scoring formula after it has been shown to predict something.
    """
    out = []
    closed = [s for s in closed if score(s) is not None]
    for lo, hi in BANDS:
        grp = [s for s in closed if lo <= round(score(s) * 100) < hi]
        wins = sum(1 for s in grp if s.status == SignalStatus.CLOSED_TP)
        pnls = [realized_pct(s) for s in grp]
        ci = wilson(wins, len(grp))
        out.append({
            "band": f"{lo}-{hi - 1}" if hi <= 100 else f"{lo}+",
            "n": len(grp),
            "wins": wins,
            "win_rate": wins / len(grp) if grp else None,
            "ci_low": ci[0], "ci_high": ci[1],
            "avg_pnl": sum(pnls) / len(pnls) if pnls else None,
            "enough": len(grp) >= MIN_PER_BUCKET,
        })
    return out


def percentiles(scored: list[Signal]) -> dict:
    wefs = sorted(round(s.ai_confidence * 100) for s in scored)
    if not wefs:
        return {}
    def p(q):
        return wefs[min(len(wefs) - 1, int(len(wefs) * q))]
    return {"n": len(wefs), "min": wefs[0], "max": wefs[-1],
            "p50": p(0.50), "p75": p(0.75), "p90": p(0.90)}


def main_report(scored, closed, as_json: bool):
    bands = analyse(closed)
    pct = percentiles(scored)
    thr = settings.free_teaser_max_wef
    teased = sum(1 for s in scored if round(s.ai_confidence * 100) < thr)

    if as_json:
        print(json.dumps({"bands": bands, "distribution": pct,
                          "teaser_threshold": thr, "teased_share": teased / max(len(scored), 1)},
                         ensure_ascii=False, indent=2))
        return

    print("=" * 68)
    print("ВАЛИДАЦИЯ WEF SCORE — предсказывает ли балл результат сделки")
    print("=" * 68)
    print(f"\nЗакрытых реальных сделок с баллом: {len(closed)}")
    print(f"Сигналов с баллом всего:          {len(scored)}\n")

    print(f"{'WEF':>8} {'N':>5} {'Win rate':>10} {'95% ДИ':>16} {'Ср. P&L':>9}")
    print("-" * 55)
    for b in bands:
        if not b["n"]:
            print(f"{b['band']:>8} {0:>5} {'—':>10} {'—':>16} {'—':>9}")
            continue
        ci = f"{b['ci_low']:.0%}–{b['ci_high']:.0%}"
        mark = "" if b["enough"] else "  ⚠ мало"
        print(f"{b['band']:>8} {b['n']:>5} {b['win_rate']:>9.0%} {ci:>16} "
              f"{b['avg_pnl']:>8.1f}%{mark}")

    filled = [b for b in bands if b["enough"]]
    print()
    if len(closed) < MIN_TOTAL or len(filled) < 3:
        print(f"ВЫВОД: недостаточно данных. Нужно ≥{MIN_TOTAL} закрытых сделок "
              f"и ≥{MIN_PER_BUCKET} в каждой полосе (сейчас полос с достаточной "
              f"выборкой: {len(filled)}).")
        print("До этого момента WEF Score — это оценка качества входных данных,")
        print("а не проверенный предиктор. Так его и надо описывать пользователю.")
    else:
        rates = [b["win_rate"] for b in filled]
        mono = all(rates[i] <= rates[i + 1] for i in range(len(rates) - 1))
        spread = max(rates) - min(rates)
        print(f"ВЫВОД: монотонность {'подтверждена' if mono else 'НЕ подтверждена'}, "
              f"разброс win rate между полосами {spread:.0%}.")
        if not mono or spread < 0.10:
            print("Балл не разделяет сделки по результату — веса надо перекалибровать.")

    if pct:
        print(f"\nРаспределение балла: min {pct['min']} · медиана {pct['p50']} · "
              f"p75 {pct['p75']} · p90 {pct['p90']} · max {pct['max']}  (n={pct['n']})")
        print(f"Порог тизера сейчас {thr}: тизер уходит в общий канал "
              f"для {teased}/{len(scored)} ({teased / max(len(scored), 1):.0%}) сигналов, "
              f"эксклюзивно в VIP — {len(scored) - teased}.")
        print(f"Чтобы VIP-эксклюзивом была верхняя четверть, порог = {pct['p75']}; "
              f"верхняя десятая — {pct['p90']}.")
        print("Диапазон балла узкий (почти все сигналы в 55–70), поэтому порог")
        print("осмысленно задавать процентилем, а не фиксированным числом.")

    _source_confidence_report(closed)


def _source_confidence_report(closed: list[Signal]) -> None:
    """Same validation for the source's own confidence (MT5 model self-assessment).

    Kept separate from the WEF report because it answers a different question: does
    the model's own 0..1 number predict anything? Until it does, it stays out of the
    scoring formula — the EA also must not use it as a trade trigger.
    """
    have = [s for s in closed if s.source_confidence is not None]
    print("\n" + "=" * 68)
    print("САМООЦЕНКА МОДЕЛИ (source_confidence) — предсказывает ли она результат")
    print("=" * 68)
    if not have:
        print("\nЗакрытых сделок с самооценкой модели: 0.")
        print("Появятся после того, как мост MT5 начнёт отдавать сигналы (cmd=signal)")
        print("и они закроются. До тех пор это число нельзя ни использовать, ни")
        print("показывать как вероятность.")
        return

    bands = analyse(have, score=lambda s: s.source_confidence)
    print(f"\nЗакрытых сделок с самооценкой: {len(have)}\n")
    print(f"{'Увер.':>8} {'N':>5} {'Win rate':>10} {'95% ДИ':>16} {'Ср. P&L':>9}")
    print("-" * 55)
    for b in bands:
        if not b["n"]:
            print(f"{b['band']:>8} {0:>5} {'—':>10} {'—':>16} {'—':>9}")
            continue
        ci = f"{b['ci_low']:.0%}–{b['ci_high']:.0%}"
        mark = "" if b["enough"] else "  ⚠ мало"
        print(f"{b['band']:>8} {b['n']:>5} {b['win_rate']:>9.0%} {ci:>16} "
              f"{b['avg_pnl']:>8.1f}%{mark}")

    filled = [b for b in bands if b["enough"]]
    print()
    if len(filled) < 3:
        print(f"ВЫВОД: недостаточно данных (полос с ≥{MIN_PER_BUCKET} сделок: "
              f"{len(filled)}). Самооценка модели остаётся справочной: в WEF Score "
              f"она не входит и триггером сделки быть не должна.")
        return

    # Calibration: a confidence of 0.7 should win about 70% of the time.
    worst = max(abs(b["win_rate"] - (int(b["band"].split("-")[0]) + 5) / 100)
                for b in filled)
    rates = [b["win_rate"] for b in filled]
    mono = all(rates[i] <= rates[i + 1] for i in range(len(rates) - 1))
    print(f"ВЫВОД: монотонность {'подтверждена' if mono else 'НЕ подтверждена'}, "
          f"максимальное отклонение от калибровки {worst:.0%}.")
    if mono and worst <= 0.15:
        print("Самооценка калибрована — её можно вводить в WEF Score как фактор.")
    else:
        print("Самооценка не калибрована: показывать её как вероятность нельзя.")


async def main():
    scored, closed = await collect()
    main_report(scored, closed, "--json" in sys.argv)


asyncio.run(main())
