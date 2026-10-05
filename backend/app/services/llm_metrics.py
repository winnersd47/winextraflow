"""Per-call cost and latency ledger for LLM requests.

Nothing measured any of this before. `parse_with_llm` returned `None` for every
failure mode — no API key, HTTP error, timeout, unparseable JSON, rejected ticker —
so the log could not distinguish "the model is broken" from "the key is missing"
from "this message was not a signal". At the same time OpenRouter returns a
`usage` block on every response, and it was discarded.

What this records, one JSON object per line:

    ts, caller, model, ok, outcome, latency_ms,
    prompt_tokens, completion_tokens, cost_usd, attempt, note

`outcome` is the part that was missing. It names why a call ended the way it did,
so a run can be read as "40 calls, 31 parsed, 6 not-a-signal, 3 invalid JSON, no
HTTP errors" instead of "40 calls, 31 results".

Cost is computed from a local price table rather than trusted from the response,
because OpenRouter only returns a credit figure for some models and zero for the
free tier. An unknown model logs `cost_usd: null` rather than 0 — a silent zero
would read as "this is free" and hide the one number the ledger exists to show.

Deliberately a JSONL file, not a table: it has to survive the API being down and
be readable with a text editor on the VPS. Rotated by size, since it sits next to
a cron job that will run unattended for months.
"""

import json
import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

LEDGER_PATH = os.environ.get(
    "LLM_METRICS_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "llm_metrics.jsonl"),
)
MAX_BYTES = 5 * 1024 * 1024

# USD per 1M tokens, (prompt, completion). Keep model ids exactly as sent to the
# API. A model missing here logs a null cost, not a zero.
PRICES: dict[str, tuple[float, float]] = {
    # Free tier on OpenRouter — genuinely 0, and worth stating explicitly so it
    # is distinguishable from "unknown".
    "openai/gpt-oss-20b:free": (0.0, 0.0),
    "meta-llama/llama-3.3-70b-instruct:free": (0.0, 0.0),
    "google/gemini-2.0-flash-exp:free": (0.0, 0.0),
    "deepseek/deepseek-chat-v3-0324:free": (0.0, 0.0),
    # Paid, for when the free tier's rate limits become the bottleneck.
    "openai/gpt-4o-mini": (0.15, 0.60),
    "anthropic/claude-3.5-haiku": (0.80, 4.00),
    "anthropic/claude-sonnet-4": (3.00, 15.00),
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "deepseek/deepseek-chat": (0.27, 1.10),
}

# Every value `outcome` may take, so a reader knows the full vocabulary.
OUTCOMES = (
    "parsed",          # a usable object came back
    "not_a_signal",    # the model correctly said this is news/analytics
    "invalid_json",    # response contained nothing parseable
    "schema_invalid",  # parsed, but failed validation
    "rejected_ticker", # passed schema, ticker not recognised
    "empty_response",  # no content and no reasoning
    "http_error",
    "timeout",
    "no_api_key",
    "exception",
)


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    """Price the call, or None when the model is not in the table."""
    price = PRICES.get(model)
    if price is None:
        return None
    p_in, p_out = price
    return round(prompt_tokens / 1e6 * p_in + completion_tokens / 1e6 * p_out, 6)


def _rotate() -> None:
    try:
        if os.path.exists(LEDGER_PATH) and os.path.getsize(LEDGER_PATH) > MAX_BYTES:
            os.replace(LEDGER_PATH, LEDGER_PATH + ".1")
    except OSError as e:
        logger.debug(f"LLM metrics rotate failed: {e}")


def record(caller: str, model: str, ok: bool, outcome: str, latency_ms: int,
           prompt_tokens: int = 0, completion_tokens: int = 0,
           attempt: int = 1, note: str = "") -> dict:
    """Append one line. Never raises — metrics must not break the caller."""
    row = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "caller": caller,
        "model": model,
        "ok": ok,
        "outcome": outcome,
        "latency_ms": latency_ms,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cost_usd": cost_usd(model, prompt_tokens, completion_tokens),
        "attempt": attempt,
        "note": note[:200],
    }
    try:
        _rotate()
        with open(LEDGER_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as e:
        logger.debug(f"LLM metrics write failed: {e}")
    return row


@contextmanager
def timed():
    """Measure wall time around a call. `elapsed_ms()` works after the block."""
    start = time.perf_counter()
    box = {"ms": 0}

    def elapsed_ms() -> int:
        return box["ms"] or int((time.perf_counter() - start) * 1000)

    box["elapsed_ms"] = elapsed_ms
    try:
        yield box
    finally:
        box["ms"] = int((time.perf_counter() - start) * 1000)


def usage_from_response(payload: dict) -> tuple[int, int]:
    """Pull (prompt, completion) token counts out of an OpenAI-compatible body.

    Anthropic names them input_tokens/output_tokens; both shapes appear here
    because the parser has a fallback path to the Anthropic API directly.
    """
    u = payload.get("usage") or {}
    return (
        int(u.get("prompt_tokens") or u.get("input_tokens") or 0),
        int(u.get("completion_tokens") or u.get("output_tokens") or 0),
    )


def summarize(path: str = LEDGER_PATH, since_iso: str | None = None) -> dict:
    """Aggregate the ledger. Used by scripts/llm_report.py."""
    rows = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if since_iso and r.get("ts", "") < since_iso:
                    continue
                rows.append(r)
    except FileNotFoundError:
        return {"calls": 0, "rows": []}

    lat = sorted(r.get("latency_ms", 0) for r in rows)
    priced = [r["cost_usd"] for r in rows if r.get("cost_usd") is not None]
    by_outcome: dict[str, int] = {}
    for r in rows:
        by_outcome[r.get("outcome", "?")] = by_outcome.get(r.get("outcome", "?"), 0) + 1

    def pct(q: float) -> int:
        return lat[min(len(lat) - 1, int(len(lat) * q))] if lat else 0

    return {
        "calls": len(rows),
        "ok": sum(1 for r in rows if r.get("ok")),
        "by_outcome": dict(sorted(by_outcome.items(), key=lambda x: -x[1])),
        "latency_ms": {"p50": pct(.50), "p90": pct(.90),
                       "max": lat[-1] if lat else 0},
        "prompt_tokens": sum(r.get("prompt_tokens", 0) for r in rows),
        "completion_tokens": sum(r.get("completion_tokens", 0) for r in rows),
        "cost_usd": round(sum(priced), 6),
        "unpriced_calls": len(rows) - len(priced),
        "rows": rows,
    }
