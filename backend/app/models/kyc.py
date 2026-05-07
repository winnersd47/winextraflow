"""KYC verification model — photo with passport for premium access."""

import enum
import uuid

from sqlalchemy import String, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class KYCStatus(str, enum.Enum):
    NONE = "none"              # Not submitted
    PENDING = "pending"        # Submitted, awaiting admin review
    APPROVED = "approved"      # Verified by admin
    REJECTED = "rejected"      # Rejected by admin


class KYCVerification(Base):
    __tablename__ = "kyc_verifications"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    photo_path: Mapped[str] = mapped_column(String(500))  # Path to uploaded photo
    status: Mapped[KYCStatus] = mapped_column(Enum(KYCStatus), default=KYCStatus.PENDING)
    admin_comment: Mapped[str | None] = mapped_column(Text)  # Reason for rejection
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
