"""MetaTrader 5 adapter — Forex, CFD, Futures via MT5 Web API.

MetaTrader 5 is the world's most popular Forex trading platform.
Brokers: Exness, RoboForex, IC Markets, Pepperstone, XM, etc.

This adapter connects via the MT5 Manager/Web API.
Requires: server URL, login, password (configured as api_key=login, api_secret=password).

For production: use MetaApi (https://metaapi.cloud/) as a bridge, or
connect directly to broker's MT5 server via their REST API.
"""

import logging

import httpx

from app.services.exchanges.base import BaseExchangeAdapter, OrderResult

logger = logging.getLogger(__name__)


class MetaTrader5Adapter(BaseExchangeAdapter):
    """MetaTrader 5 via MetaApi cloud bridge or direct broker REST API.

    api_key = MetaApi account ID or broker login
    api_secret = MetaApi token or broker password
    """

    def __init__(self, api_key: str, api_secret: str, server_url: str = ""):
        super().__init__(api_key, api_secret)
        # MetaApi cloud: https://mt-client-api-v1.london.agiliumtrade.ai
        base = server_url or "https://mt-client-api-v1.london.agiliumtrade.ai"
        self.account_id = api_key
        self.client = httpx.AsyncClient(
            base_url=base,
            headers={"auth-token": api_secret},
            timeout=30.0,
        )

    async def place_market_order(self, symbol: str, side: str, quantity: float) -> OrderResult:
        action = "ORDER_TYPE_BUY" if side == "buy" else "ORDER_TYPE_SELL"
        payload = {
            "symbol": symbol.upper(),
            "actionType": action,
            "volume": quantity,
        }
        try:
            resp = await self.client.post(
                f"/users/current/accounts/{self.account_id}/trade", json=payload
            )
            data = resp.json()
            if resp.status_code != 200:
                return OrderResult(
                    exchange_order_id="", symbol=symbol, side=side, order_type="market",
                    quantity=quantity, price=None, filled_price=None, filled_quantity=None,
                    status="failed", error=data.get("message", "MT5 API error"),
                )
            return OrderResult(
                exchange_order_id=str(data.get("orderId", "")),
                symbol=symbol, side=side, order_type="market", quantity=quantity,
                price=data.get("openPrice"), filled_price=data.get("openPrice"),
                filled_quantity=quantity, status="filled",
            )
        except Exception as e:
            logger.error(f"MT5 market order error: {e}")
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side, order_type="market",
                quantity=quantity, price=None, filled_price=None, filled_quantity=None,
                status="failed", error="Exchange connection error",
            )

    async def place_limit_order(self, symbol: str, side: str, quantity: float, price: float) -> OrderResult:
        action = "ORDER_TYPE_BUY_LIMIT" if side == "buy" else "ORDER_TYPE_SELL_LIMIT"
        payload = {
            "symbol": symbol.upper(),
            "actionType": action,
            "volume": quantity,
            "openPrice": price,
        }
        try:
            resp = await self.client.post(
                f"/users/current/accounts/{self.account_id}/trade", json=payload
            )
            data = resp.json()
            if resp.status_code != 200:
                return OrderResult(
                    exchange_order_id="", symbol=symbol, side=side, order_type="limit",
                    quantity=quantity, price=price, filled_price=None, filled_quantity=None,
                    status="failed", error=data.get("message", "MT5 API error"),
                )
            return OrderResult(
                exchange_order_id=str(data.get("orderId", "")),
                symbol=symbol, side=side, order_type="limit", quantity=quantity,
                price=price, filled_price=None, filled_quantity=None, status="pending",
            )
        except Exception as e:
            logger.error(f"MT5 limit order error: {e}")
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side, order_type="limit",
                quantity=quantity, price=price, filled_price=None, filled_quantity=None,
                status="failed", error="Exchange connection error",
            )

    async def get_balance(self, asset: str = "USD") -> float:
        try:
            resp = await self.client.get(
                f"/users/current/accounts/{self.account_id}/account-information"
            )
            data = resp.json()
            return float(data.get("freeMargin", data.get("balance", 0)))
        except Exception:
            return 0.0

    async def get_ticker_price(self, symbol: str) -> float:
        try:
            resp = await self.client.get(
                f"/users/current/accounts/{self.account_id}/symbols/{symbol.upper()}/current-price"
            )
            data = resp.json()
            return float(data.get("ask", data.get("bid", 0)))
        except Exception:
            return 0.0

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        try:
            resp = await self.client.post(
                f"/users/current/accounts/{self.account_id}/trade",
                json={"actionType": "ORDER_CANCEL", "orderId": int(order_id)},
            )
            return resp.status_code == 200
        except Exception:
            return False
