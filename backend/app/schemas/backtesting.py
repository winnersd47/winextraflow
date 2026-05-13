import uuid
from datetime import datetime

from pydantic import BaseModel


class BacktestRequest(BaseModel):
    provider_id: uuid.UUID | None = None
    ticker: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    initial_capital: float = 10000.0

    def model_post_init(self, __context: object) -> None:
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if self.initial_capital > 100_000_000:
            raise ValueError("initial_capital too large")


class TradeResultSchema(BaseModel):
    signal_id: str
    ticker: str
    action: str
    entry_price: float
    close_price: float
    profit_pct: float
    status: str
    created_at: str


class BacktestResponse(BaseModel):
    # Request
    provider_id: str | None
    ticker: str | None
    date_from: str | None
    date_to: str | None

    # Summary
    total_signals: int
    closed_signals: int
    active_signals: int
    expired_signals: int

    # Performance
    total_return_pct: float
    win_rate: float
    avg_profit_pct: float
    avg_loss_pct: float
    best_trade_pct: float
    worst_trade_pct: float

    # Risk
    sharpe_ratio: float | None
    profit_factor: float | None
    max_drawdown_pct: float
    max_consecutive_wins: int
    max_consecutive_losses: int

    # Detail
    trades: list[TradeResultSchema]
    equity_curve: list[float]
