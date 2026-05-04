"""Payment model — tracks Stripe payments for Premium subscriptions."""

import enum
import uuid

from sqlalchemy import String, Enum, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PaymentPlan(str, enum.Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class Payment(Base):
    __tablename__ = "payments"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    stripe_session_id: Mapped[str | None] = mapped_column(String(200), unique=True)
    stripe_payment_id: Mapped[str | None] = mapped_column(String(200))
    plan: Mapped[PaymentPlan] = mapped_column(Enum(PaymentPlan))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="usd")
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus), default=PaymentStatus.PENDING
    )
