"""Remember which messages were already sent to the LLM parser.

The backfill runs every 30 minutes over a 48-hour message window, so it re-reads
the same posts about 48 times before they age out. Without a ledger, one message the
regex cannot parse would be sent to the LLM on every single run — 48 calls for one
message, against a free tier that allows 50 requests a day in total.

So each (channel, message) pair is tried once. A message that failed to parse will
not be retried: the failure is a property of the text, not of the moment, and the
regex parsers are tried first anyway.

The file lives next to the other cron state (monitored_channels.json and friends)
and is pruned to the message window, so it cannot grow without bound.
"""

import json
import logging
import os
import time

logger = logging.getLogger(__name__)

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEDGER_PATH = os.path.join(_BASE, "llm_parse_ledger.json")

# Slightly longer than the backfill's message window, so an entry outlives the
# message that created it and cannot come back for a second attempt.
KEEP_HOURS = 72


class ParseLedger:
    """Attempt ledger with a per-run call budget."""

    def __init__(self, path: str = LEDGER_PATH, max_per_run: int = 0):
        self.path = path
        self.max_per_run = max_per_run
        self.used = 0
        self.skipped_seen = 0
        self.skipped_budget = 0
        self._attempts: dict[str, float] = {}
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            self._attempts = {k: float(v) for k, v in (data.get("attempts") or {}).items()}
        except (OSError, ValueError, TypeError):
            self._attempts = {}
        cutoff = time.time() - KEEP_HOURS * 3600
        before = len(self._attempts)
        self._attempts = {k: v for k, v in self._attempts.items() if v >= cutoff}
        if before != len(self._attempts):
            logger.debug(f"Parse ledger pruned {before - len(self._attempts)} old entries")

    def save(self) -> None:
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"attempts": self._attempts}, f)
            os.replace(tmp, self.path)          # atomic: a killed cron run cannot
        except OSError as e:                    # leave a truncated ledger behind
            logger.warning(f"Parse ledger save failed: {e}")

    @staticmethod
    def key(channel: str, message_id) -> str:
        return f"{channel}:{message_id}"

    def budget_left(self) -> int:
        if not self.max_per_run:
            return 0
        return max(0, self.max_per_run - self.used)

    def should_try(self, channel: str, message_id) -> bool:
        """True if this message has never been sent to the LLM and budget remains."""
        if self.key(channel, message_id) in self._attempts:
            self.skipped_seen += 1
            return False
        if self.budget_left() <= 0:
            self.skipped_budget += 1
            return False
        return True

    def mark(self, channel: str, message_id) -> None:
        """Record the attempt — whether or not it produced a signal."""
        self._attempts[self.key(channel, message_id)] = time.time()
        self.used += 1

    def summary(self) -> str:
        parts = [f"LLM-парсер: вызовов {self.used}/{self.max_per_run}"]
        if self.skipped_seen:
            parts.append(f"уже пробовали {self.skipped_seen}")
        if self.skipped_budget:
            parts.append(f"не хватило бюджета {self.skipped_budget}")
        parts.append(f"в журнале {len(self._attempts)}")
        return ", ".join(parts)
