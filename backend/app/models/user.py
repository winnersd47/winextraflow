import enum
import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, Enum, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    USER = "user"
    PREMIUM = "premium"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.USER
    )

    # Premium
    premium_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Referral
    referral_code: Mapped[str | None] = mapped_column(String(20), unique=True)
    referred_by: Mapped[uuid.UUID | None] = mapped_column()
