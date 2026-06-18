"""Price Alerts — user-defined conditions for notifications."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String, Boolean
from app.database import Base


class PriceAlert(Base):
    __tablename__ = "price_alerts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    ticker = Column(String, nullable=False, index=True)
    condition = Column(String, nullable=False)  # "above" or "below"
    target_price = Column(Float, nullable=False)
    note = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_triggered = Column(Boolean, default=False)
    triggered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
