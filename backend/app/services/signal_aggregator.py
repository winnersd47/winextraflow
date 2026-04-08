"""Signal Aggregator — unified entry point for all signal sources.

Handles normalization, deduplication, and broadcasting of signals
regardless of their origin (TradingView, Telegram, Manual).
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal import Signal, SignalAction, SignalStatus

logger = logging.getLogger(__name__)

# Deduplication window: signals from same provider with same ticker/action
# within this time window are considered duplicates
DEDUP_WINDOW_MINUTES = 5


class SignalAggregator:
    """Central service for signal normalization and deduplication."""

    def __init__(self):
        self._listeners: list = []  # Callbacks for new signal notifications

    def on_new_signal(self, callback):
        """Register a callback to be called when a new signal is created.

        Used by WebSocket broadcaster to push real-time updates.
        """
        self._listeners.append(callback)

    def remove_listener(self, callback):
        """Remove a previously registered callback."""
        self._listeners = [cb for cb in self._listeners if cb != callback]

    async def _notify_listeners(self, signal: Signal):
        """Notify all registered listeners about a new signal."""
        for callback in self._listeners:
            try:
                await callback(signal)
            except Exception as e:
                logger.error(f"Listener error: {e}")

    @staticmethod
    def normalize_ticker(ticker: str) -> str:
        """Normalize ticker symbol to a standard format.

        Examples:
            BTC/USDT -> BTCUSDT
            btcusdt -> BTCUSDT
            BTC-USDT -> BTCUSDT
        """
        ticker = ticker.upper().strip()
        # Remove common separators
        for sep in ["/", "-", "_", "."]:
            ticker = ticker.replace(sep, "")
        return ticker

    async def check_duplicate(
        self,
        db: AsyncSession,
        provider_id,
        ticker: str,
        action: SignalAction,
    ) -> bool:
        """Check if a similar signal already exists within the dedup window.

        Returns True if a duplicate was found.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=DEDUP_WINDOW_MINUTES)
        result = await db.execute(
            select(Signal).where(
                and_(
                    Signal.provider_id == provider_id,
                    Signal.ticker == ticker,
                    Signal.action == action,
                    Signal.created_at >= cutoff,
                )
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            logger.info(
                f"Duplicate signal detected: {action.value} {ticker} "
                f"from provider {provider_id} (existing: {existing.id})"
            )
            return True
        return False

    async def process_signal(
        self,
        db: AsyncSession,
        *,
        provider_id,
        ticker: str,
        action: str | SignalAction,
        entry_price: float,
        take_profit: float | None = None,
        stop_loss: float | None = None,
        timeframe: str | None = None,
        raw_message: str | None = None,
        skip_dedup: bool = False,
    ) -> Signal | None:
        """Process and save a normalized signal.

        1. Normalizes ticker
        2. Checks for duplicates
        3. Creates Signal record
        4. Notifies listeners

        Returns the created Signal, or None if it was a duplicate.
        """
        # Normalize
        ticker = self.normalize_ticker(ticker)
        if isinstance(action, str):
            action = SignalAction(action.lower())

        # Dedup check
        if not skip_dedup:
            is_dup = await self.check_duplicate(db, provider_id, ticker, action)
            if is_dup:
                return None

        # Create signal
        signal = Signal(
            provider_id=provider_id,
            ticker=ticker,
            action=action,
            entry_price=entry_price,
            take_profit=take_profit,
            stop_loss=stop_loss,
            timeframe=timeframe,
            raw_message=raw_message,
        )
        db.add(signal)
        await db.commit()
        await db.refresh(signal)

        logger.info(f"New signal: {action.value} {ticker} @ {entry_price}")

        # Notify listeners (WebSocket, etc.)
        await self._notify_listeners(signal)

        return signal

    async def get_active_signals(
        self, db: AsyncSession, limit: int = 50
    ) -> list[Signal]:
        """Get currently active signals."""
        result = await db.execute(
            select(Signal)
            .where(Signal.status == SignalStatus.ACTIVE)
            .order_by(Signal.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


signal_aggregator = SignalAggregator()
