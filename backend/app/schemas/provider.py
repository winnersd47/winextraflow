import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.provider import ProviderSource


class ProviderCreate(BaseModel):
    name: str
    source: ProviderSource
    description: str | None = None
    telegram_channel_id: str | None = None
    tradingview_webhook_id: str | None = None


class ProviderResponse(BaseModel):
    id: uuid.UUID
    name: str
    source: ProviderSource
    description: str | None
    is_active: bool
    total_signals: int
    win_rate: float | None
    avg_profit: float | None
    ai_score: float | None
    sharpe_ratio: float | None
    profit_factor: float | None
    max_drawdown: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProviderList(BaseModel):
    items: list[ProviderResponse]
    total: int
