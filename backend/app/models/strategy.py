"""Strategy model — publishable trading strategy on the marketplace."""

import enum
import uuid

from sqlalchemy import String, Enum, Float, Integer, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PriceType(str, enum.Enum):
    FREE = "free"
    PREMIUM = "premium"  # Requires platform premium subscription
    PAID = "paid"        # Monthly fee to strategy author


class Strategy(Base):
    __tablename__ = "strategies"

    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("providers.id"), unique=True)

    name: Mapped[str] = mapped_column(String(150), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[str | None] = mapped_column(String(500))  # comma-separated: "crypto,scalping,btc"

    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    price_type: Mapped[PriceType] = mapped_column(Enum(PriceType), default=PriceType.FREE)
    price_monthly: Mapped[float] = mapped_column(Float, default=0.0)  # USD for PAID type

    subscriber_count: Mapped[int] = mapped_column(Integer, default=0)
