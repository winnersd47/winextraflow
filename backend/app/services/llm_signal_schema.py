"""Strict schema for what the LLM parser is allowed to return.

The parser previously accepted whatever came back: it scraped `{...}` blocks out
of prose with a regex, took the last one that happened to contain a "ticker" key,
and passed the values straight into `float()`. Everything after that point trusted
the result — and the three WEF factors that actually vary all read entry / TP / SL,
so a hallucinated level does not merely produce a bad signal, it produces a bad
signal with a confident score attached.

`LLMSignal` is the contract. It rejects, rather than repairs:

  * a target on the wrong side of entry for the stated direction. A "buy" with a
    target below entry is not a parse, it is a misread of the direction, and
    guessing which half was wrong would invent a trade nobody published.
  * a stop on the wrong side, same reasoning.
  * non-positive prices, and levels absurdly far from entry (a decimal-point slip
    turns 2.47 into 247 and passes every other check).

`JSON_SCHEMA` is sent to the API as `response_format` so the model is constrained
at generation time on providers that support it. Validation still runs afterwards:
structured-output support varies per model on OpenRouter, and a schema cannot
express the cross-field rules above.
"""

import logging

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

# A level further than this from entry is treated as a misparse rather than a very
# ambitious trade. 3x covers every real signal seen in this project; a
# decimal-point slip lands one or two orders of magnitude out.
MAX_LEVEL_MULTIPLE = 3.0


class LLMSignal(BaseModel):
    """One parsed signal, or a validation error. No middle state."""

    ticker: str = Field(min_length=2, max_length=20)
    action: str
    entry_price: float = Field(gt=0)
    take_profit: float | None = Field(default=None, gt=0)
    stop_loss: float | None = Field(default=None, gt=0)

    @field_validator("ticker")
    @classmethod
    def _clean_ticker(cls, v: str) -> str:
        return v.strip().upper().replace(" ", "")

    @field_validator("action")
    @classmethod
    def _norm_action(cls, v: str) -> str:
        a = v.strip().lower()
        if a in ("buy", "long", "покупка", "лонг"):
            return "buy"
        if a in ("sell", "short", "продажа", "шорт"):
            return "sell"
        raise ValueError(f"неизвестное направление: {v!r}")

    @model_validator(mode="after")
    def _levels_consistent(self):
        e = self.entry_price
        for name, lvl in (("take_profit", self.take_profit),
                          ("stop_loss", self.stop_loss)):
            if lvl is None:
                continue
            if not (e / MAX_LEVEL_MULTIPLE <= lvl <= e * MAX_LEVEL_MULTIPLE):
                raise ValueError(
                    f"{name} {lvl} слишком далеко от входа {e} — похоже на "
                    f"смещение разряда, а не на уровень")

        if self.action == "buy":
            if self.take_profit is not None and self.take_profit <= e:
                raise ValueError("покупка с тейком не выше входа")
            if self.stop_loss is not None and self.stop_loss >= e:
                raise ValueError("покупка со стопом не ниже входа")
        else:
            if self.take_profit is not None and self.take_profit >= e:
                raise ValueError("продажа с тейком не ниже входа")
            if self.stop_loss is not None and self.stop_loss <= e:
                raise ValueError("продажа со стопом не выше входа")
        return self


# Sent as `response_format` where the provider supports it. `not_a_signal` is part
# of the schema on purpose: without it the model has no valid way to decline, and
# a model with no way to decline invents a signal out of a news post.
JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "trading_signal",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["not_a_signal", "ticker", "action", "entry_price",
                         "take_profit", "stop_loss"],
            "properties": {
                "not_a_signal": {
                    "type": "boolean",
                    "description": "true if this is news, analytics or opinion "
                                   "rather than an actionable trade",
                },
                "ticker": {"type": ["string", "null"]},
                "action": {"type": ["string", "null"], "enum": ["buy", "sell", None]},
                "entry_price": {"type": ["number", "null"]},
                "take_profit": {"type": ["number", "null"]},
                "stop_loss": {"type": ["number", "null"]},
            },
        },
    },
}

PROMPT = """Extract a trading signal from this message (may be Russian or English).
Return JSON only, no explanation.

Set "not_a_signal": true if this is NOT an actionable trade (news, analytics,
opinion, a results report). In that case leave every other field null.

Rules:
- action: "buy" for покупка/лонг/buy/long, "sell" for продажа/шорт/sell/short
- ticker: the instrument symbol (SBER, BTCUSDT, EURUSD, XAUUSD). Never an order
  type like "LIMIT" or a leverage note like "5-10X".
- entry_price: entry / цена входа, as a number
- take_profit: TP / цель / тейк, or null if the message does not state one
- stop_loss: SL / стоп, or null if the message does not state one
- Do not compute a level the message does not state. Null is correct and expected.
- For a buy, take_profit must be above entry and stop_loss below it. For a sell,
  the reverse. If the message contradicts that, you have misread the direction —
  re-read it rather than adjusting the numbers.

Message:
{text}

JSON:"""
