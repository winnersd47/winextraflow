"""Backtest Report model — stores backtest results as persistent reports."""

import uuid

from sqlalchemy import String, Float, Integer, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BacktestReport(Base):
    __tablename__ = "backtest_reports"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))

    # Filters used
    provider_id: Mapped[str | None] = mapped_column(String(50))
    provider_name: Mapped[str | None] = mapped_column(String(200))
    ticker: Mapped[str | None] = mapped_column(String(20))
    initial_capital: Mapped[float] = mapped_column(Float, default=10000.0)

    # Summary
    total_signals: Mapped[int] = mapped_column(Integer, default=0)
    closed_signals: Mapped[int] = mapped_column(Integer, default=0)
    total_return_pct: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    sharpe_ratio: Mapped[float | None] = mapped_column(Float)
    profit_factor: Mapped[float | None] = mapped_column(Float)
    max_drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0)
    avg_profit_pct: Mapped[float] = mapped_column(Float, default=0.0)
    avg_loss_pct: Mapped[float] = mapped_column(Float, default=0.0)
    best_trade_pct: Mapped[float] = mapped_column(Float, default=0.0)
    worst_trade_pct: Mapped[float] = mapped_column(Float, default=0.0)

    # Full data (JSON)
    equity_curve: Mapped[dict | None] = mapped_column(JSON)
