"""MEXC exchange adapter — crypto spot trading via the v3 REST API.

MEXC earned a place here by answering the Russian network directly, which is
where this deploys and who it is for: measured 2026-10-29, quotes and candles
return 200 in ~0.5-1.1s with no proxy, while Binance has withdrawn from that
market. The same reachability already made it the third price source in
services/live_price.py.

**There is no spot testnet.** `api-testnet.mexc.com` and `api-sandbox.mexc.com`
do not resolve (checked 2026-10-29); only the futures host has one, and this is
a spot adapter. So this class deliberately takes no `testnet` argument — which
is not an oversight but the safety mechanism:

    execution._get_adapter calls `adapter_cls(key, secret, testnet=...)`, and on
    TypeError falls back to DemoAdapter for any account marked virtual.

An account the user created as paper therefore cannot reach real MEXC by
accident. Giving this class a `testnet` flag it could not honour would defeat
that, and routing virtual orders to the live book is the one mistake that costs
real money.

Auth is Binance-shaped: HMAC-SHA256 over the query string, key in a header.
The differences that matter are in `_sign` and `get_balance`.
"""

import hashlib
import hmac
import logging
import time
from urllib.parse import urlencode

import httpx

from app.services.exchanges.base import BaseExchangeAdapter, OrderResult

logger = logging.getLogger(__name__)

MEXC_BASE_URL = "https://api.mexc.com"

# MEXC rejects a request whose timestamp drifts outside this window. The default
# is 5s; 5000ms is the documented maximum this field accepts.
RECV_WINDOW_MS = 5000


class MexcAdapter(BaseExchangeAdapter):
    """MEXC v3 spot adapter. Live keys only — see the module docstring."""

    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        self.client = httpx.AsyncClient(
            base_url=MEXC_BASE_URL,
            headers={"X-MEXC-APIKEY": api_key,
                     "Content-Type": "application/json"},
            timeout=30.0,
        )

    def _sign(self, params: dict) -> dict:
        """Timestamp + HMAC-SHA256 over the encoded query, signature appended.

        The signature covers the query string EXACTLY as it is sent, so the
        signed string and the request must be built from the same ordered
        mapping — re-encoding afterwards with a different key order produces a
        valid-looking request that the exchange rejects as unauthorised.
        """
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = RECV_WINDOW_MS
        query = urlencode(params)
        params["signature"] = hmac.new(
            self.api_secret.encode(), query.encode(), hashlib.sha256
        ).hexdigest()
        return params

    def _failed(self, symbol: str, side: str, kind: str, quantity: float,
                price: float | None, error: str) -> OrderResult:
        return OrderResult(
            exchange_order_id="", symbol=symbol, side=side, order_type=kind,
            quantity=quantity, price=price, filled_price=None,
            filled_quantity=None, status="failed", error=error,
        )

    @staticmethod
    def _error_text(data: dict) -> str:
        """MEXC reports failures as {"code": -1121, "msg": "..."}."""
        if isinstance(data, dict) and data.get("msg"):
            return f"MEXC {data.get('code', '')}: {data['msg']}".strip()
        return "MEXC API error"

    async def place_market_order(self, symbol: str, side: str,
                                 quantity: float) -> OrderResult:
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
                # Most often a precision or minimum-notional rejection: MEXC
                # requires the quantity to match the symbol's step size, which
                # /api/v3/exchangeInfo publishes. Surface the exchange's own
                # wording rather than a generic failure.
                return self._failed(symbol, side, "market", quantity, None,
                                    self._error_text(data))
            # A filled market order reports cummulativeQuoteQty and executedQty;
            # the average fill is the first divided by the second. Reporting the
            # requested quantity as if it were the fill is how slippage hides.
            executed = float(data.get("executedQty") or 0)
            quote = float(data.get("cummulativeQuoteQty") or 0)
            avg = quote / executed if executed else None
            return OrderResult(
                exchange_order_id=str(data.get("orderId", "")),
                symbol=symbol, side=side, order_type="market", quantity=quantity,
                price=None, filled_price=avg,
                filled_quantity=executed or None,
                status="filled" if executed else "pending",
            )
        except Exception as e:
            logger.error(f"MEXC market order error: {e}")
            return self._failed(symbol, side, "market", quantity, None,
                                "Exchange connection error")

    async def place_limit_order(self, symbol: str, side: str, quantity: float,
                                price: float) -> OrderResult:
        params = self._sign({
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": "LIMIT",
            "quantity": str(quantity),
            "price": str(price),
            "timeInForce": "GTC",
        })
        try:
            resp = await self.client.post("/api/v3/order", params=params)
            data = resp.json()
            if resp.status_code != 200:
                return self._failed(symbol, side, "limit", quantity, price,
                                    self._error_text(data))
            executed = float(data.get("executedQty") or 0)
            return OrderResult(
                exchange_order_id=str(data.get("orderId", "")),
                symbol=symbol, side=side, order_type="limit", quantity=quantity,
                price=price, filled_price=None,
                filled_quantity=executed or None,
                status="filled" if executed >= quantity > 0 else "pending",
            )
        except Exception as e:
            logger.error(f"MEXC limit order error: {e}")
            return self._failed(symbol, side, "limit", quantity, price,
                                "Exchange connection error")

    async def get_balance(self, asset: str = "USDT") -> float:
        """Free balance for one asset. 0.0 when the account cannot be read.

        `/api/v3/account` returns every balance as {asset, free, locked}; `free`
        is what can be spent. `locked` sits in open orders and counting it would
        let the sizer stake money that is already committed.
        """
        try:
            resp = await self.client.get("/api/v3/account", params=self._sign({}))
            data = resp.json()
            if resp.status_code != 200:
                logger.warning(f"MEXC balance: {self._error_text(data)}")
                return 0.0
            for row in data.get("balances") or []:
                if (row.get("asset") or "").upper() == asset.upper():
                    return float(row.get("free") or 0)
            return 0.0
        except Exception as e:
            logger.error(f"MEXC balance error: {e}")
            return 0.0

    async def get_ticker_price(self, symbol: str) -> float:
        """Last price, 0.0 when unavailable — public, needs no key."""
        try:
            resp = await self.client.get("/api/v3/ticker/price",
                                         params={"symbol": symbol.upper()})
            if resp.status_code != 200:
                logger.info(f"MEXC price {symbol}: HTTP {resp.status_code}")
                return 0.0
            data = resp.json()
            return float(data.get("price") or 0) if isinstance(data, dict) else 0.0
        except Exception as e:
            logger.error(f"MEXC ticker error: {e}")
            return 0.0

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        try:
            resp = await self.client.delete("/api/v3/order", params=self._sign({
                "symbol": symbol.upper(), "orderId": str(order_id),
            }))
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"MEXC cancel error: {e}")
            return False
