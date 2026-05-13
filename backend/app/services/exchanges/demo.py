"""Demo (paper trading) exchange adapter — instant fills, no real money."""

import logging
import uuid

from app.services.exchanges.base import BaseExchangeAdapter, OrderResult

logger = logging.getLogger(__name__)

# Simulated balances per user session
_demo_balances: dict[str, float] = {}
_demo_prices: dict[str, float] = {
    # Crypto
    "BTCUSDT": 65000.0,
    "ETHUSDT": 3500.0,
    "BNBUSDT": 580.0,
    "SOLUSDT": 145.0,
    "XRPUSDT": 0.55,
    "DOGEUSDT": 0.12,
    "AVAXUSDT": 35.0,
    "ADAUSDT": 0.45,
    "DOTUSDT": 7.20,
    "MATICUSDT": 0.70,
    "LINKUSDT": 14.50,
    "NEARUSDT": 6.80,
    # Forex
    "EURUSD": 1.0850,
    "GBPUSD": 1.2720,
    "USDJPY": 155.50,
    "USDCHF": 0.8830,
    "AUDUSD": 0.6620,
    "USDCAD": 1.3650,
    "EURGBP": 0.8530,
    "EURJPY": 168.70,
    # US Stocks
    "AAPL": 192.50,
    "MSFT": 415.00,
    "GOOGL": 175.30,
    "AMZN": 185.60,
    "TSLA": 245.00,
    "NVDA": 880.00,
    "META": 505.00,
    # RU Stocks (MOEX)
    "SBER": 305.0,
    "GAZP": 163.0,
    "LKOH": 7200.0,
    "YNDX": 3800.0,
    "GMKN": 155.0,
    # Indices / Futures
    "SPX500": 5320.0,
    "NAS100": 18750.0,
    "XAUUSD": 2350.0,
    "XAGUSD": 29.50,
}

INITIAL_BALANCE = 100000.0  # $100k paper money


class DemoAdapter(BaseExchangeAdapter):
    """Paper trading adapter — simulates exchange behavior instantly."""

    def __init__(self, api_key: str = "demo", api_secret: str = "demo"):
        super().__init__(api_key, api_secret)
        if api_key not in _demo_balances:
            _demo_balances[api_key] = INITIAL_BALANCE

    async def place_market_order(
        self, symbol: str, side: str, quantity: float
    ) -> OrderResult:
        price = await self.get_ticker_price(symbol)
        cost = price * quantity

        if side == "buy":
            balance = _demo_balances.get(self.api_key, 0)
            if cost > balance:
                return OrderResult(
                    exchange_order_id="",
                    symbol=symbol,
                    side=side,
                    order_type="market",
                    quantity=quantity,
                    price=price,
                    filled_price=None,
                    filled_quantity=None,
                    status="failed",
                    error=f"Insufficient balance: need ${cost:.2f}, have ${balance:.2f}",
                )
            _demo_balances[self.api_key] -= cost
        else:
            _demo_balances[self.api_key] += cost

        order_id = f"DEMO-{uuid.uuid4().hex[:12].upper()}"
        logger.info(f"[DEMO] {side.upper()} {quantity} {symbol} @ {price} (ID: {order_id})")

        return OrderResult(
            exchange_order_id=order_id,
            symbol=symbol,
            side=side,
            order_type="market",
            quantity=quantity,
            price=price,
            filled_price=price,
            filled_quantity=quantity,
            status="filled",
        )

    async def place_limit_order(
        self, symbol: str, side: str, quantity: float, price: float
    ) -> OrderResult:
        # Demo: limit orders fill instantly at requested price
        order_id = f"DEMO-{uuid.uuid4().hex[:12].upper()}"
        logger.info(f"[DEMO] LIMIT {side.upper()} {quantity} {symbol} @ {price} (ID: {order_id})")

        return OrderResult(
            exchange_order_id=order_id,
            symbol=symbol,
            side=side,
            order_type="limit",
            quantity=quantity,
            price=price,
            filled_price=price,
            filled_quantity=quantity,
            status="filled",
        )

    async def get_balance(self, asset: str = "USDT") -> float:
        return _demo_balances.get(self.api_key, INITIAL_BALANCE)

    async def get_ticker_price(self, symbol: str) -> float:
        return _demo_prices.get(symbol.upper(), 100.0)

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        logger.info(f"[DEMO] Cancelled order {order_id}")
        return True
