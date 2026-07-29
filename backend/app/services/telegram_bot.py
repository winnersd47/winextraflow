"""Telegram Bot — notifications and commands for WinExtraFlow users.

Bot features:
- /start — link Telegram account to WinExtraFlow
- /signals — latest signals
- /premium — premium status
- /stop — disable notifications
- Push notifications for: new signals, order fills, achievements
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

BOT_API = "https://api.telegram.org/bot{token}"


class TelegramBot:
    """Lightweight Telegram Bot using raw HTTP API (no external bot library needed)."""

    def __init__(self):
        self.token = settings.telegram_bot_token
        self.base_url = BOT_API.format(token=self.token) if self.token else ""
        self._running = False
        self._offset = 0

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    async def _call(self, method: str, **params) -> dict | None:
        if not self.enabled:
            return None
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(f"{self.base_url}/{method}", json=params)
                data = resp.json()
                if not data.get("ok"):
                    logger.error(f"Bot API error: {data}")
                return data
        except Exception as e:
            logger.error(f"Bot API call failed: {e}")
            return None

    async def send_message(self, chat_id: str, text: str, parse_mode: str = "HTML"):
        """Send a message to a Telegram chat."""
        return await self._call("sendMessage", chat_id=chat_id, text=text, parse_mode=parse_mode)

    async def send_to_channel(self, channel_id: str, text: str, parse_mode: str = "HTML"):
        """Send a message to a Telegram channel (for content publishing)."""
        return await self._call("sendMessage", chat_id=channel_id, text=text, parse_mode=parse_mode, disable_web_page_preview=False, disable_notification=True)

    async def send_raw_message(self, text: str):
        """Send to the free channel (for digest/announcements)."""
        if self.free_channel_id:
            return await self.send_to_channel(self.free_channel_id, text)

    # ─── Notification Methods ─────────────────────────────────

    async def notify_signal(self, user: User, ticker: str, action: str, price: float, confidence: float | None):
        """Send new signal notification."""
        if not user.telegram_chat_id or not user.telegram_notifications:
            return
        emoji = "🟢" if action == "buy" else "🔴"
        conf = f" | AI: {confidence:.0%}" if confidence else ""
        text = (
            f"{emoji} <b>{action.upper()} {ticker}</b>\n"
            f"Entry: ${price:,.2f}{conf}\n"
            f"\n<a href='{settings.frontend_url}/dashboard'>Open Dashboard</a>"
        )
        await self.send_message(user.telegram_chat_id, text)

    async def notify_order(self, user: User, symbol: str, side: str, status: str, price: float | None):
        """Send order execution notification."""
        if not user.telegram_chat_id or not user.telegram_notifications:
            return
        emoji = "✅" if status == "filled" else "❌"
        price_str = f" @ ${price:,.2f}" if price else ""
        text = f"{emoji} Order <b>{status}</b>: {side.upper()} {symbol}{price_str}"
        await self.send_message(user.telegram_chat_id, text)

    async def notify_achievement(self, user: User, name: str, icon: str, xp: int):
        """Send achievement unlock notification."""
        if not user.telegram_chat_id or not user.telegram_notifications:
            return
        text = f"🏆 Achievement unlocked!\n\n{icon} <b>{name}</b>\n+{xp} XP"
        await self.send_message(user.telegram_chat_id, text)

    async def notify_premium(self, user: User, days: int):
        """Send premium activation notification."""
        if not user.telegram_chat_id or not user.telegram_notifications:
            return
        text = f"💎 <b>Premium Activated!</b>\n\nYou received {days} days of Premium access."
        await self.send_message(user.telegram_chat_id, text)

    # ─── Channel Broadcast (VIP + Free) ─────────────────────

    def _format_vip_signal(self, ticker: str, action: str, price: float, confidence: float | None,
                           tp: float | None = None, sl: float | None = None,
                           expert: dict | None = None) -> str:
        """Full VIP signal with expert analysis."""
        arrow = "🟢" if action == "buy" else "🔴"
        wef = f"{confidence:.0%}" if confidence else "N/A"

        # WEF tier
        if confidence and confidence >= 0.8:
            tier = "STRONG"
        elif confidence and confidence >= 0.6:
            tier = "GOOD"
        elif confidence and confidence >= 0.5:
            tier = "AVERAGE"
        else:
            tier = "WEAK"

        # R:R ratio
        rr = ""
        if tp and sl and price > 0:
            reward = abs(tp - price)
            risk = abs(price - sl)
            if risk > 0:
                rr = f"\nR:R = 1:{reward/risk:.1f}"

        lines = [
            f"{arrow} <b>{action.upper()} {ticker}</b>  |  WEF {wef} ({tier})",
            f"",
            f"Вход: <b>{price:,.2f}</b>",
        ]
        if tp:
            lines.append(f"TP: <b>{tp:,.2f}</b>")
        if sl:
            lines.append(f"SL: <b>{sl:,.2f}</b>")
        if rr:
            lines.append(rr)

        # Expert analysis (if available)
        if expert:
            lines.append("")
            lines.append("--- Expert Analysis ---")
            verdict = expert.get("verdict", "")
            if verdict:
                lines.append(f"Вердикт: <b>{verdict}</b>")
            ev = expert.get("ev_per_trade_pct")
            if ev is not None:
                lines.append(f"EV: {ev:.2f}% на сделку")
            pf = expert.get("profit_factor")
            if pf:
                lines.append(f"Profit Factor: {pf}")
            kelly = expert.get("kelly_half_pct")
            if kelly:
                lines.append(f"Kelly (half): {kelly}%")
            strategy = expert.get("regime_strategy")
            if strategy:
                lines.append(f"Стратегия: {strategy}")
            pyramid = expert.get("pyramid_levels", 0)
            if pyramid:
                lines.append(f"Пирамидинг: {pyramid} уровня")
            edge = expert.get("edge_pct")
            if edge:
                lines.append(f"Edge: {edge}%")

        lines.append("")
        lines.append(f"<a href='{settings.frontend_url}/dashboard'>Открыть платформу</a>")

        return "\n".join(lines)

    def _format_free_signal(self, ticker: str, action: str, confidence: float | None) -> str:
        """Shortened signal for free channel (no price, no TP/SL)."""
        arrow = "🟢" if action == "buy" else "🔴"
        quality = ""
        if confidence and confidence >= 0.7:
            quality = " | Отличный"
        elif confidence and confidence >= 0.5:
            quality = " | Хороший"
        return (
            f"{arrow} <b>{action.upper()} {ticker}</b>{quality}\n"
            f"\n💎 Цена входа, TP и SL — в VIP-канале"
            f"\n\n💎 <b>Сигналы с WEF 70%+ — только в VIP</b>"
            f"\nСамые сильные сетапы в общий канал не публикуются."
            f"\n📊 <a href='https://winextraflow.pages.dev'>Подключить Premium</a>"
        )

    async def broadcast_signal(self, ticker: str, action: str, price: float, confidence: float | None,
                               tp: float | None = None, sl: float | None = None,
                               expert: dict | None = None, signal_id: str | None = None):
        """Broadcast signal to VIP (instant) + Free (delayed) channels + personal notifications.

        VIP: only WEF >= 50%, full expert analysis
        Free: delayed, no prices, teaser only
        """

        # 1. VIP channel — instant, full expert details (WEF >= 50% only)
        if settings.telegram_vip_channel_id and (not confidence or confidence >= 0.5):
            vip_text = self._format_vip_signal(ticker, action, price, confidence, tp, sl, expert)
            await self.send_message(settings.telegram_vip_channel_id, vip_text)
            logger.info(f"VIP broadcast: {action} {ticker} WEF={confidence} → VIP")

            # Forward to AI Growth Club if high quality
            if confidence and confidence >= 0.7 and settings.telegram_growth_group_id:
                try:
                    tagged = vip_text + "\n\n#repost #aigc #winextraflow"
                    msg = await self.send_to_channel(settings.telegram_free_channel_id or settings.telegram_vip_channel_id, tagged)
                    if msg and msg.get("result", {}).get("message_id") and settings.telegram_growth_group_id:
                        await self._call("forwardMessage",
                            chat_id=settings.telegram_growth_group_id,
                            from_chat_id=settings.telegram_free_channel_id or settings.telegram_vip_channel_id,
                            message_id=msg["result"]["message_id"])
                except Exception as e:
                    logger.warning(f"Growth Club forward failed: {e}")

        # 2. Free channel — delayed, no prices
        if settings.telegram_free_channel_id:
            delay = settings.telegram_free_delay_minutes * 60
            free_text = self._format_free_signal(ticker, action, confidence)

            async def _delayed_free():
                await asyncio.sleep(delay)
                await self.send_message(settings.telegram_free_channel_id, free_text)
                logger.info(f"Free broadcast (delayed {settings.telegram_free_delay_minutes}m): {action} {ticker}")

            asyncio.create_task(_delayed_free())

        # 3. Personal notifications to linked users
        await self.broadcast_free_and_personal(ticker, action, price, confidence, skip_free=True)

    async def broadcast_free_and_personal(self, ticker: str, action: str, price: float,
                                          confidence: float | None, skip_free: bool = False):
        """Send delayed free-channel teaser + personal notifications (no VIP).

        Used by the connected-signals pipeline whose VIP message is the rich
        chart card (sent separately), so this avoids a duplicate VIP post.
        """
        # Free channel — delayed teaser, no prices
        if not skip_free and settings.telegram_free_channel_id:
            delay = settings.telegram_free_delay_minutes * 60
            free_text = self._format_free_signal(ticker, action, confidence)

            async def _delayed_free():
                await asyncio.sleep(delay)
                await self.send_message(settings.telegram_free_channel_id, free_text)
                logger.info(f"Free broadcast (delayed {settings.telegram_free_delay_minutes}m): {action} {ticker}")

            asyncio.create_task(_delayed_free())

        # Personal notifications to linked users
        async with async_session() as db:
            result = await db.execute(
                select(User).where(
                    User.telegram_chat_id.isnot(None),
                    User.telegram_notifications == True,
                    User.is_active == True,
                )
            )
            users = result.scalars().all()
            for user in users:
                await self.notify_signal(user, ticker, action, price, confidence)
                await asyncio.sleep(0.05)
            if users:
                logger.info(f"Personal broadcast: {action} {ticker} to {len(users)} users")

    # ─── Polling (updates processing) ─────────────────────────

    async def start_polling(self):
        """Start polling for bot updates (commands)."""
        if not self.enabled:
            logger.info("Telegram bot not configured, skipping")
            return

        self._running = True
        logger.info("Telegram bot polling started")

        while self._running:
            try:
                data = await self._call("getUpdates", offset=self._offset, timeout=30)
                if not data or not data.get("result"):
                    await asyncio.sleep(1)
                    continue

                for update in data["result"]:
                    self._offset = update["update_id"] + 1
                    await self._handle_update(update)

            except Exception as e:
                logger.error(f"Bot polling error: {e}")
                await asyncio.sleep(5)

    async def stop_polling(self):
        self._running = False

    async def _handle_update(self, update: dict):
        """Process a single bot update."""
        message = update.get("message")
        if not message or not message.get("text"):
            return

        chat_id = str(message["chat"]["id"])
        text = message["text"].strip()
        username = message["from"].get("username", "")

        if text == "/start" or text.startswith("/start "):
            await self._cmd_start(chat_id, username, text)
        elif text == "/signals":
            await self._cmd_signals(chat_id)
        elif text == "/premium":
            await self._cmd_premium(chat_id)
        elif text == "/stop":
            await self._cmd_stop(chat_id)
        elif text == "/help":
            await self._cmd_help(chat_id)
        else:
            await self._cmd_help(chat_id)

    async def _cmd_start(self, chat_id: str, tg_username: str, text: str):
        """Link Telegram to WinExtraFlow account."""
        # Check if link code provided: /start link_<username>
        parts = text.split()
        link_code = parts[1] if len(parts) > 1 else None

        async with async_session() as db:
            if link_code and link_code.startswith("link_"):
                wef_username = link_code[5:]
                user = (await db.execute(
                    select(User).where(User.username == wef_username)
                )).scalar_one_or_none()
                if user:
                    user.telegram_chat_id = chat_id
                    user.telegram_notifications = True
                    await db.commit()
                    await self.send_message(chat_id,
                        f"✅ <b>Account linked!</b>\n\n"
                        f"Welcome, {user.username}! You'll now receive trading signal notifications.\n\n"
                        f"Commands:\n/signals — Latest signals\n/premium — Premium status\n/stop — Disable notifications\n/help — Help"
                    )
                    return
                else:
                    await self.send_message(chat_id, "❌ User not found. Check your link.")
                    return

            # No code — check if already linked
            existing = (await db.execute(
                select(User).where(User.telegram_chat_id == chat_id)
            )).scalar_one_or_none()
            if existing:
                await self.send_message(chat_id,
                    f"👋 Welcome back, <b>{existing.username}</b>!\n\n"
                    f"Your account is linked. Use /help to see commands."
                )
            else:
                await self.send_message(chat_id,
                    f"👋 <b>Welcome to WinExtraFlow Bot!</b>\n\n"
                    f"To link your account, go to Dashboard → Profile and click 'Link Telegram'.\n\n"
                    f"Or register at {settings.frontend_url}/register"
                )

    async def _cmd_signals(self, chat_id: str):
        """Show latest signals."""
        from app.models.signal import Signal
        async with async_session() as db:
            result = await db.execute(
                select(Signal).order_by(Signal.created_at.desc()).limit(5)
            )
            signals = result.scalars().all()
            if not signals:
                await self.send_message(chat_id, "No signals yet. Stay tuned! 📡")
                return

            lines = ["<b>📊 Latest Signals:</b>\n"]
            for s in signals:
                emoji = "🟢" if s.action.value == "buy" else "🔴"
                conf = f" AI:{s.ai_confidence:.0%}" if s.ai_confidence else ""
                lines.append(f"{emoji} {s.action.value.upper()} <b>{s.ticker}</b> @ ${s.entry_price:,.2f}{conf}")
            await self.send_message(chat_id, "\n".join(lines))

    async def _cmd_premium(self, chat_id: str):
        """Show premium status."""
        from app.services.premium import is_premium, premium_days_left
        async with async_session() as db:
            user = (await db.execute(
                select(User).where(User.telegram_chat_id == chat_id)
            )).scalar_one_or_none()
            if not user:
                await self.send_message(chat_id, "Account not linked. Use /start to link.")
                return

            if is_premium(user):
                days = premium_days_left(user)
                await self.send_message(chat_id, f"💎 <b>Premium Active</b>\n{days} days remaining")
            else:
                await self.send_message(chat_id,
                    f"🔒 <b>Free Plan</b>\n\n"
                    f"Upgrade to Premium for unlimited signals, execution, and copy trading.\n"
                    f"{settings.frontend_url}/dashboard/premium"
                )

    async def _cmd_stop(self, chat_id: str):
        """Disable notifications."""
        async with async_session() as db:
            user = (await db.execute(
                select(User).where(User.telegram_chat_id == chat_id)
            )).scalar_one_or_none()
            if user:
                user.telegram_notifications = False
                await db.commit()
            await self.send_message(chat_id, "🔕 Notifications disabled. Use /start to re-enable.")

    async def _cmd_help(self, chat_id: str):
        await self.send_message(chat_id,
            "<b>WinExtraFlow Bot Commands:</b>\n\n"
            "/start — Link your account\n"
            "/signals — Latest 5 signals\n"
            "/premium — Premium status\n"
            "/stop — Disable notifications\n"
            "/help — This message\n\n"
            f"Dashboard: {settings.frontend_url}/dashboard"
        )


telegram_bot = TelegramBot()
