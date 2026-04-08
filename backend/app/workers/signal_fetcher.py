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

        self.client = TelegramClient(
            "winextraflow_bot",
            int(settings.telegram_api_id),
            settings.telegram_api_hash,
        )
        await self.client.start(phone=settings.telegram_phone)
        logger.info("Telegram client connected")

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

    async def _load_channels(self):
        """Load active Telegram channel providers from database."""
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

            # Parse the signal
            parsed = telegram_parser.parse_message(message_text)
            if not parsed:
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
