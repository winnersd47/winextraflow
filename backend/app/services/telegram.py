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

# Keywords that indicate a trading signal message
SIGNAL_KEYWORDS = [
    "buy", "sell", "long", "short", "entry", "take profit",
    "stop loss", "tp", "sl", "target", "signal",
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
    def parse_message(text: str) -> ParsedSignal | None:
        """Parse a Telegram message into a structured signal.

        Tries multiple patterns to handle different channel formats.
        Returns ParsedSignal if parsed successfully, None otherwise.
        """
        if not text or len(text) < 5:
            return None

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

                    result = ParsedSignal(
                        ticker=groups["ticker"].upper().strip("#"),
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
        """Fallback: use Claude API to parse non-standard signal formats.

        Requires ANTHROPIC_API_KEY in environment. Returns None if unavailable.
        """
        import os
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return None

        prompt = f"""Extract trading signal from this message. Return JSON only, no explanation.
If this is NOT a trading signal, return {{"error": "not a signal"}}.

Required fields: ticker (string), action ("buy" or "sell"), entry_price (number)
Optional fields: take_profit (number or null), stop_loss (number or null)

Message:
{text}

JSON:"""

        try:
            async with httpx.AsyncClient(timeout=10) as client:
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
                    # Try to find JSON in response
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    if start >= 0 and end > start:
                        data = json.loads(content[start:end])
                    else:
                        return None

                if "error" in data:
                    return None

                return ParsedSignal(
                    ticker=data["ticker"].upper(),
                    action=_normalize_action(data["action"]),
                    entry_price=float(data["entry_price"]),
                    take_profit=float(data["take_profit"]) if data.get("take_profit") else None,
                    stop_loss=float(data["stop_loss"]) if data.get("stop_loss") else None,
                )
        except Exception as e:
            logger.debug(f"LLM parser error: {e}")
            return None


telegram_parser = TelegramParser()
