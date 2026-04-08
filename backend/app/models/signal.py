import enum
import uuid

from sqlalchemy import String, Enum, Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SignalAction(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"
    CLOSE = "close"


class SignalStatus(str, enum.Enum):
    ACTIVE = "active"
    CLOSED_TP = "closed_tp"
    CLOSED_SL = "closed_sl"
    CLOSED_MANUAL = "closed_manual"
    EXPIRED = "expired"


class Signal(Base):
    __tablename__ = "signals"

    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("providers.id"), index=True)
    provider: Mapped["Provider"] = relationship()

    # Signal data
    ticker: Mapped[str] = mapped_column(String(20), index=True)
    action: Mapped[SignalAction] = mapped_column(Enum(SignalAction))
    entry_price: Mapped[float] = mapped_column(Float)
    take_profit: Mapped[float | None] = mapped_column(Float)
    stop_loss: Mapped[float | None] = mapped_column(Float)
    timeframe: Mapped[str | None] = mapped_column(String(10))

    # Status
    status: Mapped[SignalStatus] = mapped_column(
        Enum(SignalStatus), default=SignalStatus.ACTIVE
    )
    close_price: Mapped[float | None] = mapped_column(Float)
    profit_pct: Mapped[float | None] = mapped_column(Float)

    # AI Rating
    ai_confidence: Mapped[float | None] = mapped_column(Float)
    ai_reasoning: Mapped[str | None] = mapped_column(Text)

    # Raw data
    raw_message: Mapped[str | None] = mapped_column(Text)
