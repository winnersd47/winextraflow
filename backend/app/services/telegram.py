"""Telegram channel signal parser service.

Connects to Telegram channels via Telethon, parses trading signal messages
and converts them into normalized Signal objects.
"""

import json
import logging
import re
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ParsedSignal:
    """Parsed signal data from a Telegram message."""

    ticker: str
    action: str  # "buy" or "sell"
    entry_price: float
    take_profit: float | None = None
    stop_loss: float | None = None
    timeframe: str | None = None
    # True when the source gave only a direction + target, so entry and stop were
    # computed rather than published. signal_levels.resolve_levels() replaces them
    # with a live entry and an ATR-based stop before the signal is stored.
    derived_levels: bool = False


# --- Signal parsing patterns ---
# Supports various popular crypto/forex Telegram channel formats

SIGNAL_PATTERNS = [
    # Format: "🟢 BUY BTCUSDT @ 65000 TP: 67000 SL: 63000"
    re.compile(
        r"(?:🟢|🔴|📈|📉|⬆️|⬇️)?\s*(?P<action>BUY|SELL|LONG|SHORT)\s+"
        r"(?P<ticker>[A-Z0-9/._-]+)\s*"
        r"(?:@|at|entry|price)[:\s]*(?P<price>[\d,.]+)"
        r"(?:.*?(?:TP|take\s*profit|target)[:\s]*(?P<tp>[\d,.]+))?"
        r"(?:.*?(?:SL|stop\s*loss|stop)[:\s]*(?P<sl>[\d,.]+))?",
        re.IGNORECASE | re.DOTALL,
    ),
    # Format: "BTCUSDT BUY\nEntry: 65000\nTP: 67000\nSL: 63000"
    re.compile(
        r"(?P<ticker>[A-Z0-9/._-]{2,20})\s+"
        r"(?P<action>BUY|SELL|LONG|SHORT)\s*"
        r"[\n\r]+\s*(?:Entry|Price)[:\s]*(?P<price>[\d,.]+)"
        r"(?:.*?(?:TP|Target|Take\s*Profit)\s*\d?[:\s]*(?P<tp>[\d,.]+))?"
        r"(?:.*?(?:SL|Stop\s*Loss|Stop)\s*[:\s]*(?P<sl>[\d,.]+))?",
        re.IGNORECASE | re.DOTALL,
    ),
    # Format: "#BTCUSDT 🟢 Entry: 65000 | TP1: 67000 | SL: 63000"
    re.compile(
        r"#?(?P<ticker>[A-Z0-9/._-]{2,20})\s*"
        r"(?:🟢|🔴|📈|📉)?\s*"
        r"(?:Entry|Price)[:\s]*(?P<price>[\d,.]+)\s*"
        r"(?:.*?(?P<action>BUY|SELL|LONG|SHORT))?"
        r"(?:.*?(?:TP|Target)\s*\d?[:\s]*(?P<tp>[\d,.]+))?"
        r"(?:.*?(?:SL|Stop)[:\s]*(?P<sl>[\d,.]+))?",
        re.IGNORECASE | re.DOTALL,
    ),
    # Simple format: "Buy BTCUSDT 65000"
    re.compile(
        r"(?P<action>BUY|SELL|LONG|SHORT)\s+(?P<ticker>[A-Z0-9/._-]{2,20})\s+(?P<price>[\d,.]+)",
        re.IGNORECASE,
    ),
]

# Words that are NOT tickers (order types, directions, common false-positives)
NON_TICKER_WORDS = {
    "LIMIT", "STOP", "MARKET", "BUY", "SELL", "LONG", "SHORT",
    "TP", "SL", "ENTRY", "PRICE", "TARGET", "NOW", "AT",
    "BELOW", "ABOVE", "HERE", "AROUND", "ZONE", "SPOT", "FUTURES",
    "LEVERAGE", "CROSS", "ISOLATED", "SIGNAL", "COIN", "PAIR", "USDT",
    "USING", "FROM", "WITH", "TODAY", "PROFIT", "LOSS", "RISK", "RR",
}

# Leverage patterns wrongly captured as ticker: "5X", "2-5X", "10-20X", "5-10x"
_LEVERAGE_RE = re.compile(r"^\d+([-–]\d+)?X$", re.IGNORECASE)


# The LLM returns whatever the message called the instrument, which for RU channels
# is often the company name: "Лукойл" -> LUKOIL rather than LKOH. An unrecognised
# ticker silently yields no candles — no chart, no ATR, no TP/SL monitoring — so the
# name has to be mapped back to the exchange symbol before the signal is stored.
_LATIN_ALIASES = {
    "LUKOIL": "LKOH", "SBERBANK": "SBER", "GAZPROM": "GAZP", "ROSNEFT": "ROSN",
    "NORNICKEL": "GMKN", "NORILSK": "GMKN", "NOVATEK": "NVTK", "YANDEX": "YDEX",
    "MAGNIT": "MGNT", "SEVERSTAL": "CHMF", "ALROSA": "ALRS", "POLYUS": "PLZL",
    "TATNEFT": "TATN", "AEROFLOT": "AFLT", "SURGUT": "SNGS", "SURGUTNEFTEGAS": "SNGS",
    "BITCOIN": "BTCUSDT", "ETHEREUM": "ETHUSDT", "SOLANA": "SOLUSDT",
}


def _resolve_ticker(raw: str) -> str:
    """Map a company name or alias to the exchange symbol the platform can price.

    Built by inverting signal_chart.NAME_MAP (ticker -> Russian name) so the two
    cannot drift apart, plus the Latin transliterations the model tends to emit.
    """
    t = (raw or "").strip().upper().lstrip("#")
    if not t:
        return t
    if t in _LATIN_ALIASES:
        return _LATIN_ALIASES[t]
    try:
        from app.services.signal_chart import NAME_MAP
        for ticker, name in NAME_MAP.items():
            if name.upper() == t:
                return ticker
    except Exception:          # never let a lookup failure drop a signal
        pass
    return t


def _is_valid_ticker(ticker: str) -> bool:
    """A ticker must contain letters, not be an order/direction word or leverage."""
    if not ticker or len(ticker) < 2:
        return False
    if ticker.upper() in NON_TICKER_WORDS:
        return False
    if _LEVERAGE_RE.match(ticker):
        return False
    # Must contain at least one letter (rejects "5-10", "1.5")
    if not any(c.isalpha() for c in ticker):
        return False
    return True

# Keywords that indicate a trading signal message (EN + RU)
SIGNAL_KEYWORDS = [
    # English
    "buy", "sell", "long", "short", "entry", "take profit",
    "stop loss", "tp", "sl", "target", "signal",
    # Russian
    "покупа", "продаж", "продаём", "продаем", "лонг", "шорт",
    "вход", "цель", "тейк", "стоп", "сигнал", "покупк",
    "докуп", "фиксир", "цена входа",
]


def _clean_price(price_str: str) -> float:
    """Clean price string: remove commas, convert to float."""
    return float(price_str.replace(",", ""))


def _normalize_action(action: str) -> str:
    """Normalize action to 'buy' or 'sell'."""
    action = action.lower().strip()
    if action in ("buy", "long"):
        return "buy"
    if action in ("sell", "short"):
        return "sell"
    return action


class TelegramParser:
    """Parse trading signals from Telegram messages."""

    @staticmethod
    def is_signal_message(text: str) -> bool:
        """Check if a message likely contains a trading signal."""
        text_lower = text.lower()
        keyword_count = sum(1 for kw in SIGNAL_KEYWORDS if kw in text_lower)
        return keyword_count >= 2

    @staticmethod
    def parse_ru_futures_signal(text: str) -> ParsedSignal | None:
        """Parse RU futures signal format (DluxTrading-style).

        Example:
            Нефть
            Br-8.26 Шорт
            Вход 94,12
            Стоп  94,64
            Тейк.   59  пунктов +3%. (93,53)

        Comma decimals, RU direction (Шорт/Лонг), futures ticker code.
        """
        # Direction
        if re.search(r"\bШорт\b", text, re.IGNORECASE):
            action = "sell"
        elif re.search(r"\bЛонг\b", text, re.IGNORECASE):
            action = "buy"
        else:
            return None

        def _num(pattern):
            m = re.search(pattern, text, re.IGNORECASE)
            if not m:
                return None
            try:
                return float(m.group(1).replace(" ", "").replace(",", ".").rstrip("."))
            except ValueError:
                return None

        entry = _num(r"Вход[:\s]+([\d\s.,]+?)[\n\r]")
        if entry is None or entry <= 0:
            return None  # watchlist post without explicit entry — skip
        sl = _num(r"Стоп[:\s]+([\d\s.,]+?)[\n\r]")
        # Take profit: prefer explicit price in parens after Тейк
        tp = _num(r"Тейк[^\n\r]*?\(([\d\s.,]+)\)")

        # Ticker: futures code on the direction line, e.g. "Br-8.26 Шорт"
        tm = re.search(r"([A-Za-z]{1,5}[-–][\d.]+|[A-Z]{2,6})\s+(?:Шорт|Лонг)", text, re.IGNORECASE)
        ticker = tm.group(1).upper().replace("–", "-") if tm else None
        if not ticker or not any(c.isalpha() for c in ticker):
            return None

        return ParsedSignal(ticker=ticker, action=action, entry_price=entry,
                            take_profit=tp, stop_loss=sl)

    @staticmethod
    def parse_crypto_range(text: str) -> ParsedSignal | None:
        """Parse the common crypto range-format signal.

        Example:
            Long enjusdt 2.47-2.50
            Target 2.54-2.61-2.74+
            Stop loss- 2.4499
            Lev- 5x

        Takes first of entry range, first target as TP, the stop as SL.
        Requires all three (entry, target, stop) to avoid promo false positives.
        """
        # Direction + ticker + entry (first of an optional range)
        m = re.search(
            r"\b(Long|Short|Buy|Sell)\s+#?([A-Za-z]{2,12}(?:USDT|USD|BTC|PERP)?)\s+(?:@|at|entry[:\s]*)?([\d]+\.?[\d]*)",
            text, re.IGNORECASE,
        )
        if not m:
            return None
        action = "buy" if m.group(1).lower() in ("long", "buy") else "sell"
        ticker = m.group(2).upper()
        if not _is_valid_ticker(ticker):
            return None
        try:
            entry = float(m.group(3))
        except ValueError:
            return None
        if entry <= 0:
            return None

        # First target
        tm = re.search(r"(?:Target|Targets|TP\d?|Take\s*profit)[s:\-\s]*([\d]+\.?[\d]*)", text, re.IGNORECASE)
        # Stop
        sm = re.search(r"(?:Stop\s*loss|Stoploss|Stop|SL)[:\-\s]*([\d]+\.?[\d]*)", text, re.IGNORECASE)
        if not tm or not sm:
            return None  # need a complete signal
        try:
            tp = float(tm.group(1))
            sl = float(sm.group(1))
        except ValueError:
            return None
        if tp <= 0 or sl <= 0:
            return None

        # Direction sanity: buy => tp>entry>sl ; sell => tp<entry<sl
        if action == "buy" and not (tp > entry > sl):
            return None
        if action == "sell" and not (tp < entry < sl):
            return None

        return ParsedSignal(ticker=ticker, action=action, entry_price=entry,
                            take_profit=tp, stop_loss=sl)

    @staticmethod
    def parse_ru_recommendation(text: str) -> ParsedSignal | None:
        """Parse RU analyst-recommendation format (beststocks-style).

        Example:
            Тикер: JBHT
            Рекомендация: Покупать
            Прогнозная цена: $335 (+21%)

        Derives: action from Покупать/Продавать, TP = target price,
        entry = target / (1 + pct/100), SL = default 10% adverse.
        """
        # Must contain a recommendation line
        rec_match = re.search(r"Рекоменд\w*[:\s*]+\**\s*(Покупать|Продавать|Держать)", text, re.IGNORECASE)
        if not rec_match:
            return None

        rec_word = rec_match.group(1).lower()
        if rec_word.startswith("держ"):
            return None  # "Hold" is not actionable
        action = "buy" if rec_word.startswith("покуп") else "sell"

        # Target price + optional percentage: "Прогнозная цена: 596.27 ₽ (+57%)" or "$335 (+21%)"
        price_match = re.search(
            r"Прогнозная\s+цена[:\s*]+\**\s*\$?([\d\s.,]+)\s*[₽$]?\s*\**\s*(?:\(([+\-]?[\d.,]+)\s*%\))?",
            text, re.IGNORECASE,
        )
        if not price_match:
            return None

        try:
            target = float(price_match.group(1).replace(" ", "").replace(",", ".").rstrip("."))
        except ValueError:
            return None
        if target <= 0:
            return None

        pct = None
        if price_match.group(2):
            try:
                pct = float(price_match.group(2).replace(",", "."))
            except ValueError:
                pct = None

        # Extract ticker: "Тикер: XXX" or beststocks URL (/stock/xxx, /rustock/xxx)
        ticker = None
        t_match = re.search(r"Тикер[:\s*]+\**\s*([A-Z]{2,6})", text, re.IGNORECASE)
        if t_match:
            ticker = t_match.group(1).upper()
        else:
            url_match = re.search(r"beststocks\.ru/(?:rustock|stock)/([a-z0-9]+)", text, re.IGNORECASE)
            if url_match:
                ticker = url_match.group(1).upper()
        if not ticker:
            return None

        # Derive entry from target + pct; default SL 10% adverse
        if pct and pct != 0:
            entry = target / (1 + pct / 100) if action == "buy" else target / (1 - pct / 100)
        else:
            entry = target  # no pct → can't derive; use target as reference
        entry = round(entry, 4)

        if action == "buy":
            sl = round(entry * 0.90, 4)
        else:
            sl = round(entry * 1.10, 4)

        return ParsedSignal(
            ticker=ticker,
            action=action,
            entry_price=entry,
            take_profit=round(target, 4),
            stop_loss=sl,
            derived_levels=True,   # entry and stop are ours, not the analyst's
        )

    @staticmethod
    def parse_message(text: str) -> ParsedSignal | None:
        """Parse a Telegram message into a structured signal.

        Tries multiple patterns to handle different channel formats.
        Returns ParsedSignal if parsed successfully, None otherwise.
        """
        if not text or len(text) < 5:
            return None

        # Try RU analyst-recommendation format first (beststocks-style)
        rec = TelegramParser.parse_ru_recommendation(text)
        if rec:
            return rec

        # Try RU futures signal format (DluxTrading-style: Вход/Стоп/Тейк)
        fut = TelegramParser.parse_ru_futures_signal(text)
        if fut:
            return fut

        # Try crypto range format (Long TICKER lo-hi / Target ... / Stop loss ...)
        crange = TelegramParser.parse_crypto_range(text)
        if crange:
            return crange

        for pattern in SIGNAL_PATTERNS:
            match = pattern.search(text)
            if match:
                groups = match.groupdict()

                # Determine action
                action_raw = groups.get("action")
                if not action_raw:
                    # Try to infer from emoji or context
                    if "🟢" in text or "📈" in text or "⬆️" in text:
                        action_raw = "buy"
                    elif "🔴" in text or "📉" in text or "⬇️" in text:
                        action_raw = "sell"
                    else:
                        continue  # Can't determine action

                try:
                    price = _clean_price(groups["price"])
                    if price <= 0:
                        continue

                    ticker = groups["ticker"].upper().strip("#")
                    # Reject order-type / direction / leverage words captured as ticker
                    if not _is_valid_ticker(ticker):
                        continue

                    result = ParsedSignal(
                        ticker=ticker,
                        action=_normalize_action(action_raw),
                        entry_price=price,
                    )

                    if groups.get("tp"):
                        result.take_profit = _clean_price(groups["tp"])
                    if groups.get("sl"):
                        result.stop_loss = _clean_price(groups["sl"])

                    logger.debug(f"Parsed signal: {result}")
                    return result

                except (ValueError, KeyError) as e:
                    logger.debug(f"Failed to parse with pattern: {e}")
                    continue

        return None

    @staticmethod
    def parse_multiple_targets(text: str) -> list[float]:
        """Extract multiple take-profit targets from a message.

        Matches patterns like "TP1: 100, TP2: 110, TP3: 120".
        """
        tp_pattern = re.compile(
            r"(?:TP|Target)\s*\d?\s*[:\s]\s*([\d,.]+)", re.IGNORECASE
        )
        targets = []
        for match in tp_pattern.finditer(text):
            try:
                targets.append(_clean_price(match.group(1)))
            except ValueError:
                continue
        return targets


    @staticmethod
    async def parse_with_llm(text: str, max_attempts: int = 2) -> ParsedSignal | None:
        """Fallback: use an LLM to parse non-standard / Russian signal formats.

        Every outcome is recorded to the metrics ledger with its reason. Before,
        all of these collapsed into a bare `return None`: no key, HTTP error,
        timeout, unparseable response, schema violation, unrecognised ticker, and
        "this is correctly not a signal" were indistinguishable in the log.

        `max_attempts` retries only a *validation* failure — a response that came
        back but did not satisfy `LLMSignal`. HTTP and timeout failures are not
        retried here: the caller's ledger (llm_parse_ledger) grants one attempt
        per message for the whole run, and burning it on a provider outage means
        the message can never be reparsed once the provider recovers.
        """
        import os

        # settings first (.env is loaded there), env var as an override
        from app.config import settings as _s
        from app.services import llm_metrics as _m
        from app.services.llm_signal_schema import JSON_SCHEMA, PROMPT, LLMSignal

        or_key = os.environ.get("OPENROUTER_API_KEY", "") or _s.openrouter_api_key
        model = os.environ.get("LLM_MODEL", "") or _s.llm_model
        prompt = PROMPT.format(text=text)

        if not or_key and not os.environ.get("ANTHROPIC_API_KEY", ""):
            _m.record("parse_with_llm", model or "none", False, "no_api_key", 0)
            return None

        last_note = ""
        for attempt in range(1, max_attempts + 1):
            outcome, parsed, note, ptok, ctok, ms = await TelegramParser._llm_attempt(
                prompt, or_key, model, attempt
            )
            _m.record("parse_with_llm", model, outcome == "parsed", outcome, ms,
                      ptok, ctok, attempt=attempt, note=note)
            if outcome == "parsed":
                return parsed
            last_note = note
            # Only a malformed or invalid answer is worth asking again for.
            if outcome not in ("invalid_json", "schema_invalid", "empty_response"):
                return None

        logger.debug(f"LLM parser gave up after {max_attempts} attempts: {last_note}")
        return None

    @staticmethod
    async def _llm_attempt(prompt: str, or_key: str, model: str, attempt: int):
        """One request. Returns (outcome, ParsedSignal|None, note, ptok, ctok, ms)."""
        import os

        from app.services import llm_metrics as _m
        from app.services.llm_signal_schema import JSON_SCHEMA, LLMSignal

        from pydantic import ValidationError

        ptok = ctok = 0
        with _m.timed() as t:
            try:
                if or_key:
                    async with httpx.AsyncClient(timeout=15) as client:
                        resp = await client.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers={
                                "Authorization": f"Bearer {or_key}",
                                "Content-Type": "application/json",
                                "HTTP-Referer": "https://winextraflow.com",
                                "X-Title": "WinExtraFlow",
                            },
                            json={
                                "model": model,
                                # Reasoning models (e.g. gpt-oss) spend tokens on a
                                # thinking pass first — a small budget truncates
                                # them before any answer is produced.
                                "max_tokens": 900,
                                "temperature": 0.1,
                                # Constrains generation where the provider supports
                                # it. Support varies per model on OpenRouter and a
                                # schema cannot express the cross-field rules, so
                                # LLMSignal still validates the result.
                                "response_format": JSON_SCHEMA,
                                "messages": [{"role": "user", "content": prompt}],
                            },
                        )
                    body = {}
                    try:
                        body = resp.json()
                    except ValueError:
                        pass
                    ptok, ctok = _m.usage_from_response(body)
                    if resp.status_code != 200:
                        return ("http_error", None,
                                f"{resp.status_code} {resp.text[:120]}",
                                ptok, ctok, t["elapsed_ms"]())
                    msg = (body.get("choices") or [{}])[0].get("message", {}) or {}
                    # Reasoning models may leave `content` empty and put the answer
                    # in `reasoning`; accept either.
                    content = (msg.get("content") or msg.get("reasoning") or "").strip()
                else:
                    # Backward-compat: direct Anthropic.
                    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
                    async with httpx.AsyncClient(timeout=15) as client:
                        resp = await client.post(
                            "https://api.anthropic.com/v1/messages",
                            headers={
                                "x-api-key": api_key,
                                "anthropic-version": "2023-06-01",
                                "content-type": "application/json",
                            },
                            json={
                                "model": "claude-sonnet-4-20250514",
                                # Was 200, which truncated the answer on any long
                                # message while the OpenRouter path allowed 900.
                                "max_tokens": 900,
                                "messages": [{"role": "user", "content": prompt}],
                            },
                        )
                    body = {}
                    try:
                        body = resp.json()
                    except ValueError:
                        pass
                    ptok, ctok = _m.usage_from_response(body)
                    if resp.status_code != 200:
                        return ("http_error", None, str(resp.status_code),
                                ptok, ctok, t["elapsed_ms"]())
                    content = (body.get("content") or [{}])[0].get("text", "").strip()

                if not content:
                    return ("empty_response", None, "no content and no reasoning",
                            ptok, ctok, t["elapsed_ms"]())

                data = _extract_json(content)
                if data is None:
                    return ("invalid_json", None, content[:120],
                            ptok, ctok, t["elapsed_ms"]())

                # The model declining is a correct outcome, not a failure. It is
                # counted separately so "the parser is broken" and "these messages
                # were not signals" stop looking the same in the log.
                if data.get("not_a_signal") is True or "error" in data:
                    return ("not_a_signal", None, "", ptok, ctok, t["elapsed_ms"]())

                try:
                    sig = LLMSignal(**{k: data.get(k) for k in
                                       ("ticker", "action", "entry_price",
                                        "take_profit", "stop_loss")})
                except ValidationError as e:
                    first = e.errors()[0]
                    return ("schema_invalid", None,
                            f"{'.'.join(str(x) for x in first['loc'])}: "
                            f"{first['msg']}",
                            ptok, ctok, t["elapsed_ms"]())

                ticker = _resolve_ticker(sig.ticker)
                if not _is_valid_ticker(ticker):
                    return ("rejected_ticker", None, sig.ticker,
                            ptok, ctok, t["elapsed_ms"]())

                return ("parsed", ParsedSignal(
                    ticker=ticker,
                    action=_normalize_action(sig.action),
                    entry_price=sig.entry_price,
                    take_profit=sig.take_profit,
                    stop_loss=sig.stop_loss,
                ), "", ptok, ctok, t["elapsed_ms"]())

            except httpx.TimeoutException:
                return ("timeout", None, "15s", ptok, ctok, t["elapsed_ms"]())
            except Exception as e:
                return ("exception", None, f"{type(e).__name__}: {e}",
                        ptok, ctok, t["elapsed_ms"]())


def _extract_json(content: str) -> dict | None:
    """Pull the answer object out of a response that may be wrapped in prose.

    Needed because `response_format` is honoured by only some OpenRouter models;
    the rest still return a JSON object inside an explanation, and reasoning
    models may show several draft objects before the final one. The last block
    that looks like an answer wins.
    """
    if content.startswith("{"):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
    for block in reversed(re.findall(r"\{[^{}]*\}", content, re.DOTALL)):
        try:
            cand = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(cand, dict) and (
            "ticker" in cand or "error" in cand or "not_a_signal" in cand
        ):
            return cand
    return None


telegram_parser = TelegramParser()
