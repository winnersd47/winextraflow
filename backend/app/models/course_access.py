"""Course Access model — tracks purchased courses and lesson progress."""

import uuid

from sqlalchemy import String, Integer, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CourseAccess(Base):
    __tablename__ = "course_access"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[str] = mapped_column(String(100), index=True)
    lessons_completed: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
