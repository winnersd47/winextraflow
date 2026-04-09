import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.strategy import PriceType
from app.models.subscription import SubscriptionStatus


class StrategyCreate(BaseModel):
    provider_id: uuid.UUID
    name: str
    description: str | None = None
    tags: str | None = None
    price_type: PriceType = PriceType.FREE
    price_monthly: float = 0.0


class StrategyResponse(BaseModel):
    id: uuid.UUID
    author_id: uuid.UUID
    provider_id: uuid.UUID
    name: str
    description: str | None
    tags: str | None
    is_published: bool
    price_type: PriceType
    price_monthly: float
    subscriber_count: int
    created_at: datetime

    # Provider stats (joined)
    win_rate: float | None = None
    avg_profit: float | None = None
    ai_score: float | None = None
    sharpe_ratio: float | None = None
    total_signals: int = 0

    model_config = {"from_attributes": True}


class StrategyList(BaseModel):
    items: list[StrategyResponse]
    total: int


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    strategy_id: uuid.UUID
    status: SubscriptionStatus
    auto_execute: bool
    expires_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
