"""Order model — tracks executed trades on exchanges."""

import enum
import uuid

from sqlalchemy import String, Enum, Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OrderSide(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, enum.Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Order(Base):
    __tablename__ = "orders"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    signal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("signals.id"), index=True)
    exchange_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exchange_accounts.id"), index=True
    )

    # Exchange info
    exchange_order_id: Mapped[str | None] = mapped_column(String(100))
    exchange: Mapped[str] = mapped_column(String(20))

    # Order details
    symbol: Mapped[str] = mapped_column(String(20))
    side: Mapped[OrderSide] = mapped_column(Enum(OrderSide))
    order_type: Mapped[OrderType] = mapped_column(Enum(OrderType), default=OrderType.MARKET)
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float | None] = mapped_column(Float)  # Requested price (limit)
    filled_price: Mapped[float | None] = mapped_column(Float)  # Actual fill price
    filled_quantity: Mapped[float | None] = mapped_column(Float)

    # Status
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), default=OrderStatus.PENDING
    )
    error_message: Mapped[str | None] = mapped_column(Text)
