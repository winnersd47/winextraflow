"""Background worker for monitoring Telegram channels and fetching signals.

Uses Telethon to listen for new messages in subscribed channels,
parses them into trading signals and saves to the database.
"""

import asyncio
import logging

from sqlalchemy import select
from telethon import TelegramClient, events

from app.config import settings
from app.database import async_session
from app.models.provider import Provider, ProviderSource
from app.models.signal import Signal, SignalAction
from app.services.telegram import telegram_parser

logger = logging.getLogger(__name__)


class TelegramSignalWorker:
    """Background worker that monitors Telegram channels for trading signals."""

    def __init__(self):
        self.client: TelegramClient | None = None
        self._running = False
        self._monitored_channels: dict[str, Provider] = {}

    async def start(self):
        """Initialize Telethon client and start monitoring channels."""
        if not settings.telegram_api_id or not settings.telegram_api_hash:
            logger.warning("Telegram credentials not configured. Worker disabled.")
            return

        # Build connection kwargs: SOCKS5 → MTProxy → direct
        connect_kwargs = {}
        proxy_label = "direct"

        # Priority 1: SOCKS5 proxy
        if settings.socks5_host and settings.socks5_port:
            import socks
            proxy_tuple = (
                socks.SOCKS5,
                settings.socks5_host,
                settings.socks5_port,
                True,  # rdns
                settings.socks5_user or None,
                settings.socks5_pass or None,
            )
            connect_kwargs["proxy"] = proxy_tuple
            proxy_label = f"SOCKS5 {settings.socks5_host}:{settings.socks5_port}"
            logger.info(f"SOCKS5 proxy configured: {proxy_label}")

        # Priority 2: MTProxy
        elif settings.mtproxy_host and settings.mtproxy_port and settings.mtproxy_secret:
            try:
                from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate
                connect_kwargs["connection"] = ConnectionTcpMTProxyRandomizedIntermediate
                connect_kwargs["proxy"] = (
                    settings.mtproxy_host,
                    settings.mtproxy_port,
                    settings.mtproxy_secret,
                )
                proxy_label = f"MTProxy {settings.mtproxy_host}:{settings.mtproxy_port}"
                logger.info(f"MTProxy configured: {proxy_label}")
            except ImportError:
                logger.warning("MTProxy connection class not available")

        self.client = TelegramClient(
            "winextraflow_bot",
            int(settings.telegram_api_id),
            settings.telegram_api_hash,
            **connect_kwargs,
        )
        # Use existing session if authorized; only prompt for phone if no session
        await self.client.connect()
        if not await self.client.is_user_authorized():
            if settings.telegram_phone:
                await self.client.start(phone=settings.telegram_phone)
            else:
                logger.warning(
                    "Telegram session not authorized and no phone set. "
                    "Run scripts/tg_send_code.py + tg_signin.py to create a session."
                )
                await self.client.disconnect()
                return
        me = await self.client.get_me()
        logger.info(f"Telegram client connected via {proxy_label} as @{getattr(me, 'username', '?')}")

        # Load active Telegram providers from DB
        await self._load_channels()

        # Register message handler
        self.client.add_event_handler(
            self._on_new_message,
            events.NewMessage(chats=list(self._monitored_channels.keys())),
        )

        self._running = True
        logger.info(
            f"Monitoring {len(self._monitored_channels)} Telegram channels"
        )

    async def stop(self):
        """Disconnect Telethon client."""
        self._running = False
        if self.client:
            await self.client.disconnect()
            logger.info("Telegram client disconnected")

    async def resolve_username(self, username: str) -> dict | None:
        """Resolve a @username or t.me/username to channel_id and title."""
        if not self.client or not self.client.is_connected():
            logger.warning("Telegram client not connected, cannot resolve username")
            return None
        try:
            username = username.lstrip("@").split("/")[-1]  # Handle @name or t.me/name
            entity = await self.client.get_entity(username)
            return {
                "id": str(entity.id),
                "title": getattr(entity, "title", username),
                "username": getattr(entity, "username", username),
            }
        except Exception as e:
            logger.error(f"Failed to resolve Telegram username '{username}': {e}")
            return None

    async def _load_channels(self):
        """Load active Telegram channel providers from database + .env channels."""
        async with async_session() as db:
            result = await db.execute(
                select(Provider).where(
                    Provider.source == ProviderSource.TELEGRAM,
                    Provider.is_active == True,
                    Provider.telegram_channel_id.isnot(None),
                )
            )
            providers = result.scalars().all()
            self._monitored_channels = {
                p.telegram_channel_id: p for p in providers
            }

            # Also register channels from TELEGRAM_PARSE_CHANNELS env var
            env_channels = [c.strip() for c in settings.telegram_parse_channels.split(",") if c.strip()]
            for username in env_channels:
                # Check if already registered
                existing = await db.execute(
                    select(Provider).where(Provider.telegram_channel_id == username)
                )
                if existing.scalar_one_or_none():
                    continue

                # Resolve and register
                if self.client:
                    try:
                        entity = await self.client.get_entity(username)
                        title = getattr(entity, "title", username)
                        channel_id = str(entity.id)

                        # Create provider
                        import secrets
                        provider = Provider(
                            name=title,
                            source=ProviderSource.TELEGRAM,
                            description=f"Auto-registered from Telegram @{username}",
                            telegram_channel_id=channel_id,
                            is_active=True,
                        )
                        db.add(provider)
                        await db.commit()
                        await db.refresh(provider)
                        self._monitored_channels[channel_id] = provider
                        logger.info(f"Auto-registered channel @{username} as provider '{title}' (id: {channel_id})")
                    except Exception as e:
                        logger.warning(f"Could not resolve channel @{username}: {e}")

            logger.info(
                f"Loaded {len(self._monitored_channels)} channels: "
                f"{list(self._monitored_channels.keys())}"
            )

    async def reload_channels(self):
        """Reload channel list from database (call after add/remove channel)."""
        await self._load_channels()
        if self.client:
            # Remove old handlers and re-register
            self.client.remove_event_handler(self._on_new_message)
            self.client.add_event_handler(
                self._on_new_message,
                events.NewMessage(chats=list(self._monitored_channels.keys())),
            )

    async def _on_new_message(self, event: events.NewMessage.Event):
        """Handle new message from a monitored Telegram channel."""
        try:
            message_text = event.message.text
            if not message_text:
                return

            # Check if it looks like a signal
            if not telegram_parser.is_signal_message(message_text):
                return

            # Parse the signal (regex first, LLM fallback)
            parsed = telegram_parser.parse_message(message_text)
            if not parsed:
                # Fallback: try LLM parser for non-standard formats
                parsed = await telegram_parser.parse_with_llm(message_text)
                if parsed:
                    logger.info(f"LLM parsed signal: {parsed.action} {parsed.ticker}")
                else:
                    logger.debug(f"Could not parse signal from: {message_text[:100]}")
                    return

            # Find provider for this channel
            chat_id = str(event.chat_id)
            provider = self._monitored_channels.get(chat_id)
            if not provider:
                logger.warning(f"No provider found for channel {chat_id}")
                return

            # Save signal to database
            async with async_session() as db:
                signal = Signal(
                    provider_id=provider.id,
                    ticker=parsed.ticker,
                    action=SignalAction(parsed.action),
                    entry_price=parsed.entry_price,
                    take_profit=parsed.take_profit,
                    stop_loss=parsed.stop_loss,
                    timeframe=parsed.timeframe,
                    raw_message=message_text,
                )
                db.add(signal)

                # Update provider stats
                provider_db = await db.get(Provider, provider.id)
                if provider_db:
                    provider_db.total_signals = (provider_db.total_signals or 0) + 1

                await db.commit()
                logger.info(
                    f"New signal from {provider.name}: "
                    f"{parsed.action.upper()} {parsed.ticker} @ {parsed.entry_price}"
                )

        except Exception as e:
            logger.error(f"Error processing Telegram message: {e}", exc_info=True)


# Singleton worker instance
telegram_worker = TelegramSignalWorker()
