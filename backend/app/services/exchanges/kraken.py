"""Kraken exchange adapter — crypto spot and futures.

Kraken REST API. Requires API key + private key from https://www.kraken.com/
One of the oldest and most regulated crypto exchanges (US/EU).
Supports: Spot, Margin, Staking, Futures.
"""

import base64
import hashlib
import hmac
import logging
import time
from urllib.parse import urlencode

import httpx

from app.services.exchanges.base import BaseExchangeAdapter, OrderResult

logger = logging.getLogger(__name__)

KRAKEN_BASE_URL = "https://api.kraken.com"


class KrakenAdapter(BaseExchangeAdapter):
    """Kraken REST API adapter."""

    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        self.client = httpx.AsyncClient(base_url=KRAKEN_BASE_URL, timeout=30.0)

    def _sign(self, path: str, data: dict) -> dict:
        """Kraken HMAC-SHA512 signature."""
        nonce = str(int(time.time() * 1000))
        data["nonce"] = nonce
        post_data = urlencode(data)
        encoded = (nonce + post_data).encode()
        message = path.encode() + hashlib.sha256(encoded).digest()
        signature = base64.b64encode(
            hmac.new(base64.b64decode(self.api_secret), message, hashlib.sha512).digest()
        ).decode()
        return {"API-Key": self.api_key, "API-Sign": signature}

    async def place_market_order(self, symbol: str, side: str, quantity: float) -> OrderResult:
        # Kraken uses pairs like XBTUSD, ETHUSD
        pair = self._normalize_pair(symbol)
        data = {"pair": pair, "type": side, "ordertype": "market", "volume": str(quantity)}
        headers = self._sign("/0/private/AddOrder", data)
        try:
            resp = await self.client.post("/0/private/AddOrder", data=data, headers=headers)
            result = resp.json()
            if result.get("error"):
                return OrderResult(
                    exchange_order_id="", symbol=symbol, side=side, order_type="market",
                    quantity=quantity, price=None, filled_price=None, filled_quantity=None,
                    status="failed", error=result["error"][0] if result["error"] else "Kraken error",
                )
            txids = result.get("result", {}).get("txid", [])
            return OrderResult(
                exchange_order_id=txids[0] if txids else "",
                symbol=symbol, side=side, order_type="market", quantity=quantity,
                price=None, filled_price=None, filled_quantity=quantity, status="filled",
            )
        except Exception as e:
            logger.error(f"Kraken market order error: {e}")
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side, order_type="market",
                quantity=quantity, price=None, filled_price=None, filled_quantity=None,
                status="failed", error="Exchange connection error",
            )

    async def place_limit_order(self, symbol: str, side: str, quantity: float, price: float) -> OrderResult:
        pair = self._normalize_pair(symbol)
        data = {"pair": pair, "type": side, "ordertype": "limit", "price": str(price), "volume": str(quantity)}
        headers = self._sign("/0/private/AddOrder", data)
        try:
            resp = await self.client.post("/0/private/AddOrder", data=data, headers=headers)
            result = resp.json()
            if result.get("error"):
                return OrderResult(
                    exchange_order_id="", symbol=symbol, side=side, order_type="limit",
                    quantity=quantity, price=price, filled_price=None, filled_quantity=None,
                    status="failed", error=result["error"][0] if result["error"] else "Kraken error",
                )
            txids = result.get("result", {}).get("txid", [])
            return OrderResult(
                exchange_order_id=txids[0] if txids else "",
                symbol=symbol, side=side, order_type="limit", quantity=quantity,
                price=price, filled_price=None, filled_quantity=None, status="pending",
            )
        except Exception as e:
            logger.error(f"Kraken limit order error: {e}")
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side, order_type="limit",
                quantity=quantity, price=price, filled_price=None, filled_quantity=None,
                status="failed", error="Exchange connection error",
            )

    async def get_balance(self, asset: str = "USDT") -> float:
        data: dict = {}
        headers = self._sign("/0/private/Balance", data)
        resp = await self.client.post("/0/private/Balance", data=data, headers=headers)
        result = resp.json()
        balances = result.get("result", {})
        # Kraken uses ZUSD for USD, XXBT for BTC, etc.
        asset_map = {"USDT": "USDT", "USD": "ZUSD", "BTC": "XXBT", "ETH": "XETH"}
        key = asset_map.get(asset.upper(), asset.upper())
        return float(balances.get(key, 0))

    async def get_ticker_price(self, symbol: str) -> float:
        pair = self._normalize_pair(symbol)
        resp = await self.client.get(f"/0/public/Ticker?pair={pair}")
        result = resp.json()
        for _, v in result.get("result", {}).items():
            return float(v.get("c", [0])[0])  # "c" = last trade closed [price, lot-volume]
        return 0.0

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        data = {"txid": order_id}
        headers = self._sign("/0/private/CancelOrder", data)
        resp = await self.client.post("/0/private/CancelOrder", data=data, headers=headers)
        return not resp.json().get("error")

    @staticmethod
    def _normalize_pair(symbol: str) -> str:
        """Convert BTCUSDT → XBTUSDT for Kraken."""
        s = symbol.upper()
        s = s.replace("BTC", "XBT")
        return s
