"""Exchange account model — stores encrypted API credentials per user."""

import enum
import uuid

from sqlalchemy import String, Enum, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExchangeName(str, enum.Enum):
    BINANCE = "binance"
    BYBIT = "bybit"
    DEMO = "demo"


class ExchangeAccount(Base):
    __tablename__ = "exchange_accounts"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    exchange: Mapped[ExchangeName] = mapped_column(Enum(ExchangeName))
    label: Mapped[str] = mapped_column(String(100))  # e.g. "My Binance Main"

    # Encrypted with Fernet (app.config.secret_key)
    api_key_encrypted: Mapped[str] = mapped_column(Text)
    api_secret_encrypted: Mapped[str] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Auto-execution settings per account
    auto_execute: Mapped[bool] = mapped_column(Boolean, default=False)
    min_confidence: Mapped[float] = mapped_column(default=0.7)
    max_position_pct: Mapped[float] = mapped_column(default=5.0)  # % of balance
