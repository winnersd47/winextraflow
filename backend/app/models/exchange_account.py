"""Exchange account model — stores encrypted API credentials per user."""

import enum
import uuid

from sqlalchemy import String, Enum, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExchangeName(str, enum.Enum):
    # ─── Paper Trading ───────────────────────────────────
    DEMO = "demo"

    # ─── Crypto ──────────────────────────────────────────
    BINANCE = "binance"
    BYBIT = "bybit"
    OKX = "okx"
    KRAKEN = "kraken"

    # ─── Forex / CFD ─────────────────────────────────────
    METATRADER5 = "metatrader5"          # MetaTrader 5 (Forex, CFD, Futures)
    INTERACTIVE_BROKERS = "interactive_brokers"  # Stocks, Options, Futures, Forex

    # ─── Stocks & Multi-asset ────────────────────────────
    TINKOFF = "tinkoff"                  # Tinkoff Invest (RU stocks, bonds, ETF)
    EXANTE = "exante"                    # EU/US stocks, options, futures


class ExchangeAccount(Base):
    __tablename__ = "exchange_accounts"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    exchange: Mapped[ExchangeName] = mapped_column(Enum(ExchangeName))
    label: Mapped[str] = mapped_column(String(100))  # e.g. "My Binance Main"

    # Encrypted with Fernet (app.config.secret_key)
    api_key_encrypted: Mapped[str] = mapped_column(Text)
    api_secret_encrypted: Mapped[str] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Route this account at the exchange's testnet: real order book, virtual funds.
    # Defaults to True so a newly connected account cannot place a real order before
    # someone deliberately turns it off — the platform has 11 measured trades and
    # none profitable, which is not a record to trade real money against.
    is_testnet: Mapped[bool] = mapped_column(Boolean, default=True)

    # Auto-execution settings per account
    auto_execute: Mapped[bool] = mapped_column(Boolean, default=False)
    min_confidence: Mapped[float] = mapped_column(default=0.7)
    max_position_pct: Mapped[float] = mapped_column(default=5.0)  # % of balance
