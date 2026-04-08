"""TradingView webhook processing service."""

import logging
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import Provider, ProviderSource
from app.models.signal import Signal, SignalAction

logger = logging.getLogger(__name__)

# Valid ticker pattern: 1-20 alphanumeric chars, may include / for forex pairs
TICKER_PATTERN = re.compile(r"^[A-Z0-9]{1,10}(?:[/.-][A-Z0-9]{1,10})?$")

# TradingView alert message patterns
ALERT_PATTERNS = [
    # "BUY BTCUSDT at 65000"
    re.compile(
        r"(?P<action>BUY|SELL|CLOSE)\s+(?P<ticker>[A-Z0-9/.]+)\s+(?:at|@)\s+(?P<price>[\d.]+)",
        re.IGNORECASE,
    ),
    # "BTCUSDT | BUY | Entry: 65000 | TP: 67000 | SL: 63000"
    re.compile(
        r"(?P<ticker>[A-Z0-9/.]+)\s*\|\s*(?P<action>BUY|SELL|CLOSE)\s*\|"
        r"\s*(?:Entry|Price):\s*(?P<price>[\d.]+)"
        r"(?:\s*\|\s*TP:\s*(?P<tp>[\d.]+))?"
        r"(?:\s*\|\s*SL:\s*(?P<sl>[\d.]+))?",
        re.IGNORECASE,
    ),
]


class TradingViewService:
    """Process TradingView webhook alerts into normalized signals."""

    @staticmethod
    def validate_ticker(ticker: str) -> str:
        """Validate and normalize ticker symbol."""
        ticker = ticker.upper().strip()
        if not TICKER_PATTERN.match(ticker):
            raise ValueError(f"Invalid ticker format: {ticker}")
        return ticker

    @staticmethod
    def validate_price(price: float) -> float:
        """Validate price is positive."""
        if price <= 0:
            raise ValueError(f"Price must be positive, got: {price}")
        return price

    @staticmethod
    def parse_alert_message(message: str) -> dict | None:
        """Parse a TradingView alert text message into structured data.

        Returns dict with keys: ticker, action, price, tp, sl
        or None if no pattern matched.
        """
        for pattern in ALERT_PATTERNS:
            match = pattern.search(message)
            if match:
                groups = match.groupdict()
                result = {
                    "ticker": groups["ticker"].upper(),
                    "action": groups["action"].lower(),
                    "price": float(groups["price"]),
                }
                if groups.get("tp"):
                    result["take_profit"] = float(groups["tp"])
                if groups.get("sl"):
                    result["stop_loss"] = float(groups["sl"])
                return result
        return None

    @staticmethod
    async def get_or_create_provider(
        db: AsyncSession, name: str = "TradingView Default", webhook_id: str | None = None
    ) -> Provider:
        """Get existing or create new TradingView provider."""
        result = await db.execute(select(Provider).where(Provider.name == name))
        provider = result.scalar_one_or_none()
        if not provider:
            provider = Provider(
                name=name,
                source=ProviderSource.TRADINGVIEW,
                tradingview_webhook_id=webhook_id,
            )
            db.add(provider)
            await db.flush()
            logger.info(f"Created TradingView provider: {name}")
        return provider

    async def process_webhook(
        self,
        db: AsyncSession,
        *,
        ticker: str,
        action: str,
        price: float,
        timeframe: str | None = None,
        take_profit: float | None = None,
        stop_loss: float | None = None,
        provider_name: str = "TradingView Default",
        raw_message: str | None = None,
    ) -> Signal:
        """Process a TradingView webhook and create a Signal.

        Validates input, resolves provider, creates and returns Signal.
        """
        ticker = self.validate_ticker(ticker)
        price = self.validate_price(price)
        if take_profit is not None:
            self.validate_price(take_profit)
        if stop_loss is not None:
            self.validate_price(stop_loss)

        signal_action = SignalAction(action.lower())
        provider = await self.get_or_create_provider(db, name=provider_name)

        signal = Signal(
            provider_id=provider.id,
            ticker=ticker,
            action=signal_action,
            entry_price=price,
            take_profit=take_profit,
            stop_loss=stop_loss,
            timeframe=timeframe,
            raw_message=raw_message,
        )
        db.add(signal)

        # Update provider stats
        provider.total_signals = (provider.total_signals or 0) + 1

        await db.commit()
        await db.refresh(signal)
        logger.info(f"Created signal: {signal_action.value} {ticker} @ {price}")
        return signal


tradingview_service = TradingViewService()
