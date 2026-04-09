import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.exchange_account import ExchangeName
from app.models.order import OrderSide, OrderStatus, OrderType


class ExchangeAccountCreate(BaseModel):
    exchange: ExchangeName
    label: str
    api_key: str
    api_secret: str
    auto_execute: bool = False
    min_confidence: float = 0.7
    max_position_pct: float = 5.0


class ExchangeAccountResponse(BaseModel):
    id: uuid.UUID
    exchange: ExchangeName
    label: str
    is_active: bool
    auto_execute: bool
    min_confidence: float
    max_position_pct: float
    created_at: datetime

    model_config = {"from_attributes": True}


class ExchangeAccountUpdate(BaseModel):
    auto_execute: bool | None = None
    min_confidence: float | None = None
    max_position_pct: float | None = None
    is_active: bool | None = None


class ExecuteRequest(BaseModel):
    exchange_account_id: uuid.UUID
    order_type: OrderType = OrderType.MARKET
    quantity: float | None = None


class OrderResponse(BaseModel):
    id: uuid.UUID
    signal_id: uuid.UUID
    exchange_account_id: uuid.UUID
    exchange_order_id: str | None
    exchange: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: float | None
    filled_price: float | None
    filled_quantity: float | None
    status: OrderStatus
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderList(BaseModel):
    items: list[OrderResponse]
    total: int
