import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.signal import SignalAction, SignalStatus


class SignalCreate(BaseModel):
    provider_id: uuid.UUID
    ticker: str
    action: SignalAction
    entry_price: float
    take_profit: float | None = None
    stop_loss: float | None = None
    timeframe: str | None = None
    raw_message: str | None = None


class SignalResponse(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID
    ticker: str
    action: SignalAction
    entry_price: float
    take_profit: float | None
    stop_loss: float | None
    timeframe: str | None
    status: SignalStatus
    close_price: float | None
    profit_pct: float | None
    ai_confidence: float | None
    ai_reasoning: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SignalList(BaseModel):
    items: list[SignalResponse]
    total: int


class TradingViewWebhook(BaseModel):
    ticker: str
    action: str
    price: float
    timeframe: str | None = None
    take_profit: float | None = None
    stop_loss: float | None = None
    secret: str | None = None
