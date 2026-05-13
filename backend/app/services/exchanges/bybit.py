"""Bybit exchange adapter — crypto derivatives and spot trading.

Bybit V5 Unified API. Requires API key + secret from https://www.bybit.com/
Supports: Spot, Linear (USDT perpetual), Inverse, Options.
"""

import hashlib
import hmac
import logging
import time

import httpx

from app.services.exchanges.base import BaseExchangeAdapter, OrderResult

logger = logging.getLogger(__name__)

BYBIT_BASE_URL = "https://api.bybit.com"


class BybitAdapter(BaseExchangeAdapter):
    """Bybit V5 Unified API adapter."""

    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        self.client = httpx.AsyncClient(base_url=BYBIT_BASE_URL, timeout=30.0)

    def _sign(self, params: str, timestamp: str) -> dict:
        """Generate Bybit V5 HMAC-SHA256 signature."""
        recv_window = "5000"
        sign_str = f"{timestamp}{self.api_key}{recv_window}{params}"
        signature = hmac.new(
            self.api_secret.encode(), sign_str.encode(), hashlib.sha256
        ).hexdigest()
        return {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": recv_window,
            "X-BAPI-SIGN": signature,
            "Content-Type": "application/json",
        }

    async def place_market_order(self, symbol: str, side: str, quantity: float) -> OrderResult:
        timestamp = str(int(time.time() * 1000))
        body = f'{{"category":"spot","symbol":"{symbol.upper()}","side":"{side.capitalize()}","orderType":"Market","qty":"{quantity}"}}'
        headers = self._sign(body, timestamp)
        try:
            resp = await self.client.post("/v5/order/create", content=body, headers=headers)
            data = resp.json()
            if data.get("retCode") != 0:
                return OrderResult(
                    exchange_order_id="", symbol=symbol, side=side, order_type="market",
                    quantity=quantity, price=None, filled_price=None, filled_quantity=None,
                    status="failed", error=data.get("retMsg", "Bybit API error"),
                )
            result = data.get("result", {})
            return OrderResult(
                exchange_order_id=result.get("orderId", ""),
                symbol=symbol, side=side, order_type="market", quantity=quantity,
                price=None, filled_price=None, filled_quantity=quantity,
                status="filled",
            )
        except Exception as e:
            logger.error(f"Bybit market order error: {e}")
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side, order_type="market",
                quantity=quantity, price=None, filled_price=None, filled_quantity=None,
                status="failed", error="Exchange connection error",
            )

    async def place_limit_order(self, symbol: str, side: str, quantity: float, price: float) -> OrderResult:
        timestamp = str(int(time.time() * 1000))
        body = f'{{"category":"spot","symbol":"{symbol.upper()}","side":"{side.capitalize()}","orderType":"Limit","qty":"{quantity}","price":"{price}"}}'
        headers = self._sign(body, timestamp)
        try:
            resp = await self.client.post("/v5/order/create", content=body, headers=headers)
            data = resp.json()
            if data.get("retCode") != 0:
                return OrderResult(
                    exchange_order_id="", symbol=symbol, side=side, order_type="limit",
                    quantity=quantity, price=price, filled_price=None, filled_quantity=None,
                    status="failed", error=data.get("retMsg", "Bybit API error"),
                )
            result = data.get("result", {})
            return OrderResult(
                exchange_order_id=result.get("orderId", ""),
                symbol=symbol, side=side, order_type="limit", quantity=quantity,
                price=price, filled_price=None, filled_quantity=None, status="pending",
            )
        except Exception as e:
            logger.error(f"Bybit limit order error: {e}")
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side, order_type="limit",
                quantity=quantity, price=price, filled_price=None, filled_quantity=None,
                status="failed", error="Exchange connection error",
            )

    async def get_balance(self, asset: str = "USDT") -> float:
        timestamp = str(int(time.time() * 1000))
        params = f"accountType=UNIFIED&coin={asset.upper()}"
        headers = self._sign(params, timestamp)
        resp = await self.client.get(f"/v5/account/wallet-balance?{params}", headers=headers)
        data = resp.json()
        for acct in data.get("result", {}).get("list", []):
            for coin in acct.get("coin", []):
                if coin.get("coin") == asset.upper():
                    return float(coin.get("availableToWithdraw", 0))
        return 0.0

    async def get_ticker_price(self, symbol: str) -> float:
        resp = await self.client.get("/v5/market/tickers", params={"category": "spot", "symbol": symbol.upper()})
        data = resp.json()
        tickers = data.get("result", {}).get("list", [])
        if tickers:
            return float(tickers[0].get("lastPrice", 0))
        return 0.0

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        timestamp = str(int(time.time() * 1000))
        body = f'{{"category":"spot","symbol":"{symbol.upper()}","orderId":"{order_id}"}}'
        headers = self._sign(body, timestamp)
        resp = await self.client.post("/v5/order/cancel", content=body, headers=headers)
        return resp.json().get("retCode") == 0
