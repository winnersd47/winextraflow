"""Trading Journal — personal trade diary with notes and stats."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.sqlite import JSON
from app.database import Base


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    signal_id = Column(String, ForeignKey("signals.id"), nullable=True)

    # Trade details
    ticker = Column(String, nullable=False)
    action = Column(String, nullable=False)  # buy / sell
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    quantity = Column(Float, nullable=True)
    profit_pct = Column(Float, nullable=True)
    profit_abs = Column(Float, nullable=True)  # absolute profit in currency

    # User notes
    note = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True)  # ["scalp", "swing", "moex"]
    emotion = Column(String, nullable=True)  # confident, nervous, fomo, disciplined
    rating = Column(Float, nullable=True)  # 1-5 self-rating

    # Timestamps
    opened_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
