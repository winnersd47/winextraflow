import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Enum, Float, ForeignKey, Integer, Text
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
    # The source's own far target when it is an annual price forecast. take_profit
    # holds the tradable near target instead (see services/signal_levels.py).
    long_target: Mapped[float | None] = mapped_column(Float)

    # Status
    status: Mapped[SignalStatus] = mapped_column(
        Enum(SignalStatus), default=SignalStatus.ACTIVE
    )
    close_price: Mapped[float | None] = mapped_column(Float)
    profit_pct: Mapped[float | None] = mapped_column(Float)
    # When the trade actually settled. `ai_rating._score_time_decay` used
    # `updated_at` for this, which is the last time ANY column was written — so a
    # backfill script that filled in missing P&L made eleven months-old closes
    # look like they had all just happened, and the "recent 30 days" window
    # silently became "rows edited in the last 30 days". Left NULL on the
    # historical closes, where the real date is no longer recoverable; the factor
    # reports itself unmeasured for those rather than guessing.
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set when a row must not count toward the measured record — currently only
    # exact duplicates of another closed signal. The row is kept rather than
    # deleted: a measured outcome is the scarcest thing this project owns, and a
    # DELETE leaves no trace of what was removed or why. Anything that feeds a
    # public number filters on this being NULL; see `not_excluded()` in
    # services/signal_quality.py.
    excluded_reason: Mapped[str | None] = mapped_column(String(120))

    # AI Rating
    ai_confidence: Mapped[float | None] = mapped_column(Float)
    ai_reasoning: Mapped[str | None] = mapped_column(Text)

    # The source's own confidence, 0..1 — currently the MT5 bridge model's
    # self-assessment. Stored separately from ai_confidence (our WEF Score) and
    # deliberately NOT part of it: nobody has checked that 0.7 means seven wins in
    # ten. scripts/wef_validation.py buckets outcomes by this so it can earn a place
    # in the score, or be shown not to deserve one.
    source_confidence: Mapped[float | None] = mapped_column(Float)

    # Telegram post ids, so the result can be published as a reply to the signal
    # itself instead of an unanchored message in the feed.
    tg_vip_message_id: Mapped[int | None] = mapped_column(Integer)
    tg_free_message_id: Mapped[int | None] = mapped_column(Integer)

    # Raw data
    raw_message: Mapped[str | None] = mapped_column(Text)
