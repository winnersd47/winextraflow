"""Measure a candidate LLM against the messages we are actually losing.

Why this exists
---------------
A free OpenRouter slug can be withdrawn at any time, and when it is, the
fallback parser does not degrade — it stops. `openai/gpt-oss-20b:free` was
withdrawn on 2026-11-04 and answered 404 to 4,603 consecutive calls over
fifteen days. Nothing failed loudly: the rejection log recorded every message
as "ни regex, ни LLM не разобрали", which read as the sources being
unparseable rather than as our own parser being dead.

So picking a replacement must not be done by reading model cards. A model that
answers "ok" to a smoke test can still be unable to read a signal — measured
2026-11-18, nemotron-3.5-lightning answered every smoke test and then returned
prose the schema could not read on every real message.

What it measures
----------------
Real `raw_message` rows from rejected_candidates where stage='parse' — the
messages the regex parsers could not read — run through the production path
(`telegram_parser.parse_with_llm`), so the result includes schema validation
and the JSON extraction fallback, not just the model's reply.

Two numbers matter, and the second one matters more:

  разобрано          the model produced a signal at all
  с полными уровнями entry AND stop AND target were all present

Only the second is a tradable signal. A parse that invents nothing but a
direction and a target leaves the stop to be derived, and signals whose levels
were derived rather than read are how the track record got polluted before.

Writes nothing. Reads the database read-only.

Usage
-----
    py -3.13 scripts/bench_parse_models.py 40 inclusionai/ling-3.2-flash:free
    py -3.13 scripts/bench_parse_models.py 20 <slug-a> <slug-b> <slug-c>

Note the free tier allows 50 calls a DAY in total without credits, and
`parse_with_llm` retries once, so a 40-message run can cost 80 calls and the
tail of it will come back as 429 "Rate limit exceeded: free-models-per-day".
Check the outcomes in llm_metrics.jsonl before believing a zero.
"""
import asyncio
import os
import random
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.telegram import telegram_parser   # noqa: E402

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BACKEND, "winextraflow.db")
# Fixed, so every model is judged on the same messages and two runs of the same
# model are comparable. The model itself is not deterministic — ling-3.2-flash
# returned 8 and then 6 parses on this identical sample — so a single run is an
# estimate, not a measurement.
SEED = 20261118


def sample(n: int) -> list[tuple[str, str]]:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT channel, raw_message FROM rejected_candidates "
        "WHERE stage='parse' AND raw_message IS NOT NULL "
        "AND length(raw_message) > 20 ORDER BY id").fetchall()
    con.close()
    out = [(r["channel"], r["raw_message"]) for r in rows]
    random.Random(SEED).shuffle(out)
    return out[:n]


async def run(model: str, msgs: list[tuple[str, str]]) -> dict:
    os.environ["LLM_MODEL"] = model
    res = {"parsed": 0, "complete": 0, "none": 0, "raised": 0, "examples": []}
    for ch, text in msgs:
        try:
            p = await telegram_parser.parse_with_llm(text)
        except Exception as e:
            res["raised"] += 1
            print(f"      вызов упал: {type(e).__name__}: {e}")
            continue
        if p is None:
            res["none"] += 1
            continue
        res["parsed"] += 1
        full = p.stop_loss is not None and p.take_profit is not None
        res["complete"] += bool(full)
        res["examples"].append(
            f"      [{ch}] {p.action.upper()} {p.ticker} вход={p.entry_price} "
            f"стоп={p.stop_loss} цель={p.take_profit}"
            f"{'' if full else '   <- неполные уровни, стоп придётся выводить'}")
    return res


async def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    n = int(sys.argv[1])
    msgs = sample(n)
    if not msgs:
        print("В журнале отказов нет parse-записей с текстом — измерять нечего.")
        sys.exit(1)
    print(f"выборка: {len(msgs)} реальных сообщений из parse-отказов "
          f"(seed {SEED})\n")
    for model in sys.argv[2:]:
        r = await run(model, msgs)
        n_ = len(msgs)
        print(f"{model}")
        print(f"   разобрано            {r['parsed']:>3}/{n_}"
              f"  = {r['parsed']*100/n_:.0f}%")
        print(f"   из них полные уровни {r['complete']:>3}/{n_}"
              f"  = {r['complete']*100/n_:.0f}%   <- только это торгуемо")
        print(f"   не сигнал / не смог  {r['none']:>3}"
              f"   | вызов упал {r['raised']}")
        for line in r["examples"][:6]:
            print(line)
        print()
    print("Если доля нулевая — сверьтесь с llm_metrics.jsonl: 429 "
          "'free-models-per-day' означает исчерпанную квоту, а не плохую модель.")


if __name__ == "__main__":
    asyncio.run(main())
