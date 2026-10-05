import enum

from sqlalchemy import String, Enum, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProviderSource(str, enum.Enum):
    TRADINGVIEW = "tradingview"
    TELEGRAM = "telegram"
    MANUAL = "manual"
    # MetaTrader 5 terminal via the bridge (services/mt5_bridge.py). Distinct from
    # MANUAL so the source can be shown on the signal card and counted separately:
    # it is the only source whose fills can be measured against a real broker.
    MT5 = "mt5"


class Provider(Base):
    __tablename__ = "providers"

    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    source: Mapped[ProviderSource] = mapped_column(Enum(ProviderSource))
    description: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(default=True)
    # Demo fixture from seed_data, not a real source. Every seeded provider carries
    # a win rate of 56-85% and a Sharpe of 3-13 — numbers that do not occur in
    # reality — while every real provider has win_rate NULL. Ranking by win_rate
    # therefore returned only fabricated leaders, so rankings must exclude these.
    is_seed: Mapped[bool] = mapped_column(default=False, index=True)

    # Source-specific config
    telegram_channel_id: Mapped[str | None] = mapped_column(String(100))
    tradingview_webhook_id: Mapped[str | None] = mapped_column(String(100))

    # Stats (updated by AI rating service)
    total_signals: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float | None] = mapped_column(Float)
    avg_profit: Mapped[float | None] = mapped_column(Float)
    ai_score: Mapped[float | None] = mapped_column(Float)

    # Advanced metrics (updated by enhanced AI rating)
    sharpe_ratio: Mapped[float | None] = mapped_column(Float)
    profit_factor: Mapped[float | None] = mapped_column(Float)
    max_drawdown: Mapped[float | None] = mapped_column(Float)
