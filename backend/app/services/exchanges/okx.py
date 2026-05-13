"""OKX exchange adapter — crypto spot, futures, options.

OKX V5 API. Requires API key + secret + passphrase from https://www.okx.com/
Supports: Spot, Margin, Swap (perpetual), Futures, Options.
"""

import base64
import hashlib
import hmac
import logging
import time
from datetime import datetime, timezone

import httpx

from app.services.exchanges.base import BaseExchangeAdapter, OrderResult

logger = logging.getLogger(__name__)

OKX_BASE_URL = "https://www.okx.com"


class OKXAdapter(BaseExchangeAdapter):
    """OKX V5 REST API adapter."""

    def __init__(self, api_key: str, api_secret: str, passphrase: str = ""):
        super().__init__(api_key, api_secret)
        self.passphrase = passphrase
        self.client = httpx.AsyncClient(base_url=OKX_BASE_URL, timeout=30.0)

    def _sign(self, timestamp: str, method: str, path: str, body: str = "") -> dict:
        sign_str = f"{timestamp}{method}{path}{body}"
        signature = base64.b64encode(
            hmac.new(self.api_secret.encode(), sign_str.encode(), hashlib.sha256).digest()
        ).decode()
        return {
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
        }

    async def place_market_order(self, symbol: str, side: str, quantity: float) -> OrderResult:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        path = "/api/v5/trade/order"
        # OKX uses instId like BTC-USDT (hyphen, not concatenated)
        inst_id = symbol.upper().replace("USDT", "-USDT").replace("USD", "-USD") if "-" not in symbol else symbol
        body = f'{{"instId":"{inst_id}","tdMode":"cash","side":"{side}","ordType":"market","sz":"{quantity}"}}'
        headers = self._sign(timestamp, "POST", path, body)
        try:
            resp = await self.client.post(path, content=body, headers=headers)
            data = resp.json()
            if data.get("code") != "0":
                msg = data.get("data", [{}])[0].get("sMsg", "OKX API error") if data.get("data") else data.get("msg", "OKX error")
                return OrderResult(
                    exchange_order_id="", symbol=symbol, side=side, order_type="market",
                    quantity=quantity, price=None, filled_price=None, filled_quantity=None,
                    status="failed", error=msg,
                )
            order_data = data.get("data", [{}])[0]
            return OrderResult(
                exchange_order_id=order_data.get("ordId", ""),
                symbol=symbol, side=side, order_type="market", quantity=quantity,
                price=None, filled_price=None, filled_quantity=quantity, status="filled",
            )
        except Exception as e:
            logger.error(f"OKX market order error: {e}")
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side, order_type="market",
                quantity=quantity, price=None, filled_price=None, filled_quantity=None,
                status="failed", error="Exchange connection error",
            )

    async def place_limit_order(self, symbol: str, side: str, quantity: float, price: float) -> OrderResult:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        path = "/api/v5/trade/order"
        inst_id = symbol.upper().replace("USDT", "-USDT").replace("USD", "-USD") if "-" not in symbol else symbol
        body = f'{{"instId":"{inst_id}","tdMode":"cash","side":"{side}","ordType":"limit","sz":"{quantity}","px":"{price}"}}'
        headers = self._sign(timestamp, "POST", path, body)
        try:
            resp = await self.client.post(path, content=body, headers=headers)
            data = resp.json()
            if data.get("code") != "0":
                return OrderResult(
                    exchange_order_id="", symbol=symbol, side=side, order_type="limit",
                    quantity=quantity, price=price, filled_price=None, filled_quantity=None,
                    status="failed", error="OKX order rejected",
                )
            order_data = data.get("data", [{}])[0]
            return OrderResult(
                exchange_order_id=order_data.get("ordId", ""),
                symbol=symbol, side=side, order_type="limit", quantity=quantity,
                price=price, filled_price=None, filled_quantity=None, status="pending",
            )
        except Exception as e:
            logger.error(f"OKX limit order error: {e}")
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side, order_type="limit",
                quantity=quantity, price=price, filled_price=None, filled_quantity=None,
                status="failed", error="Exchange connection error",
            )

    async def get_balance(self, asset: str = "USDT") -> float:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        path = f"/api/v5/account/balance?ccy={asset.upper()}"
        headers = self._sign(timestamp, "GET", path)
        resp = await self.client.get(path, headers=headers)
        data = resp.json()
        for detail in data.get("data", [{}])[0].get("details", []):
            if detail.get("ccy") == asset.upper():
                return float(detail.get("availBal", 0))
        return 0.0

    async def get_ticker_price(self, symbol: str) -> float:
        inst_id = symbol.upper().replace("USDT", "-USDT").replace("USD", "-USD") if "-" not in symbol else symbol
        resp = await self.client.get(f"/api/v5/market/ticker?instId={inst_id}")
        data = resp.json()
        tickers = data.get("data", [])
        if tickers:
            return float(tickers[0].get("last", 0))
        return 0.0

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        inst_id = symbol.upper().replace("USDT", "-USDT").replace("USD", "-USD") if "-" not in symbol else symbol
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        path = "/api/v5/trade/cancel-order"
        body = f'{{"instId":"{inst_id}","ordId":"{order_id}"}}'
        headers = self._sign(timestamp, "POST", path, body)
        resp = await self.client.post(path, content=body, headers=headers)
        return resp.json().get("code") == "0"
