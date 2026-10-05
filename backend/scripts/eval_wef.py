"""Eval set for the WEF Score: replay every stored signal against real candles.

The platform has 11 closed signals and all 11 lost, so the outcome column has no
variation and no correlation with the score can be computed — a point-biserial
correlation needs both classes present. Waiting for the sample to accumulate means
waiting months.

But 150 of the 153 real signals carry entry, target and stop, and 118 of them
expired without ever being resolved. Their outcome is not unknown: it is recorded
in the price history. Replaying each one forward from its publication date and
seeing which level the market reached first turns them into labelled cases today.

The split that decides whether this measures anything
-----------------------------------------------------
The stop level came from the source's own text in only 19 of 153 signals (12%).
The other 88% were derived by this platform's ATR rules. Replaying those measures
`STOP_ATR_MULT`, not the provider's skill or the score's discrimination — and
mixing the two groups would produce a number that looks like score validation but
is mostly a backtest of our own defaults.

So results are reported in three cohorts:

  source   — both levels stated by the source. Small, but it is the only cohort
             that says anything about the signal as published.
  derived  — levels we computed. Measures our level rules.
  mixed    — target from the source, stop from us. The common case.

Method
------
  * forward bars only, from the publication date. Nothing after the resolution.
  * a bar touching both levels counts as the STOP. Intraday order is unknowable
    from daily candles, and assuming the favourable one is how backtests flatter
    themselves.
  * unresolved after MAX_BARS is its own outcome, not a loss and not a win.
  * seed data excluded throughout.

Usage:
    python scripts/eval_wef.py                    # replay + report
    python scripts/eval_wef.py --limit 40
    python scripts/eval_wef.py --json
    python scripts/eval_wef.py --cache eval.json  # reuse a previous replay
"""
import asyncio
import json
import math
import os
import statistics
import sys
from datetime import timedelta

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.database import async_session
from app.models.signal import Signal, SignalAction
from app.services.backtesting_real import fetch_candles
from app.services.signal_quality import is_seed_signal

# A signal that resolves neither way inside this window is treated as unresolved
# rather than stretched until it happens to work out.
MAX_BARS = 30
# Bands for the score-vs-outcome table. Wide, because the score currently takes
# only four distinct values.
BANDS = [(0, 79), (80, 85), (86, 91), (92, 100)]


def _num(x) -> float:
    return float(x)


def level_source(s: Signal) -> str:
    """Whether each level came from the source's text or from our own rules.

    Matching on the digits as they would appear in the message. Crude, but the
    database has no column recording provenance, and the alternative — assuming
    every level is the provider's — is what produced the fabricated track record
    this project already had to unwind once.
    """
    msg = s.raw_message or ""
    def stated(v) -> bool:
        if v is None or not msg:
            return False
        forms = {f"{v:.10f}".rstrip("0").rstrip("."), f"{v:.0f}",
                 f"{v:.1f}", f"{v:.2f}"}
        forms |= {f.replace(".", ",") for f in forms}
        return any(f in msg for f in forms)

    tp, sl = stated(s.take_profit), stated(s.stop_loss)
    if tp and sl:
        return "source"
    if not tp and not sl:
        return "derived"
    return "mixed"


async def replay(s: Signal) -> dict | None:
    """Walk forward from publication and return which level was reached first."""
    if not (s.entry_price and s.take_profit and s.stop_loss and s.created_at):
        return None

    start = s.created_at.date()
    # A window wide enough to contain MAX_BARS trading days plus weekends.
    end = start + timedelta(days=int(MAX_BARS * 1.8) + 10)
    try:
        bars = await fetch_candles(s.ticker, start.isoformat(), end.isoformat())
    except Exception as e:
        return {"outcome": "no_data", "note": f"{type(e).__name__}", "bars": 0}
    if not bars:
        return {"outcome": "no_data", "note": "нет свечей", "bars": 0}

    tp, sl, entry = _num(s.take_profit), _num(s.stop_loss), _num(s.entry_price)
    is_buy = s.action == SignalAction.BUY

    for i, c in enumerate(bars[:MAX_BARS]):
        hi, lo = _num(c.get("high", 0)), _num(c.get("low", 0))
        if not hi or not lo:
            continue
        hit_tp = hi >= tp if is_buy else lo <= tp
        hit_sl = lo <= sl if is_buy else hi >= sl
        if hit_tp and hit_sl:
            # Both inside one bar. Daily candles cannot say which came first, so
            # the stop is assumed — the conservative reading.
            return {"outcome": "loss", "bars": i + 1, "level": sl,
                    "note": "оба уровня в одной свече — считаю стопом"}
        if hit_tp:
            return {"outcome": "win", "bars": i + 1, "level": tp, "note": ""}
        if hit_sl:
            return {"outcome": "loss", "bars": i + 1, "level": sl, "note": ""}

    return {"outcome": "unresolved", "bars": min(len(bars), MAX_BARS),
            "level": None, "note": f"не разрешился за {MAX_BARS} свечей"}


def band_of(score: int) -> str:
    for lo, hi in BANDS:
        if lo <= score <= hi:
            return f"{lo}-{hi}"
    return "?"


def wilson(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p = wins / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - m) / d), min(1.0, (c + m) / d)


def point_biserial(scores: list[float], wins: list[int]) -> float | None:
    """Correlation between the score and a binary win/loss outcome.

    Returns None when either class is empty — which is the state the platform's
    own 11 closed trades are in, and the reason this script exists.
    """
    n = len(scores)
    if n < 3:
        return None
    n1 = sum(wins)
    n0 = n - n1
    if n1 == 0 or n0 == 0:
        return None
    sd = statistics.pstdev(scores)
    if sd == 0:
        return None
    m1 = statistics.fmean([s for s, w in zip(scores, wins) if w])
    m0 = statistics.fmean([s for s, w in zip(scores, wins) if not w])
    return (m1 - m0) / sd * math.sqrt(n1 * n0 / (n * n))


def report(rows: list[dict], as_json: bool) -> None:
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    total = len(rows)
    resolved = [r for r in rows if r["outcome"] in ("win", "loss")]
    print("=" * 70)
    print("EVAL WEF SCORE — исходы восстановлены по реальным свечам")
    print("=" * 70)
    print(f"Сигналов переиграно:  {total}")
    print(f"  разрешились:        {len(resolved)}")
    print(f"  не разрешились:     {sum(1 for r in rows if r['outcome'] == 'unresolved')}")
    print(f"  нет данных:         {sum(1 for r in rows if r['outcome'] == 'no_data')}")

    for cohort, label, meaning in (
        ("source", "УРОВНИ ОТ ИСТОЧНИКА", "говорит о сигнале как он опубликован"),
        ("mixed", "ЦЕЛЬ ОТ ИСТОЧНИКА, СТОП НАШ", "смесь"),
        ("derived", "УРОВНИ ВЫВЕДЕНЫ НАМИ", "говорит о наших ATR-правилах, не о провайдере"),
    ):
        sub = [r for r in resolved if r["levels"] == cohort]
        print("\n" + "─" * 70)
        print(f"{label}  (n={sub and len(sub) or 0}) — {meaning}")
        print("─" * 70)
        if not sub:
            print("  нет разрешившихся сигналов в этой группе")
            continue

        wins = sum(1 for r in sub if r["outcome"] == "win")
        lo, hi = wilson(wins, len(sub))
        print(f"  win rate: {wins}/{len(sub)} = {wins / len(sub) * 100:.0f}%  "
              f"(95% ДИ {lo * 100:.0f}%–{hi * 100:.0f}%)")

        print(f"\n  {'полоса WEF':<12}{'N':>4}{'побед':>7}{'win rate':>10}{'95% ДИ':>16}")
        for lo_b, hi_b in BANDS:
            band = [r for r in sub if lo_b <= r["wef"] <= hi_b]
            if not band:
                continue
            w = sum(1 for r in band if r["outcome"] == "win")
            cl, ch = wilson(w, len(band))
            print(f"  {f'{lo_b}-{hi_b}':<12}{len(band):>4}{w:>7}"
                  f"{w / len(band) * 100:>9.0f}%"
                  f"{f'{cl * 100:.0f}%–{ch * 100:.0f}%':>16}")

        # Win rate alone cannot judge this score, and reading it that way would
        # get the wrong answer. The score's heaviest live factor is risk_reward:
        # 3:1 scores higher than 1:1. A wider target relative to the stop is
        # mechanically LESS likely to be reached first — that is geometry, not
        # weakness — so a score that rewards R:R must show a lower win rate at
        # the top. The question is whether the payoff compensates.
        print(f"\n  {'полоса WEF':<12}{'N':>4}{'ср. R:R':>9}{'ср. P&L':>10}"
              f"{'сумма P&L':>11}")
        for lo_b, hi_b in BANDS:
            band = [r for r in sub if lo_b <= r["wef"] <= hi_b]
            if not band:
                continue
            rrs, pnls = [], []
            for r in band:
                e, tp, sl = r["entry"], r["tp"], r["sl"]
                tp_pct = abs(tp - e) / e * 100
                sl_pct = abs(e - sl) / e * 100
                if sl_pct > 0:
                    rrs.append(tp_pct / sl_pct)
                pnls.append(tp_pct if r["outcome"] == "win" else -sl_pct)
            print(f"  {f'{lo_b}-{hi_b}':<12}{len(band):>4}"
                  f"{statistics.fmean(rrs) if rrs else 0:>8.1f}"
                  f"{statistics.fmean(pnls):>+9.2f}%{sum(pnls):>+10.1f}%")

        all_pnl = []
        for r in sub:
            e, tp, sl = r["entry"], r["tp"], r["sl"]
            all_pnl.append(abs(tp - e) / e * 100 if r["outcome"] == "win"
                           else -abs(e - sl) / e * 100)
        print(f"  {'ИТОГО':<12}{len(sub):>4}{'':>8}"
              f"{statistics.fmean(all_pnl):>+9.2f}%{sum(all_pnl):>+10.1f}%")

        r_corr = point_biserial([r["wef"] for r in sub],
                                [1 if r["outcome"] == "win" else 0 for r in sub])
        if r_corr is None:
            print("\n  Корреляция: не определена (один из классов пуст "
                  "или скор без разброса)")
        else:
            strength = ("нет связи" if abs(r_corr) < 0.1
                        else "слабая" if abs(r_corr) < 0.3
                        else "умеренная" if abs(r_corr) < 0.5 else "сильная")
            print(f"\n  Корреляция скора с исходом: r = {r_corr:+.3f} ({strength})")
            if len(sub) < 30:
                print(f"  ВНИМАНИЕ: n={len(sub)} — на такой выборке r нестабилен, "
                      f"это ориентир, а не доказательство.")

    print("\n" + "=" * 70)
    src = [r for r in resolved if r["levels"] == "source"]
    print(f"ЧТО ЭТО ЗНАЧИТ: валидировать скор можно только на группе "
          f"«уровни от источника» (n={len(src)}).")
    print("Остальные группы измеряют наши собственные правила расстановки "
          "уровней — полезно,")
    print("но это другой вопрос. Не смешивайте их в одну цифру.")


async def main():
    as_json = "--json" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    cache = None
    if "--cache" in sys.argv:
        cache = sys.argv[sys.argv.index("--cache") + 1]

    if cache and os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            report(json.load(f), as_json)
        return

    async with async_session() as db:
        sigs = [s for s in (await db.execute(
            select(Signal).order_by(Signal.created_at)
        )).scalars().all() if not is_seed_signal(s)]
        sigs = [s for s in sigs
                if s.entry_price and s.take_profit and s.stop_loss]
        if limit:
            sigs = sigs[:limit]

        rows = []
        for i, s in enumerate(sigs, 1):
            res = await replay(s)
            if res is None:
                continue
            rows.append({
                "ticker": s.ticker,
                "action": s.action.value,
                "wef": round((s.ai_confidence or 0) * 100),
                "entry": s.entry_price,
                "tp": s.take_profit,
                "sl": s.stop_loss,
                "levels": level_source(s),
                "created": s.created_at.date().isoformat() if s.created_at else None,
                **res,
            })
            if not as_json and i % 10 == 0:
                print(f"  ...{i}/{len(sigs)}", file=sys.stderr)

    if cache:
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
    report(rows, as_json)


asyncio.run(main())
