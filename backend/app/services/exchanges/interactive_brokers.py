"""Interactive Brokers adapter — stocks, options, futures, forex, bonds.

IBKR is the world's largest electronic broker by daily revenue trades.
Used by professional traders and institutions worldwide.

This adapter uses the IBKR Client Portal API (Web API).
Requires: IBKR account + Client Portal Gateway running.
Docs: https://ibkrcampus.com/ibkr-api-page/cpapi-v1/

api_key = account ID (e.g. "DU12345")
api_secret = not used for CP API (session-based auth)
"""

import logging

import httpx

from app.services.exchanges.base import BaseExchangeAdapter, OrderResult

logger = logging.getLogger(__name__)

# Default Client Portal Gateway URL (local or cloud)
IBKR_BASE_URL = "https://localhost:5000/v1/api"


class InteractiveBrokersAdapter(BaseExchangeAdapter):
    """Interactive Brokers Client Portal API adapter."""

    def __init__(self, api_key: str, api_secret: str, gateway_url: str = ""):
        super().__init__(api_key, api_secret)
        self.account_id = api_key
        base = gateway_url or IBKR_BASE_URL
        self.client = httpx.AsyncClient(
            base_url=base, timeout=30.0, verify=False  # CP Gateway uses self-signed cert
        )

    async def place_market_order(self, symbol: str, side: str, quantity: float) -> OrderResult:
        conid = await self._resolve_conid(symbol)
        if not conid:
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side, order_type="market",
                quantity=quantity, price=None, filled_price=None, filled_quantity=None,
                status="failed", error=f"Cannot resolve contract for {symbol}",
            )
        order = {
            "acctId": self.account_id,
            "conid": conid,
            "orderType": "MKT",
            "side": side.upper(),
            "quantity": quantity,
            "tif": "DAY",
        }
        try:
            resp = await self.client.post(
                f"/iserver/account/{self.account_id}/orders", json={"orders": [order]}
            )
            data = resp.json()
            if isinstance(data, list) and data:
                item = data[0]
                if item.get("order_id"):
                    return OrderResult(
                        exchange_order_id=str(item["order_id"]),
                        symbol=symbol, side=side, order_type="market", quantity=quantity,
                        price=None, filled_price=None, filled_quantity=quantity,
                        status="filled",
                    )
                return OrderResult(
                    exchange_order_id="", symbol=symbol, side=side, order_type="market",
                    quantity=quantity, price=None, filled_price=None, filled_quantity=None,
                    status="failed", error=item.get("error", "IBKR order rejected"),
                )
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side, order_type="market",
                quantity=quantity, price=None, filled_price=None, filled_quantity=None,
                status="failed", error="Unexpected IBKR response",
            )
        except Exception as e:
            logger.error(f"IBKR market order error: {e}")
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side, order_type="market",
                quantity=quantity, price=None, filled_price=None, filled_quantity=None,
                status="failed", error="Exchange connection error",
            )

    async def place_limit_order(self, symbol: str, side: str, quantity: float, price: float) -> OrderResult:
        conid = await self._resolve_conid(symbol)
        if not conid:
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side, order_type="limit",
                quantity=quantity, price=price, filled_price=None, filled_quantity=None,
                status="failed", error=f"Cannot resolve contract for {symbol}",
            )
        order = {
            "acctId": self.account_id,
            "conid": conid,
            "orderType": "LMT",
            "side": side.upper(),
            "quantity": quantity,
            "price": price,
            "tif": "GTC",
        }
        try:
            resp = await self.client.post(
                f"/iserver/account/{self.account_id}/orders", json={"orders": [order]}
            )
            data = resp.json()
            if isinstance(data, list) and data and data[0].get("order_id"):
                return OrderResult(
                    exchange_order_id=str(data[0]["order_id"]),
                    symbol=symbol, side=side, order_type="limit", quantity=quantity,
                    price=price, filled_price=None, filled_quantity=None, status="pending",
                )
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side, order_type="limit",
                quantity=quantity, price=price, filled_price=None, filled_quantity=None,
                status="failed", error="IBKR order rejected",
            )
        except Exception as e:
            logger.error(f"IBKR limit order error: {e}")
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side, order_type="limit",
                quantity=quantity, price=price, filled_price=None, filled_quantity=None,
                status="failed", error="Exchange connection error",
            )

    async def get_balance(self, asset: str = "USD") -> float:
        try:
            resp = await self.client.get(f"/portfolio/{self.account_id}/summary")
            data = resp.json()
            return float(data.get("availablefunds", {}).get("amount", 0))
        except Exception:
            return 0.0

    async def get_ticker_price(self, symbol: str) -> float:
        conid = await self._resolve_conid(symbol)
        if not conid:
            return 0.0
        try:
            resp = await self.client.get(f"/iserver/marketdata/snapshot?conids={conid}&fields=31")
            data = resp.json()
            if isinstance(data, list) and data:
                return float(data[0].get("31", 0))  # field 31 = last price
            return 0.0
        except Exception:
            return 0.0

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        try:
            resp = await self.client.delete(
                f"/iserver/account/{self.account_id}/order/{order_id}"
            )
            return resp.status_code == 200
        except Exception:
            return False

    async def _resolve_conid(self, symbol: str) -> int | None:
        """Resolve ticker symbol to IBKR contract ID."""
        try:
            resp = await self.client.get(f"/iserver/secdef/search?symbol={symbol}")
            data = resp.json()
            if isinstance(data, list) and data:
                return data[0].get("conid")
        except Exception:
            pass
        return None
