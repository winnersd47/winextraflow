"""Recompute `ai_confidence` for every stored signal under the current scoring.

Needed after any change to `ai_rating`. Scores are written once, at ingest, and
everything downstream reads the stored value: the free/VIP teaser split, the
result-publishing gate, the screener filter, `wef_validation.py`. Leaving them at
their old values means the code computes one thing and the platform acts on
another.

The change that prompted this: factors with no measurable input used to return a
neutral 0.5. They now return None and the weights are renormalized over what was
measurable, which moved the median score from 65 to 86 — so every stored value
and every absolute threshold was calibrated against a formula that no longer
exists.

Prints the before/after distribution and the percentile cut-offs, because the two
thresholds in config.py are functions of this distribution.

Usage:
    python scripts/rescore_signals.py --check   # report, change nothing
    python scripts/rescore_signals.py           # rewrite ai_confidence
"""
import asyncio
import os
import statistics
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models.signal import Signal
from app.services.ai_rating import ai_rating_service
from app.services.signal_quality import is_seed_signal


def dist(vals: list[int], label: str) -> None:
    if not vals:
        print(f"{label}: пусто")
        return
    s = sorted(vals)
    n = len(s)
    def p(q):
        return s[min(n - 1, int(n * q))]
    print(f"{label}: n={n}  min {s[0]}  p10 {p(.10)}  p25 {p(.25)}  "
          f"медиана {p(.50)}  p75 {p(.75)}  p90 {p(.90)}  max {s[-1]}  "
          f"ст.откл {statistics.pstdev(s):.1f}")


async def main():
    check_only = "--check" in sys.argv
    async with async_session() as db:
        sigs = (await db.execute(select(Signal))).scalars().all()
        real = [s for s in sigs if not is_seed_signal(s)]

        before, after, covs, changed = [], [], [], 0
        for s in real:
            old = round((s.ai_confidence or 0) * 100)
            b = await ai_rating_service.rate_signal(db, s)
            new = round(b.final_confidence * 100)
            before.append(old)
            after.append(new)
            covs.append(b.coverage)
            if old != new:
                changed += 1
            if not check_only:
                s.ai_confidence = b.final_confidence
                s.ai_reasoning = b.reasoning

        print(f"Реальных сигналов: {len(real)} (seed {len(sigs) - len(real)} не трогаю)")
        print(f"Изменится значение у: {changed}\n")
        dist(before, "ДО ")
        dist(after, "ПОСЛЕ")
        print(f"\nсреднее покрытие: {statistics.fmean(covs):.2f} "
              f"— столько веса реально измерено")

        s = sorted(after)
        n = len(s)
        def p(q):
            return s[min(n - 1, int(n * q))]
        print(f"\nПороги в config.py против нового распределения:")
        for name, val, sense in (
            ("free_teaser_max_wef", settings.free_teaser_max_wef, "VIP-эксклюзив при >="),
            ("free_result_min_wef", settings.free_result_min_wef, "результат в канал при >="),
        ):
            hit = sum(1 for x in s if x >= val)
            print(f"  {name}={val}: {sense} — {hit}/{n} ({hit / n * 100:.0f}%)")
        print(f"  ориентиры: p25={p(.25)}  медиана={p(.50)}  p75={p(.75)}  p90={p(.90)}")
        print(f"  free_teaser_percentile={settings.free_teaser_percentile} "
              f"=> согласованный порог {p(settings.free_teaser_percentile / 100)}")

        if check_only:
            print("\n--check: изменений не вносил.")
            return
        await db.commit()
        print(f"\nПерезаписано: {len(real)} сигналов")
        print("Дальше: python scripts/wef_validation.py — проверить, "
              "разделяет ли новый скор исходы.")


asyncio.run(main())
