"""Tinkoff Invest adapter — Russian stocks, bonds, ETF, currencies, futures.

Tinkoff Invest is the largest retail broker in Russia (30M+ clients).
API docs: https://tinkoff.github.io/investAPI/
Supports: Moscow Exchange (MOEX), SPB Exchange, OTC bonds, currencies.

api_key = Tinkoff Invest API token
api_secret = account_id (broker account ID)
"""

import logging

import httpx

from app.services.exchanges.base import BaseExchangeAdapter, OrderResult

logger = logging.getLogger(__name__)

TINKOFF_BASE_URL = "https://invest-public-api.tinkoff.ru/rest"


class TinkoffAdapter(BaseExchangeAdapter):
    """Tinkoff Invest REST API adapter."""

    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        self.account_id = api_secret  # account ID stored as secret
        self.client = httpx.AsyncClient(
            base_url=TINKOFF_BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def place_market_order(self, symbol: str, side: str, quantity: float) -> OrderResult:
        figi = await self._resolve_figi(symbol)
        if not figi:
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side, order_type="market",
                quantity=quantity, price=None, filled_price=None, filled_quantity=None,
                status="failed", error=f"Cannot resolve FIGI for {symbol}",
            )
        direction = 1 if side == "buy" else 2  # ORDER_DIRECTION_BUY=1, SELL=2
        payload = {
            "figi": figi,
            "quantity": str(int(quantity)),
            "direction": direction,
            "accountId": self.account_id,
            "orderType": 2,  # ORDER_TYPE_MARKET
        }
        try:
            resp = await self.client.post(
                "/tinkoff.public.invest.api.contract.v1.OrdersService/PostOrder",
                json=payload,
            )
            data = resp.json()
            if data.get("orderId"):
                price_val = None
                if data.get("executedOrderPrice"):
                    units = int(data["executedOrderPrice"].get("units", 0))
                    nano = int(data["executedOrderPrice"].get("nano", 0))
                    price_val = units + nano / 1e9
                return OrderResult(
                    exchange_order_id=data["orderId"],
                    symbol=symbol, side=side, order_type="market", quantity=quantity,
                    price=price_val, filled_price=price_val, filled_quantity=quantity,
                    status="filled",
                )
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side, order_type="market",
                quantity=quantity, price=None, filled_price=None, filled_quantity=None,
                status="failed", error=data.get("message", "Tinkoff order rejected"),
            )
        except Exception as e:
            logger.error(f"Tinkoff market order error: {e}")
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side, order_type="market",
                quantity=quantity, price=None, filled_price=None, filled_quantity=None,
                status="failed", error="Exchange connection error",
            )

    async def place_limit_order(self, symbol: str, side: str, quantity: float, price: float) -> OrderResult:
        figi = await self._resolve_figi(symbol)
        if not figi:
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side, order_type="limit",
                quantity=quantity, price=price, filled_price=None, filled_quantity=None,
                status="failed", error=f"Cannot resolve FIGI for {symbol}",
            )
        direction = 1 if side == "buy" else 2
        units = int(price)
        nano = int((price - units) * 1e9)
        payload = {
            "figi": figi,
            "quantity": str(int(quantity)),
            "price": {"units": str(units), "nano": nano},
            "direction": direction,
            "accountId": self.account_id,
            "orderType": 1,  # ORDER_TYPE_LIMIT
        }
        try:
            resp = await self.client.post(
                "/tinkoff.public.invest.api.contract.v1.OrdersService/PostOrder",
                json=payload,
            )
            data = resp.json()
            if data.get("orderId"):
                return OrderResult(
                    exchange_order_id=data["orderId"],
                    symbol=symbol, side=side, order_type="limit", quantity=quantity,
                    price=price, filled_price=None, filled_quantity=None, status="pending",
                )
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side, order_type="limit",
                quantity=quantity, price=price, filled_price=None, filled_quantity=None,
                status="failed", error=data.get("message", "Tinkoff order rejected"),
            )
        except Exception as e:
            logger.error(f"Tinkoff limit order error: {e}")
            return OrderResult(
                exchange_order_id="", symbol=symbol, side=side, order_type="limit",
                quantity=quantity, price=price, filled_price=None, filled_quantity=None,
                status="failed", error="Exchange connection error",
            )

    async def get_balance(self, asset: str = "RUB") -> float:
        try:
            resp = await self.client.post(
                "/tinkoff.public.invest.api.contract.v1.OperationsService/GetPortfolio",
                json={"accountId": self.account_id},
            )
            data = resp.json()
            for pos in data.get("positions", []):
                if pos.get("instrumentType") == "currency":
                    curr = pos.get("currentPrice", {})
                    units = int(curr.get("units", 0))
                    nano = int(curr.get("nano", 0))
                    qty = float(pos.get("quantity", {}).get("units", 0))
                    if qty > 0:
                        return qty * (units + nano / 1e9)
            # Fallback: total portfolio amount
            total = data.get("totalAmountCurrencies", {})
            return float(total.get("units", 0)) + float(total.get("nano", 0)) / 1e9
        except Exception:
            return 0.0

    async def get_ticker_price(self, symbol: str) -> float:
        figi = await self._resolve_figi(symbol)
        if not figi:
            return 0.0
        try:
            resp = await self.client.post(
                "/tinkoff.public.invest.api.contract.v1.MarketDataService/GetLastPrices",
                json={"figi": [figi]},
            )
            data = resp.json()
            prices = data.get("lastPrices", [])
            if prices:
                p = prices[0].get("price", {})
                return float(p.get("units", 0)) + float(p.get("nano", 0)) / 1e9
        except Exception:
            pass
        return 0.0

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        try:
            resp = await self.client.post(
                "/tinkoff.public.invest.api.contract.v1.OrdersService/CancelOrder",
                json={"accountId": self.account_id, "orderId": order_id},
            )
            return resp.status_code == 200
        except Exception:
            return False

    async def _resolve_figi(self, symbol: str) -> str | None:
        """Resolve ticker to FIGI (Financial Instrument Global Identifier)."""
        try:
            resp = await self.client.post(
                "/tinkoff.public.invest.api.contract.v1.InstrumentsService/FindInstrument",
                json={"query": symbol, "instrumentKind": 0},
            )
            data = resp.json()
            instruments = data.get("instruments", [])
            if instruments:
                return instruments[0].get("figi")
        except Exception:
            pass
        return None
