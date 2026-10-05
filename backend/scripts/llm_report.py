"""What the LLM calls cost and how long they took.

Reads the JSONL ledger written by `app/services/llm_metrics.py`. Before it
existed there was no way to answer any of this: the parser returned None for
every failure, so a run of 40 messages that produced 12 signals could equally
have been 28 non-signals or 28 broken responses.

Usage:
    python scripts/llm_report.py                # everything in the ledger
    python scripts/llm_report.py --days 7
    python scripts/llm_report.py --json
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.llm_metrics import LEDGER_PATH, PRICES, summarize

# Reasons that mean the pipeline is fine and the message simply was not a signal.
BENIGN = {"not_a_signal"}


def main():
    days = None
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    since = None
    if days:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    s = summarize(LEDGER_PATH, since)
    if "--json" in sys.argv:
        s.pop("rows", None)
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return

    if not s["calls"]:
        print(f"Журнал пуст или отсутствует: {LEDGER_PATH}")
        print("Он заполняется при каждом вызове LLM-парсера "
              "(scripts/tg_backfill.py).")
        return

    window = f"за {days} дн." if days else "за всё время"
    print("=" * 64)
    print(f"LLM: стоимость и латентность {window}")
    print("=" * 64)
    print(f"Вызовов:           {s['calls']}")
    print(f"Успешных разборов: {s['ok']} ({s['ok'] / s['calls'] * 100:.0f}%)")

    benign = sum(v for k, v in s["by_outcome"].items() if k in BENIGN)
    broken = s["calls"] - s["ok"] - benign
    print(f"Корректных отказов: {benign}  (сообщение не было сигналом)")
    print(f"Проблемных:         {broken}")

    print("\nПо исходам:")
    for k, v in s["by_outcome"].items():
        mark = "  " if k in BENIGN or k == "parsed" else "! "
        print(f"  {mark}{k:<18} {v:>5}  ({v / s['calls'] * 100:.0f}%)")

    lat = s["latency_ms"]
    print(f"\nЛатентность: p50 {lat['p50']} мс · p90 {lat['p90']} мс · "
          f"макс {lat['max']} мс")

    tok = s["prompt_tokens"] + s["completion_tokens"]
    print(f"Токены: {s['prompt_tokens']:,} вход + {s['completion_tokens']:,} выход "
          f"= {tok:,}".replace(",", " "))
    print(f"Стоимость: ${s['cost_usd']}")
    if s["unpriced_calls"]:
        print(f"  ВНИМАНИЕ: {s['unpriced_calls']} вызовов без прайса в таблице — "
              f"их стоимость НЕ учтена. Добавьте модель в "
              f"llm_metrics.PRICES, иначе расход не виден.")

    # Per-1000-signals projection, which is the number that matters when deciding
    # whether to move off the free tier.
    if s["ok"]:
        per_call = tok / s["calls"]
        print(f"\nНа 1000 сообщений: ~{per_call * 1000 / 1000:.0f}k токенов")
        for model in ("openai/gpt-4o-mini", "anthropic/claude-3.5-haiku"):
            p_in, p_out = PRICES[model]
            share_in = s["prompt_tokens"] / tok if tok else 0
            cost_1k = (per_call * 1000 / 1e6) * (p_in * share_in
                                                 + p_out * (1 - share_in))
            print(f"  на {model}: ~${cost_1k:.2f}")
        print("  (текущая модель бесплатна; это оценка на случай перехода)")


main()
