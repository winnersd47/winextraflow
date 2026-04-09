"""CopyTrade model — tracks copied trades from strategy subscriptions."""

import enum
import uuid

from sqlalchemy import String, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CopyTradeStatus(str, enum.Enum):
    PENDING = "pending"
    EXECUTED = "executed"
    FAILED = "failed"
    SKIPPED = "skipped"  # Skipped due to risk check


class CopyTrade(Base):
    __tablename__ = "copy_trades"

    subscriber_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    strategy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("strategies.id"), index=True)
    signal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("signals.id"), index=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id"))

    status: Mapped[CopyTradeStatus] = mapped_column(
        Enum(CopyTradeStatus), default=CopyTradeStatus.PENDING
    )
    error_message: Mapped[str | None] = mapped_column(String(500))
