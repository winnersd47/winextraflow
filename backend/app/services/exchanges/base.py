"""Abstract base class for exchange adapters."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class OrderResult:
    """Result of an order placement on an exchange."""

    exchange_order_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: float | None
    filled_price: float | None
    filled_quantity: float | None
    status: str  # "filled", "pending", "failed"
    error: str | None = None


class BaseExchangeAdapter(ABC):
    """Abstract exchange adapter interface."""

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret

    @abstractmethod
    async def place_market_order(
        self, symbol: str, side: str, quantity: float
    ) -> OrderResult:
        """Place a market order."""
        ...

    @abstractmethod
    async def place_limit_order(
        self, symbol: str, side: str, quantity: float, price: float
    ) -> OrderResult:
        """Place a limit order."""
        ...

    @abstractmethod
    async def get_balance(self, asset: str = "USDT") -> float:
        """Get available balance for an asset."""
        ...

    @abstractmethod
    async def get_ticker_price(self, symbol: str) -> float:
        """Get current price for a symbol."""
        ...

    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancel an open order."""
        ...
