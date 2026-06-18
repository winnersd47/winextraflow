"""Feedback system — reviews, feature requests, bug reports, NPS."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, Boolean
from sqlalchemy.dialects.sqlite import JSON
from app.database import Base


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    username = Column(String, nullable=False)

    # Type: review, feature_request, bug_report, suggestion, nps
    type = Column(String, nullable=False, index=True)

    # NPS score (0-10, only for type=nps)
    nps_score = Column(Integer, nullable=True)

    # Star rating (1-5, for reviews)
    rating = Column(Integer, nullable=True)

    # Content
    title = Column(String, nullable=True)
    text = Column(Text, nullable=False)

    # Categorization
    category = Column(String, nullable=True)  # signals, backtest, portfolio, ai, payments, ui, other
    page = Column(String, nullable=True)  # which page the feedback was submitted from
    priority = Column(String, default="normal")  # low, normal, high, critical

    # Admin response
    admin_reply = Column(Text, nullable=True)
    admin_reply_at = Column(DateTime, nullable=True)
    status = Column(String, default="new")  # new, reviewed, in_progress, resolved, wont_fix

    # Votes (other users can upvote)
    upvotes = Column(Integer, default=0)
    upvoted_by = Column(JSON, default=list)

    # Meta
    is_public = Column(Boolean, default=True)
    browser_info = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
