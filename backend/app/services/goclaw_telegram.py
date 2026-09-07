"""GoClaw Telegram Adapter — routes Telegram signals through GoClaw AI Agent Gateway.

GoClaw sits in front of the Telegram Bot API and enables multi-agent orchestration:
message queuing, rate-limit pooling, A/B routing, and audit logging across agents.

Usage:
    from app.services.goclaw_telegram import goclaw_telegram_adapter

    if goclaw_telegram_adapter.enabled:
        ok = await goclaw_telegram_adapter.broadcast_via_goclaw(text, channel_ids)
"""

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_SEND_PATH = "/api/v1/channels/telegram/send"
_REQUEST_TIMEOUT = 30  # seconds


class GoClawTelegramAdapter:
    """Send Telegram messages via the GoClaw AI Agent Gateway REST API.

    Falls back gracefully when GOCLAW_URL or GOCLAW_TOKEN are not configured
    (returns False / ``enabled`` is False) so the caller can transparently
    fall through to a direct Bot API call.
    """

    # ─── Configuration ──────────────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        """True only when both GOCLAW_URL and GOCLAW_TOKEN are non-empty."""
        return bool(settings.goclaw_url and settings.goclaw_token)

    @property
    def _base_url(self) -> str:
        return settings.goclaw_url.rstrip("/")

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.goclaw_token}",
            "Content-Type": "application/json",
        }

    # ─── Core send ──────────────────────────────────────────────────────────

    async def _send_one(self, client: httpx.AsyncClient, chat_id: str, text: str) -> bool:
        """POST a single message to GoClaw.  Returns True on HTTP 2xx."""
        url = f"{self._base_url}{_SEND_PATH}"
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        try:
            resp = await client.post(url, json=payload, headers=self._headers)
            if resp.is_success:
                logger.debug("GoClaw → chat_id=%s: OK (%s)", chat_id, resp.status_code)
                return True
            logger.warning(
                "GoClaw send failed: chat_id=%s status=%s body=%s",
                chat_id,
                resp.status_code,
                resp.text[:200],
            )
            return False
        except httpx.TimeoutException:
            logger.error("GoClaw request timed out (chat_id=%s, url=%s)", chat_id, url)
            return False
        except httpx.RequestError as exc:
            logger.error("GoClaw request error (chat_id=%s): %s", chat_id, exc)
            return False

    async def broadcast_via_goclaw(self, message: str, channel_ids: list[str]) -> bool:
        """Broadcast *message* to every chat_id in *channel_ids* through GoClaw.

        Args:
            message:     HTML-formatted text (same as Telegram Bot API).
            channel_ids: One or more Telegram chat/channel IDs (as strings).

        Returns:
            True  — every delivery succeeded.
            False — adapter not enabled, empty list, or at least one delivery failed.
        """
        if not self.enabled:
            logger.debug("GoClaw adapter is not configured; broadcast skipped.")
            return False

        if not channel_ids:
            logger.debug("GoClaw broadcast called with empty channel_ids list.")
            return False

        results: list[bool] = []
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            for chat_id in channel_ids:
                ok = await self._send_one(client, chat_id, message)
                results.append(ok)

        success_count = sum(results)
        total = len(results)
        if success_count == total:
            logger.info("GoClaw broadcast: %d/%d channels OK", success_count, total)
            return True

        logger.warning(
            "GoClaw broadcast: %d/%d channels succeeded; falling back to direct Bot API.",
            success_count,
            total,
        )
        return False


# Module-level singleton — import this in telegram_bot.py
goclaw_telegram_adapter = GoClawTelegramAdapter()
