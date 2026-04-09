import enum

from sqlalchemy import String, Enum, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProviderSource(str, enum.Enum):
    TRADINGVIEW = "tradingview"
    TELEGRAM = "telegram"
    MANUAL = "manual"


class Provider(Base):
    __tablename__ = "providers"

    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    source: Mapped[ProviderSource] = mapped_column(Enum(ProviderSource))
    description: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(default=True)

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
