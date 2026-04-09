"""Backtesting engine — simulate signal performance on historical data.

Takes a set of signals (by provider, ticker, or date range) and calculates
portfolio-level metrics: total return, win rate, Sharpe, drawdown, profit factor.
"""

import math
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal import Signal, SignalAction, SignalStatus

logger = logging.getLogger(__name__)

RISK_FREE_RATE_DAILY = 0.05 / 365


@dataclass
class TradeResult:
    """Result of a single simulated trade."""

    signal_id: str
    ticker: str
    action: str
    entry_price: float
    close_price: float
    profit_pct: float
    status: str
    created_at: str


@dataclass
class BacktestResult:
    """Complete backtesting report."""

    # Request info
    provider_id: str | None
    ticker: str | None
    date_from: str | None
    date_to: str | None

    # Summary
    total_signals: int = 0
    closed_signals: int = 0
    active_signals: int = 0
    expired_signals: int = 0

    # Performance
    total_return_pct: float = 0.0
    win_rate: float = 0.0
    avg_profit_pct: float = 0.0
    avg_loss_pct: float = 0.0
    best_trade_pct: float = 0.0
    worst_trade_pct: float = 0.0

    # Risk metrics
    sharpe_ratio: float | None = None
    profit_factor: float | None = None
    max_drawdown_pct: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0

    # Trade list
    trades: list[TradeResult] = field(default_factory=list)

    # Equity curve (cumulative returns)
    equity_curve: list[float] = field(default_factory=list)


class BacktestingEngine:
    """Simulates trading based on historical signals."""

    async def run_backtest(
        self,
        db: AsyncSession,
        *,
        provider_id: uuid.UUID | None = None,
        ticker: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        initial_capital: float = 10000.0,
    ) -> BacktestResult:
        """Run a backtest on a filtered set of signals.

        Includes only closed signals (TP, SL, MANUAL) that have profit_pct.
        Active and expired signals are counted but not included in metrics.
        """
        result = BacktestResult(
            provider_id=str(provider_id) if provider_id else None,
            ticker=ticker,
            date_from=date_from.isoformat() if date_from else None,
            date_to=date_to.isoformat() if date_to else None,
        )

        # Build query
        query = select(Signal).order_by(Signal.created_at)
        conditions = []

        if provider_id:
            conditions.append(Signal.provider_id == provider_id)
        if ticker:
            conditions.append(Signal.ticker == ticker.upper())
        if date_from:
            conditions.append(Signal.created_at >= date_from)
        if date_to:
            conditions.append(Signal.created_at <= date_to)

        if conditions:
            query = query.where(and_(*conditions))

        signals = (await db.execute(query)).scalars().all()
        result.total_signals = len(signals)

        if not signals:
            return result

        # Separate by status
        closed_statuses = {SignalStatus.CLOSED_TP, SignalStatus.CLOSED_SL, SignalStatus.CLOSED_MANUAL}
        closed_signals = [s for s in signals if s.status in closed_statuses and s.profit_pct is not None]
        result.closed_signals = len(closed_signals)
        result.active_signals = sum(1 for s in signals if s.status == SignalStatus.ACTIVE)
        result.expired_signals = sum(1 for s in signals if s.status == SignalStatus.EXPIRED)

        if not closed_signals:
            return result

        # ── Calculate trades ──
        profits = []
        wins = 0
        total_profit = 0.0
        total_loss = 0.0

        for sig in closed_signals:
            trade = TradeResult(
                signal_id=str(sig.id),
                ticker=sig.ticker,
                action=sig.action.value,
                entry_price=sig.entry_price,
                close_price=sig.close_price or sig.entry_price,
                profit_pct=sig.profit_pct,
                status=sig.status.value,
                created_at=sig.created_at.isoformat() if sig.created_at else "",
            )
            result.trades.append(trade)
            profits.append(sig.profit_pct)

            if sig.profit_pct >= 0:
                wins += 1
                total_profit += sig.profit_pct
            else:
                total_loss += abs(sig.profit_pct)

        # ── Summary metrics ──
        n = len(profits)
        result.win_rate = wins / n if n > 0 else 0
        result.total_return_pct = round(sum(profits), 2)
        result.avg_profit_pct = round(
            total_profit / wins if wins > 0 else 0, 2
        )
        result.avg_loss_pct = round(
            -total_loss / (n - wins) if (n - wins) > 0 else 0, 2
        )
        result.best_trade_pct = round(max(profits), 2)
        result.worst_trade_pct = round(min(profits), 2)

        # ── Sharpe Ratio ──
        if n >= 3:
            mean_r = sum(profits) / n
            stddev = math.sqrt(sum((p - mean_r) ** 2 for p in profits) / n)
            if stddev > 0:
                result.sharpe_ratio = round(
                    (mean_r - RISK_FREE_RATE_DAILY * 100) / stddev * math.sqrt(252), 2
                )
            else:
                result.sharpe_ratio = 0.0

        # ── Profit Factor ──
        if total_loss > 0:
            result.profit_factor = round(total_profit / total_loss, 2)
        elif total_profit > 0:
            result.profit_factor = 10.0

        # ── Max Drawdown ──
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        equity = [initial_capital]

        for p in profits:
            cumulative += p
            capital = initial_capital * (1 + cumulative / 100)
            equity.append(round(capital, 2))
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd

        result.max_drawdown_pct = round(-max_dd, 2)
        result.equity_curve = equity

        # ── Consecutive wins/losses ──
        max_w = 0
        max_l = 0
        curr_w = 0
        curr_l = 0
        for p in profits:
            if p >= 0:
                curr_w += 1
                curr_l = 0
                max_w = max(max_w, curr_w)
            else:
                curr_l += 1
                curr_w = 0
                max_l = max(max_l, curr_l)

        result.max_consecutive_wins = max_w
        result.max_consecutive_losses = max_l

        logger.info(
            f"Backtest complete: {n} trades, return={result.total_return_pct}%, "
            f"sharpe={result.sharpe_ratio}, wr={result.win_rate:.0%}"
        )
        return result


backtesting_engine = BacktestingEngine()
