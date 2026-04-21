"""Notification model — in-app notifications for users."""

import enum
import uuid

from sqlalchemy import String, Enum, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NotificationType(str, enum.Enum):
    SIGNAL = "signal"
    TRADE = "trade"
    ACHIEVEMENT = "achievement"
    REFERRAL = "referral"
    PREMIUM = "premium"
    SYSTEM = "system"


class Notification(Base):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType))
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
