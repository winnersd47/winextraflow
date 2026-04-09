import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.copy_trade import CopyTradeStatus


class CopyTradeResponse(BaseModel):
    id: uuid.UUID
    subscriber_id: uuid.UUID
    strategy_id: uuid.UUID
    signal_id: uuid.UUID
    order_id: uuid.UUID | None
    status: CopyTradeStatus
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CopyTradeList(BaseModel):
    items: list[CopyTradeResponse]
    total: int


class CopyTradingStatus(BaseModel):
    enabled: bool
    active_subscriptions: int
    auto_execute_accounts: int
    total_copied_trades: int
    successful_trades: int
    failed_trades: int
