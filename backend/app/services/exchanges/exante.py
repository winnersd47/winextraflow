"""Exante adapter — EU/US stocks, options, futures, forex, crypto.

Exante is a multi-asset broker licensed in EU (CySEC), Malta, UK.
Provides access to 50+ markets: NYSE, NASDAQ, LSE, MOEX, CME, etc.
API docs: https://api-live.exante.eu/api-docs/

api_key = application ID
api_secret = access key
"""

import logging

import httpx

from app.services.exchanges.base import BaseExchangeAdapter, OrderResult

logger = logging.getLogger(__name__)

EXANTE_BASE_URL = "https://api-live.exante.eu/md/3.0"
EXANTE_TRADE_URL = "https://api-live.exante.eu/trade/3.0"


class ExanteAdapter(BaseExchangeAdapter):
    """Exante REST API v3 adapter."""

    def __init__(self, api_key: str, api_secret: str, account_id: str = ""):
        super().__init__(api_key, api_secret)
        self.account_id = account_id or api_key
        auth = (api_key, api_secret)
        self.md_client = httpx.AsyncClient(base_url=EXANTE_BASE_URL, auth=auth, timeout=30.0)
        self.trade_client = httpx.AsyncClient(base_url=EXANTE_TRADE_URL, auth=auth, timeout=30.0)

    async def place_market_order(self, symbol: str, side: str, quantity: float) -> OrderResult:
        payload = {
            "symbolId": symbol,
            "side": side,
            "quantity": str(quantity),
            "orderType": "market",
            "duration": "day",
            "accountId": self.account_id,
        }
        try:
            resp = await self.trade_client.post("/orders", json=payload)
            data = resp.json()
            if resp.status_code in (200, 201):
                return OrderResult(
                    exchange_order_id=data.get("orderId", ""),
                    symbol=symbol, side=side, order_type="market", quantity=quantity,
                    price=None, filled_price=float(data.get("averagePrice", 0)) or None,
                    filled_quantity=float(data.get("filledQuantity", 0)) or None,
                    status="filled" if data.get("orderState") == "filled" else "pending",
                )
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side, order_type="market",
                quantity=quantity, price=None, filled_price=None, filled_quantity=None,
                status="failed", error=data.get("message", "Exante order rejected"),
            )
        except Exception as e:
            logger.error(f"Exante market order error: {e}")
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side, order_type="market",
                quantity=quantity, price=None, filled_price=None, filled_quantity=None,
                status="failed", error="Exchange connection error",
            )

    async def place_limit_order(self, symbol: str, side: str, quantity: float, price: float) -> OrderResult:
        payload = {
            "symbolId": symbol,
            "side": side,
            "quantity": str(quantity),
            "orderType": "limit",
            "limitPrice": str(price),
            "duration": "good_till_cancel",
            "accountId": self.account_id,
        }
        try:
            resp = await self.trade_client.post("/orders", json=payload)
            data = resp.json()
            if resp.status_code in (200, 201):
                return OrderResult(
                    exchange_order_id=data.get("orderId", ""),
                    symbol=symbol, side=side, order_type="limit", quantity=quantity,
                    price=price, filled_price=None, filled_quantity=None, status="pending",
                )
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side, order_type="limit",
                quantity=quantity, price=price, filled_price=None, filled_quantity=None,
                status="failed", error=data.get("message", "Exante order rejected"),
            )
        except Exception as e:
            logger.error(f"Exante limit order error: {e}")
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side, order_type="limit",
                quantity=quantity, price=price, filled_price=None, filled_quantity=None,
                status="failed", error="Exchange connection error",
            )

    async def get_balance(self, asset: str = "USD") -> float:
        try:
            resp = await self.trade_client.get(f"/accounts/{self.account_id}/summary/{asset}")
            data = resp.json()
            return float(data.get("freeMoney", data.get("netAssetValue", 0)))
        except Exception:
            return 0.0

    async def get_ticker_price(self, symbol: str) -> float:
        try:
            resp = await self.md_client.get(f"/symbols/{symbol}/last-quote")
            data = resp.json()
            if isinstance(data, list) and data:
                return float(data[0].get("ask", data[0].get("bid", 0)))
            elif isinstance(data, dict):
                return float(data.get("ask", data.get("bid", 0)))
        except Exception:
            pass
        return 0.0

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        try:
            resp = await self.trade_client.delete(f"/orders/{order_id}")
            return resp.status_code == 200
        except Exception:
            return False
