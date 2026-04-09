"""Referral model — tracks multi-level referral relationships and rewards."""

import enum
import uuid

from sqlalchemy import String, Enum, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ReferralStatus(str, enum.Enum):
    PENDING = "pending"      # User registered but not yet active
    ACTIVE = "active"        # Referred user is active
    REWARDED = "rewarded"    # Reward has been granted


class Referral(Base):
    __tablename__ = "referrals"

    referrer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), index=True
    )
    referred_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), index=True
    )
    level: Mapped[int] = mapped_column(Integer, default=1)  # 1=direct, 2=indirect

    status: Mapped[ReferralStatus] = mapped_column(
        Enum(ReferralStatus), default=ReferralStatus.ACTIVE
    )
    reward_type: Mapped[str | None] = mapped_column(String(50))  # "premium_days", "credits"
    reward_amount: Mapped[float | None] = mapped_column(Float)   # e.g. 7 (days) or 100 (credits)
