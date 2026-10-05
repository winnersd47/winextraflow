"""Paper (demo) trading accounts.

Every published signal is opened as a virtual position at the levels that were
actually published, sized by fixed risk, and closed at the level that settles it.
This is the honest sample the platform needs: it cannot be reinterpreted after the
fact, because the entry, target and stop are written down at open time and never
touched again.

Deliberately separate from Order/ExchangeAccount: those model real execution
against a broker. Nothing here can place a real order.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (Boolean, DateTime, Enum, Float, ForeignKey, Integer, String,
                        Text, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PaperTradeStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED_TP = "closed_tp"
    CLOSED_SL = "closed_sl"
    CANCELLED = "cancelled"        # signal expired before either level was reached


class PaperAccount(Base):
    """A virtual account. Several may run side by side with different risk."""

    __tablename__ = "paper_accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # NULL = the platform's own account, whose results ARE the measured track
    # record. Set = a user's simulator account, which must never enter that record:
    # mixing someone practising into the platform's numbers would destroy the one
    # thing the project is trying to establish. Every query that feeds the track
    # record filters on `user_id IS NULL`.
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    starting_balance: Mapped[float] = mapped_column(Float, default=100_000.0)
    balance: Mapped[float] = mapped_column(Float, default=100_000.0)
    risk_per_trade: Mapped[float] = mapped_column(Float, default=0.01)
    # Only take signals at or above this WEF score, so a low-rated stream cannot
    # bury the result of the rated one.
    min_wef: Mapped[int] = mapped_column(Integer, default=0)
    # An external demo account this mirrors, when one is connected (MT5 login,
    # Binance testnet label). Empty means internal-only.
    external_ref: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now())

    trades: Mapped[list["PaperTrade"]] = relationship(back_populates="account")


class PaperTrade(Base):
    """One virtual position. Levels are frozen at open time."""

    __tablename__ = "paper_trades"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("paper_accounts.id"), index=True)
    # Nullable: a hand-opened simulator trade belongs to no signal.
    signal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("signals.id"), index=True)
    # True when a person opened it in the web simulator rather than the pipeline
    # opening it from a published signal. Kept so the two can never be summed
    # together by accident.
    opened_manually: Mapped[bool] = mapped_column(Boolean, default=False)

    ticker: Mapped[str] = mapped_column(String(20), index=True)
    action: Mapped[str] = mapped_column(String(4))          # buy / sell
    entry_price: Mapped[float] = mapped_column(Float)
    take_profit: Mapped[float | None] = mapped_column(Float)
    stop_loss: Mapped[float | None] = mapped_column(Float)
    wef_at_open: Mapped[int | None] = mapped_column(Integer)

    position_value: Mapped[float] = mapped_column(Float)     # money committed
    units: Mapped[float] = mapped_column(Float)              # shares / contracts / coins
    risk_money: Mapped[float] = mapped_column(Float)         # what the stop costs

    status: Mapped[PaperTradeStatus] = mapped_column(
        Enum(PaperTradeStatus), default=PaperTradeStatus.OPEN, index=True
    )
    close_price: Mapped[float | None] = mapped_column(Float)
    result_pct: Mapped[float | None] = mapped_column(Float)
    result_money: Mapped[float | None] = mapped_column(Float)

    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    account: Mapped["PaperAccount"] = relationship(back_populates="trades")
