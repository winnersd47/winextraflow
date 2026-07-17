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

# Words that are NOT tickers (order types, common false-positives)
NON_TICKER_WORDS = {
    "LIMIT", "STOP", "MARKET", "BUY", "SELL", "LONG", "SHORT",
    "TP", "SL", "ENTRY", "PRICE", "TARGET", "NOW", "AT",
}

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
                    # Reject order-type words captured as ticker (e.g. "SELL LIMIT")
                    if ticker in NON_TICKER_WORDS or len(ticker) < 2:
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
    async def parse_with_llm(text: str) -> ParsedSignal | None:
        """Fallback: use an LLM to parse non-standard / Russian signal formats.

        Uses OpenRouter (OpenAI-compatible) with a free model by default.
        Requires OPENROUTER_API_KEY in environment. Returns None if unavailable.
        Falls back to ANTHROPIC_API_KEY (direct Claude) for backward compat.
        """
        import os
        or_key = os.environ.get("OPENROUTER_API_KEY", "")
        model = os.environ.get("LLM_MODEL", "deepseek/deepseek-chat:free")

        prompt = f"""Extract a trading signal from this message (may be Russian or English).
Return JSON only, no explanation. If this is NOT an actionable trading signal
(news, analytics, opinion), return {{"error": "not a signal"}}.

Rules:
- action: "buy" for покупка/лонг/buy/long, "sell" for продажа/шорт/sell/short
- ticker: the instrument symbol (e.g. SBER, BTCUSDT, EURUSD, XAUUSD). Not an order type like "LIMIT".
- entry_price: entry/цена входа as a number
- take_profit: TP/цель/тейк (number or null)
- stop_loss: SL/стоп (number or null)

Required: ticker, action, entry_price. Optional: take_profit, stop_loss.

Message:
{text}

JSON:"""

        try:
            if or_key:
                # OpenRouter (OpenAI-compatible)
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
                            "max_tokens": 200,
                            "temperature": 0.1,
                            "messages": [{"role": "user", "content": prompt}],
                        },
                    )
                    if resp.status_code != 200:
                        logger.debug(f"LLM parser HTTP error: {resp.status_code} {resp.text[:200]}")
                        return None
                    content = resp.json()["choices"][0]["message"]["content"].strip()
            else:
                # Backward-compat: direct Anthropic
                api_key = os.environ.get("ANTHROPIC_API_KEY", "")
                if not api_key:
                    return None
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
                            "max_tokens": 200,
                            "messages": [{"role": "user", "content": prompt}],
                        },
                    )
                    if resp.status_code != 200:
                        logger.debug(f"LLM parser HTTP error: {resp.status_code}")
                        return None
                    content = resp.json()["content"][0]["text"].strip()

            # Extract JSON from response
            if content.startswith("{"):
                data = json.loads(content)
            else:
                start = content.find("{")
                end = content.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(content[start:end])
                else:
                    return None

            if "error" in data or not data.get("ticker") or data.get("entry_price") is None:
                return None

            return ParsedSignal(
                ticker=str(data["ticker"]).upper(),
                action=_normalize_action(data["action"]),
                entry_price=float(data["entry_price"]),
                take_profit=float(data["take_profit"]) if data.get("take_profit") else None,
                stop_loss=float(data["stop_loss"]) if data.get("stop_loss") else None,
            )
        except Exception as e:
            logger.debug(f"LLM parser error: {e}")
            return None


telegram_parser = TelegramParser()
