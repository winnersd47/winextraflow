"""Binance exchange adapter — real trading via Binance REST API.

Uses httpx for HTTP requests with HMAC-SHA256 signature authentication.
This is a production-ready skeleton — requires real API keys to function.
"""

import hashlib
import hmac
import logging
import time
from urllib.parse import urlencode

import httpx

from app.services.exchanges.base import BaseExchangeAdapter, OrderResult

logger = logging.getLogger(__name__)

BINANCE_BASE_URL = "https://api.binance.com"


class BinanceAdapter(BaseExchangeAdapter):
    """Binance exchange adapter with HMAC authentication."""

    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        self.client = httpx.AsyncClient(
            base_url=BINANCE_BASE_URL,
            headers={"X-MBX-APIKEY": api_key},
            timeout=30.0,
        )

    def _sign(self, params: dict) -> dict:
        """Add timestamp and HMAC-SHA256 signature to params."""
        params["timestamp"] = int(time.time() * 1000)
        query = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode(), query.encode(), hashlib.sha256
        ).hexdigest()
        params["signature"] = signature
        return params

    async def place_market_order(
        self, symbol: str, side: str, quantity: float
    ) -> OrderResult:
        params = self._sign({
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": "MARKET",
            "quantity": str(quantity),
        })
        try:
            resp = await self.client.post("/api/v3/order", params=params)
            data = resp.json()
            if resp.status_code != 200:
                return OrderResult(
                    exchange_order_id="",
                    symbol=symbol, side=side, order_type="market",
                    quantity=quantity, price=None,
                    filled_price=None, filled_quantity=None,
                    status="failed",
                    error=data.get("msg", f"HTTP {resp.status_code}"),
                )
            return OrderResult(
                exchange_order_id=str(data["orderId"]),
                symbol=symbol, side=side, order_type="market",
                quantity=quantity,
                price=float(data.get("price", 0)),
                filled_price=float(data.get("fills", [{}])[0].get("price", 0)) if data.get("fills") else None,
                filled_quantity=float(data.get("executedQty", 0)),
                status="filled" if data["status"] == "FILLED" else "pending",
            )
        except Exception as e:
            logger.error(f"Binance market order error: {e}")
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side,
                order_type="market", quantity=quantity, price=None,
                filled_price=None, filled_quantity=None,
                status="failed", error="Exchange connection error",
            )

    async def place_limit_order(
        self, symbol: str, side: str, quantity: float, price: float
    ) -> OrderResult:
        params = self._sign({
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": str(quantity),
            "price": str(price),
        })
        try:
            resp = await self.client.post("/api/v3/order", params=params)
            data = resp.json()
            if resp.status_code != 200:
                return OrderResult(
                    exchange_order_id="", symbol=symbol, side=side,
                    order_type="limit", quantity=quantity, price=price,
                    filled_price=None, filled_quantity=None,
                    status="failed", error=data.get("msg", f"HTTP {resp.status_code}"),
                )
            return OrderResult(
                exchange_order_id=str(data["orderId"]),
                symbol=symbol, side=side, order_type="limit",
                quantity=quantity, price=price,
                filled_price=float(data.get("price", 0)),
                filled_quantity=float(data.get("executedQty", 0)),
                status="filled" if data["status"] == "FILLED" else "pending",
            )
        except Exception as e:
            logger.error(f"Binance limit order error: {e}")
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side,
                order_type="limit", quantity=quantity, price=price,
                filled_price=None, filled_quantity=None,
                status="failed", error="Exchange connection error",
            )

    async def get_balance(self, asset: str = "USDT") -> float:
        params = self._sign({})
        resp = await self.client.get("/api/v3/account", params=params)
        data = resp.json()
        for b in data.get("balances", []):
            if b["asset"] == asset.upper():
                return float(b["free"])
        return 0.0

    async def get_ticker_price(self, symbol: str) -> float:
        resp = await self.client.get("/api/v3/ticker/price", params={"symbol": symbol.upper()})
        data = resp.json()
        return float(data.get("price", 0))

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        params = self._sign({"symbol": symbol.upper(), "orderId": order_id})
        resp = await self.client.delete("/api/v3/order", params=params)
        return resp.status_code == 200
