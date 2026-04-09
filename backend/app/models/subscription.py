"""Subscription model — user subscriptions to strategies."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import String, Enum, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Subscription(Base):
    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    strategy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("strategies.id"), index=True)

    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE
    )
    auto_execute: Mapped[bool] = mapped_column(Boolean, default=False)

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
