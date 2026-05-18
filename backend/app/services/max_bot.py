"""MAX Messenger Bot — notifications and signal broadcasting.

MAX is Russia's national messenger by VK (dev.max.ru).
API base: https://platform-api.max.ru
Auth: Authorization header with bot token.
Rate limit: 30 req/sec.

Features mirror Telegram bot:
- /start — link MAX account to WinExtraFlow
- Signal broadcast to VIP (instant) + Free (delayed) channels
- Personal notifications for linked users
"""

import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.user import User

logger = logging.getLogger(__name__)

MAX_API = "https://platform-api.max.ru"


class MaxBot:
    """MAX Messenger Bot using platform-api.max.ru."""

    def __init__(self) -> None:
        self.token = settings.max_bot_token
        self._running = False
        self._marker: int | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    async def _call(self, method: str, *, http_method: str = "GET", json: dict | None = None) -> dict | None:
        if not self.enabled:
            return None
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                headers = {"Authorization": self.token}
                if http_method == "POST":
                    resp = await client.post(f"{MAX_API}/{method}", headers=headers, json=json or {})
                else:
                    resp = await client.get(f"{MAX_API}/{method}", headers=headers, params=json)
                data = resp.json()
                if resp.status_code >= 400:
                    logger.error(f"MAX API error: {resp.status_code} {data}")
                return data
        except Exception as e:
            logger.error(f"MAX API call failed: {e}")
            return None

    async def send_message(self, chat_id: str, text: str) -> dict | None:
        """Send a message to a MAX chat/channel."""
        return await self._call("messages", http_method="POST", json={
            "chat_id": chat_id,
            "body": {"text": text},
        })

    # ─── Signal Formatting ───────────────────────────────────

    def _format_vip_signal(self, ticker: str, action: str, price: float, confidence: float | None,
                           tp: float | None = None, sl: float | None = None) -> str:
        arrow = "+" if action == "buy" else "-"
        conf_str = f"\nAI качество: {confidence:.0%}" if confidence else ""
        tp_str = f"\nTP: {tp:,.2f}" if tp else ""
        sl_str = f"\nSL: {sl:,.2f}" if sl else ""
        return (
            f"{arrow} {action.upper()} {ticker}\n"
            f"Вход: {price:,.2f}{tp_str}{sl_str}{conf_str}\n"
            f"\nWinExtraFlow: {settings.frontend_url}/dashboard"
        )

    def _format_free_signal(self, ticker: str, action: str, confidence: float | None) -> str:
        arrow = "+" if action == "buy" else "-"
        quality = ""
        if confidence and confidence >= 0.7:
            quality = " | Отличный"
        elif confidence and confidence >= 0.5:
            quality = " | Хороший"
        return (
            f"{arrow} {action.upper()} {ticker}{quality}\n"
            f"\nЦена входа, TP и SL — в VIP-канале"
            f"\nПремиум: {settings.frontend_url}/dashboard/store"
        )

    # ─── Broadcast ───────────────────────────────────────────

    async def broadcast_signal(self, ticker: str, action: str, price: float, confidence: float | None,
                               tp: float | None = None, sl: float | None = None) -> None:
        """Broadcast signal to MAX VIP (instant) + Free (delayed) channels."""

        # 1. VIP channel — instant
        if settings.max_vip_channel_id:
            vip_text = self._format_vip_signal(ticker, action, price, confidence, tp, sl)
            await self.send_message(settings.max_vip_channel_id, vip_text)
            logger.info(f"MAX VIP broadcast: {action} {ticker}")

        # 2. Free channel — delayed
        if settings.max_free_channel_id:
            delay = settings.telegram_free_delay_minutes * 60  # Same delay as Telegram
            free_text = self._format_free_signal(ticker, action, confidence)

            async def _delayed():
                await asyncio.sleep(delay)
                await self.send_message(settings.max_free_channel_id, free_text)
                logger.info(f"MAX Free broadcast (delayed): {action} {ticker}")

            asyncio.create_task(_delayed())

        # 3. Personal notifications to users with MAX linked
        async with async_session() as db:
            result = await db.execute(
                select(User).where(
                    User.max_chat_id.isnot(None),
                    User.telegram_notifications == True,  # Reuse notification preference
                    User.is_active == True,
                )
            )
            users = result.scalars().all()
            for user in users:
                if user.max_chat_id:
                    arrow = "+" if action == "buy" else "-"
                    conf = f" | AI: {confidence:.0%}" if confidence else ""
                    text = f"{arrow} {action.upper()} {ticker}\nВход: {price:,.2f}{conf}"
                    await self.send_message(user.max_chat_id, text)
                    await asyncio.sleep(0.04)  # Rate limit: 30 req/sec
            if users:
                logger.info(f"MAX personal broadcast: {action} {ticker} to {len(users)} users")

    # ─── Polling ─────────────────────────────────────────────

    async def start_polling(self) -> None:
        """Poll for updates (commands from users)."""
        if not self.enabled:
            logger.info("MAX bot not configured, skipping")
            return

        self._running = True
        logger.info("MAX bot polling started")

        while self._running:
            try:
                params = {"timeout": 30, "types": "message_created"}
                if self._marker:
                    params["marker"] = self._marker
                data = await self._call("updates", json=params)
                if not data or "updates" not in data:
                    await asyncio.sleep(1)
                    continue

                self._marker = data.get("marker")
                for update in data.get("updates", []):
                    await self._handle_update(update)

            except Exception as e:
                logger.error(f"MAX polling error: {e}")
                await asyncio.sleep(5)

    async def stop_polling(self) -> None:
        self._running = False

    async def _handle_update(self, update: dict) -> None:
        """Process a single MAX update."""
        body = update.get("body", {})
        text = body.get("text", "").strip()
        chat_id = str(update.get("message", {}).get("recipient", {}).get("chat_id", ""))
        sender = update.get("message", {}).get("sender", {})
        sender_name = sender.get("name", "")

        if not text or not chat_id:
            return

        if text.startswith("/start"):
            await self._cmd_start(chat_id, sender_name, text)
        elif text == "/signals":
            await self._cmd_signals(chat_id)
        elif text == "/help":
            await self._cmd_help(chat_id)
        else:
            await self._cmd_help(chat_id)

    async def _cmd_start(self, chat_id: str, sender_name: str, text: str) -> None:
        parts = text.split()
        link_code = parts[1] if len(parts) > 1 else None

        if link_code and link_code.startswith("link_"):
            wef_username = link_code[5:]
            async with async_session() as db:
                user = (await db.execute(
                    select(User).where(User.username == wef_username)
                )).scalar_one_or_none()
                if user:
                    user.max_chat_id = chat_id
                    await db.commit()
                    await self.send_message(chat_id,
                        f"Аккаунт {wef_username} привязан к MAX!\n"
                        f"Вы будете получать уведомления о сигналах здесь.")
                    return

        await self.send_message(chat_id,
            "WinExtraFlow — торговые сигналы с AI-аналитикой.\n\n"
            f"Привяжите аккаунт: откройте Профиль на {settings.frontend_url}/dashboard/profile "
            f"и нажмите 'Привязать MAX'.\n\n"
            "/signals — последние сигналы\n"
            "/help — справка")

    async def _cmd_signals(self, chat_id: str) -> None:
        async with async_session() as db:
            from app.models.signal import Signal
            result = await db.execute(
                select(Signal).order_by(Signal.created_at.desc()).limit(5)
            )
            signals = result.scalars().all()
            if not signals:
                await self.send_message(chat_id, "Пока нет сигналов.")
                return

            lines = ["Последние 5 сигналов:\n"]
            for s in signals:
                arrow = "+" if s.action.value == "buy" else "-"
                conf = f" AI:{s.ai_confidence:.0%}" if s.ai_confidence else ""
                lines.append(f"{arrow} {s.action.value.upper()} {s.ticker} @ {s.entry_price:,.2f}{conf}")
            await self.send_message(chat_id, "\n".join(lines))

    async def _cmd_help(self, chat_id: str) -> None:
        await self.send_message(chat_id,
            "WinExtraFlow — команды:\n\n"
            "/start — привязать аккаунт\n"
            "/signals — последние сигналы\n"
            "/help — эта справка\n"
            f"\nПлатформа: {settings.frontend_url}")


max_bot = MaxBot()
