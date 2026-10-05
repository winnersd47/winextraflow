"""Tests for the LLM parser's output contract and its metrics ledger.

The parser feeds `entry_price`, `take_profit` and `stop_loss` into the signal —
and those are the only inputs the three live WEF factors read. A hallucinated
level therefore does not produce a merely bad signal, it produces a bad signal
with a confident score attached.

Before this contract existed the parser scraped `{...}` blocks out of prose with
a regex, took whichever one had a "ticker" key, and passed the values into
`float()`. Every failure — missing key, HTTP error, timeout, unparseable body,
nonsense levels, unrecognised ticker, and the model correctly declining — returned
the same bare `None`, so the log could not tell a broken provider from a channel
posting news.
"""

import json
import os

import httpx
import pytest
from pydantic import ValidationError

from app.services import llm_metrics
from app.services.llm_signal_schema import JSON_SCHEMA, LLMSignal


# ═══════════════════════════════════════════════════════════════════════
# Schema
# ═══════════════════════════════════════════════════════════════════════

def test_accepts_a_well_formed_signal():
    s = LLMSignal(ticker="sber", action="покупка", entry_price=300,
                  take_profit=330, stop_loss=290)
    assert s.ticker == "SBER"
    assert s.action == "buy"


def test_accepts_a_signal_without_levels():
    """Null levels are correct and expected — most sources state no stop."""
    s = LLMSignal(ticker="GAZP", action="buy", entry_price=140)
    assert s.take_profit is None and s.stop_loss is None


@pytest.mark.parametrize("kw,fragment", [
    (dict(ticker="SBER", action="buy", entry_price=300, take_profit=280),
     "тейком не выше"),
    (dict(ticker="SBER", action="buy", entry_price=300, stop_loss=310),
     "стопом не ниже"),
    (dict(ticker="SBER", action="sell", entry_price=300, take_profit=320),
     "тейком не ниже"),
    (dict(ticker="SBER", action="sell", entry_price=300, stop_loss=290),
     "стопом не выше"),
])
def test_rejects_levels_on_the_wrong_side(kw, fragment):
    """A target on the wrong side is a misread direction, not a bad trade.

    Repairing it would invent a trade nobody published, so it is refused.
    """
    with pytest.raises(ValidationError) as e:
        LLMSignal(**kw)
    assert fragment in str(e.value)


def test_rejects_a_shifted_decimal_point():
    """2.47 read as 254 passes every per-field check and every sanity of sign."""
    with pytest.raises(ValidationError) as e:
        LLMSignal(ticker="ENJUSDT", action="buy", entry_price=2.47,
                  take_profit=254.0, stop_loss=2.45)
    assert "слишком далеко" in str(e.value)


def test_rejects_order_type_as_direction():
    """"SELL LIMIT" and "BUY 5-10X" were captured as tickers in production."""
    with pytest.raises(ValidationError):
        LLMSignal(ticker="SBER", action="LIMIT", entry_price=300)


def test_rejects_non_positive_price():
    with pytest.raises(ValidationError):
        LLMSignal(ticker="SBER", action="buy", entry_price=0)


def test_schema_lets_the_model_decline():
    """Without a `not_a_signal` field the model has no valid way to say no, and
    a model with no way to say no invents a signal out of a news post."""
    props = JSON_SCHEMA["json_schema"]["schema"]["properties"]
    assert "not_a_signal" in props
    assert props["not_a_signal"]["type"] == "boolean"
    assert "not_a_signal" in JSON_SCHEMA["json_schema"]["schema"]["required"]


# ═══════════════════════════════════════════════════════════════════════
# Metrics ledger
# ═══════════════════════════════════════════════════════════════════════

def test_unknown_model_costs_null_not_zero():
    """A silent zero reads as "this is free" and hides the one number the
    ledger exists to surface."""
    assert llm_metrics.cost_usd("some/model-nobody-priced", 1000, 1000) is None
    assert llm_metrics.cost_usd("openai/gpt-oss-20b:free", 1000, 1000) == 0.0
    assert llm_metrics.cost_usd("openai/gpt-4o-mini", 1_000_000, 0) == 0.15


def test_usage_parsed_from_both_api_shapes():
    """OpenRouter says prompt/completion, Anthropic says input/output."""
    assert llm_metrics.usage_from_response(
        {"usage": {"prompt_tokens": 10, "completion_tokens": 20}}) == (10, 20)
    assert llm_metrics.usage_from_response(
        {"usage": {"input_tokens": 30, "output_tokens": 40}}) == (30, 40)
    assert llm_metrics.usage_from_response({}) == (0, 0)


def test_ledger_records_each_outcome_separately(tmp_path, monkeypatch):
    path = str(tmp_path / "m.jsonl")
    monkeypatch.setattr(llm_metrics, "LEDGER_PATH", path)
    for outcome in ("parsed", "not_a_signal", "invalid_json", "http_error"):
        llm_metrics.record("t", "openai/gpt-oss-20b:free",
                           outcome == "parsed", outcome, 120, 100, 50)

    s = llm_metrics.summarize(path)
    assert s["calls"] == 4
    assert s["ok"] == 1
    assert set(s["by_outcome"]) == {"parsed", "not_a_signal", "invalid_json",
                                    "http_error"}
    assert s["unpriced_calls"] == 0


def test_ledger_never_raises_on_a_bad_path(monkeypatch):
    """Metrics must not be able to break the pipeline they observe."""
    monkeypatch.setattr(llm_metrics, "LEDGER_PATH",
                        os.path.join("Z:\\nonexistent", "m.jsonl"))
    row = llm_metrics.record("t", "m", True, "parsed", 1)
    assert row["outcome"] == "parsed"


# ═══════════════════════════════════════════════════════════════════════
# End-to-end: retry policy
# ═══════════════════════════════════════════════════════════════════════

def _openrouter(content: str, code: int = 200) -> dict:
    return {"choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 400, "completion_tokens": 60}}


@pytest.fixture
def parser_env(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-oss-20b:free")
    path = str(tmp_path / "m.jsonl")
    monkeypatch.setattr(llm_metrics, "LEDGER_PATH", path)
    return path


def _mock_post(monkeypatch, code: int, payload: dict, counter: list):
    async def fake(self, url, **kw):
        counter.append(kw.get("json", {}))
        return httpx.Response(code, json=payload,
                              request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx.AsyncClient, "post", fake)


@pytest.mark.asyncio
async def test_valid_response_parses_on_first_attempt(parser_env, monkeypatch):
    from app.services.telegram import telegram_parser
    calls = []
    _mock_post(monkeypatch, 200, _openrouter(json.dumps(
        {"not_a_signal": False, "ticker": "SBER", "action": "buy",
         "entry_price": 300, "take_profit": 330, "stop_loss": 290})), calls)

    res = await telegram_parser.parse_with_llm("сообщение")
    assert res is not None and res.ticker == "SBER"
    assert len(calls) == 1
    # The schema must actually be sent, not just defined.
    assert calls[0].get("response_format") == JSON_SCHEMA


@pytest.mark.asyncio
async def test_invalid_json_is_retried_once(parser_env, monkeypatch):
    from app.services.telegram import telegram_parser
    calls = []
    _mock_post(monkeypatch, 200, _openrouter("!" * 300), calls)

    assert await telegram_parser.parse_with_llm("сообщение") is None
    assert len(calls) == 2, "a malformed answer is worth asking again for"
    outcomes = [r["outcome"] for r in llm_metrics.summarize(parser_env)["rows"]]
    assert outcomes == ["invalid_json", "invalid_json"]


@pytest.mark.asyncio
async def test_http_error_is_not_retried(parser_env, monkeypatch):
    """The caller's ledger grants one attempt per message for the whole run.
    Spending it twice on a provider outage means the message can never be
    reparsed once the provider recovers."""
    from app.services.telegram import telegram_parser
    calls = []
    _mock_post(monkeypatch, 429, {"error": {"message": "rate limited"}}, calls)

    assert await telegram_parser.parse_with_llm("сообщение") is None
    assert len(calls) == 1
    rows = llm_metrics.summarize(parser_env)["rows"]
    assert rows[0]["outcome"] == "http_error"


@pytest.mark.asyncio
async def test_declining_is_recorded_as_success_not_failure(parser_env, monkeypatch):
    """"This is a news post" is the parser working, and must be countable
    separately from "the parser is broken"."""
    from app.services.telegram import telegram_parser
    calls = []
    _mock_post(monkeypatch, 200, _openrouter(json.dumps(
        {"not_a_signal": True, "ticker": None, "action": None,
         "entry_price": None, "take_profit": None, "stop_loss": None})), calls)

    assert await telegram_parser.parse_with_llm("новостной пост") is None
    assert len(calls) == 1, "a correct refusal must not be retried"
    rows = llm_metrics.summarize(parser_env)["rows"]
    assert rows[0]["outcome"] == "not_a_signal"


@pytest.mark.asyncio
async def test_bad_levels_are_retried_then_refused(parser_env, monkeypatch):
    from app.services.telegram import telegram_parser
    calls = []
    _mock_post(monkeypatch, 200, _openrouter(json.dumps(
        {"not_a_signal": False, "ticker": "SBER", "action": "buy",
         "entry_price": 300, "take_profit": 280, "stop_loss": 290})), calls)

    assert await telegram_parser.parse_with_llm("сообщение") is None
    assert len(calls) == 2
    rows = llm_metrics.summarize(parser_env)["rows"]
    assert all(r["outcome"] == "schema_invalid" for r in rows)


@pytest.mark.asyncio
async def test_json_is_recovered_from_prose(parser_env, monkeypatch):
    """response_format is honoured by only some OpenRouter models; the rest
    still wrap the object in an explanation, and reasoning models emit drafts."""
    from app.services.telegram import telegram_parser
    calls = []
    _mock_post(monkeypatch, 200, _openrouter(
        'Thinking... {"draft": 1} Final: {"not_a_signal": false, '
        '"ticker": "GAZP", "action": "sell", "entry_price": 140, '
        '"take_profit": 130, "stop_loss": 145}'), calls)

    res = await telegram_parser.parse_with_llm("сообщение")
    assert res is not None and res.ticker == "GAZP" and res.action == "sell"


@pytest.mark.asyncio
async def test_no_api_key_is_its_own_outcome(parser_env, monkeypatch):
    from app.config import settings
    from app.services.telegram import telegram_parser
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(settings, "openrouter_api_key", "")

    assert await telegram_parser.parse_with_llm("сообщение") is None
    rows = llm_metrics.summarize(parser_env)["rows"]
    assert rows[0]["outcome"] == "no_api_key"
