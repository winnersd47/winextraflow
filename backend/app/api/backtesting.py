from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.signal import Signal
from app.models.backtest_report import BacktestReport
from app.schemas.backtesting import BacktestRequest, BacktestResponse
from app.services.backtesting import backtesting_engine
from app.services.backtesting_real import (
    run_real_backtest, detect_source, fetch_candles,
    compute_monthly_breakdown, compute_buy_and_hold, run_monte_carlo,
    apply_commission, apply_position_sizing, SimTrade,
)
from app.services.premium import is_premium

router = APIRouter()

FREE_DAILY_LIMIT = 1


@router.post("", response_model=BacktestResponse)
async def run_backtest(
    data: BacktestRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run a backtest and save report to history."""
    # Rate limit for free users
    if not is_premium(user):
        from app.models.notification import Notification
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        backtest_count = (await db.execute(
            select(func.count()).select_from(Notification).where(and_(
                Notification.user_id == user.id,
                Notification.type == "backtest_run",
                Notification.created_at >= today_start,
            ))
        )).scalar() or 0
        if backtest_count >= FREE_DAILY_LIMIT:
            raise HTTPException(429, "Free users can run 1 backtest per day. Upgrade to Premium for unlimited backtesting.")

    result = await backtesting_engine.run_backtest(
        db,
        provider_id=data.provider_id,
        ticker=data.ticker,
        date_from=data.date_from,
        date_to=data.date_to,
        initial_capital=data.initial_capital,
    )

    # Build title
    title_parts = []
    provider_name = None
    if data.provider_id:
        from app.models.provider import Provider
        prov = await db.get(Provider, data.provider_id)
        if prov:
            provider_name = prov.name
            title_parts.append(prov.name.replace("[TEST] ", ""))
    if data.ticker:
        title_parts.append(data.ticker.upper())
    if not title_parts:
        title_parts.append("All signals")
    title = " | ".join(title_parts) + f" — WR {result.win_rate*100:.0f}%, {result.total_return_pct:+.1f}%"

    # Save report
    report = BacktestReport(
        user_id=user.id,
        title=title,
        provider_id=str(data.provider_id) if data.provider_id else None,
        provider_name=provider_name,
        ticker=data.ticker,
        initial_capital=data.initial_capital,
        total_signals=result.total_signals,
        closed_signals=result.closed_signals,
        total_return_pct=result.total_return_pct,
        win_rate=result.win_rate,
        sharpe_ratio=result.sharpe_ratio,
        profit_factor=result.profit_factor,
        max_drawdown_pct=result.max_drawdown_pct,
        avg_profit_pct=result.avg_profit_pct,
        avg_loss_pct=result.avg_loss_pct,
        best_trade_pct=result.best_trade_pct,
        worst_trade_pct=result.worst_trade_pct,
        equity_curve=result.equity_curve,
    )
    db.add(report)

    # Track for rate limiting
    if not is_premium(user):
        from app.models.notification import Notification
        db.add(Notification(
            user_id=user.id,
            type="backtest_run",
            title="Backtest",
            message=f"Backtest: {title}",
        ))

    await db.commit()

    # Achievement
    try:
        from app.services.achievements import achievement_service
        await achievement_service.increment_progress(db, user.id, "first_backtest")
    except Exception:
        pass  # Non-critical

    return result


@router.get("/history")
async def backtest_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get backtest report history for the current user."""
    total = (await db.execute(
        select(func.count()).select_from(BacktestReport).where(BacktestReport.user_id == user.id)
    )).scalar() or 0

    result = await db.execute(
        select(BacktestReport)
        .where(BacktestReport.user_id == user.id)
        .order_by(BacktestReport.created_at.desc())
        .offset(skip).limit(limit)
    )
    reports = result.scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": str(r.id),
                "title": r.title,
                "provider_name": r.provider_name,
                "ticker": r.ticker,
                "initial_capital": r.initial_capital,
                "total_signals": r.total_signals,
                "closed_signals": r.closed_signals,
                "total_return_pct": r.total_return_pct,
                "win_rate": r.win_rate,
                "sharpe_ratio": r.sharpe_ratio,
                "profit_factor": r.profit_factor,
                "max_drawdown_pct": r.max_drawdown_pct,
                "avg_profit_pct": r.avg_profit_pct,
                "avg_loss_pct": r.avg_loss_pct,
                "best_trade_pct": r.best_trade_pct,
                "worst_trade_pct": r.worst_trade_pct,
                "equity_curve": r.equity_curve,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reports
        ],
    }


# ═══ REAL BACKTEST — on actual candles ═══

class RealBacktestRequest(BaseModel):
    ticker: str
    days: int = 180  # lookback period
    max_bars_per_trade: int = 30
    min_wef_score: float = 0.0  # filter: only signals with WEF >= this
    commission_pct: float = 0.1  # exchange commission per trade (%)
    position_size_pct: float = 10.0  # % of capital per trade


@router.post("/real")
async def real_backtest(
    data: RealBacktestRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run backtest on REAL candles from MOEX ISS or Binance API.

    Fetches actual OHLCV data and simulates each signal bar-by-bar:
    - Checks if price hit TP or SL
    - Calculates real P&L
    - Returns equity curve, Sharpe, drawdown, profit factor
    """
    ticker = data.ticker.upper()
    source = detect_source(ticker)

    # source "stocks" is fallback to Yahoo Finance — always works
    _ = source  # just for logging

    date_from = (datetime.now(timezone.utc) - timedelta(days=data.days)).strftime("%Y-%m-%d")
    date_to = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Get signals for this ticker (with optional WEF Score filter)
    stmt = (
        select(Signal)
        .where(
            Signal.ticker == ticker,
            Signal.entry_price > 0,
            Signal.take_profit.isnot(None),
        )
        .order_by(Signal.created_at)
    )
    if data.min_wef_score > 0:
        stmt = stmt.where(Signal.ai_confidence >= data.min_wef_score)

    signals_db = (await db.execute(stmt)).scalars().all()

    if not signals_db:
        raise HTTPException(404, f"No signals found for {ticker}" + (f" with WEF >= {data.min_wef_score}" if data.min_wef_score > 0 else ""))

    # Convert to dicts
    signals = [
        {
            "id": str(s.id),
            "action": s.action.value if hasattr(s.action, "value") else str(s.action),
            "entry_price": s.entry_price,
            "take_profit": s.take_profit,
            "stop_loss": s.stop_loss,
            "created_at": s.created_at.isoformat() if s.created_at else "",
            "wef_score": s.ai_confidence,
        }
        for s in signals_db
    ]

    result = await run_real_backtest(
        ticker=ticker,
        signals=signals,
        date_from=date_from,
        date_to=date_to,
        max_bars_per_trade=data.max_bars_per_trade,
    )

    # ── Extended analytics ──
    raw_profits = [t["profit_pct"] for t in result.trades]

    # Apply commission
    adjusted_profits = apply_commission(raw_profits, data.commission_pct)

    # Apply position sizing
    sized_profits = apply_position_sizing(adjusted_profits, data.position_size_pct)

    # Monthly breakdown
    sim_trades = [
        SimTrade(
            ticker=t["ticker"], action=t["action"],
            entry_price=t["entry"], exit_price=t["exit"],
            take_profit=t["tp"], stop_loss=t["sl"],
            profit_pct=t["profit_pct"], bars_held=t["bars_held"],
            entry_date=t["entry_date"], exit_date=t["exit_date"],
            exit_reason=t["exit_reason"],
        )
        for t in result.trades
    ]
    monthly = compute_monthly_breakdown(sim_trades)

    # Buy & Hold benchmark
    candles = await fetch_candles(ticker, date_from, date_to)
    buy_hold = compute_buy_and_hold(candles)

    # Monte Carlo (1000 simulations)
    monte_carlo = run_monte_carlo(adjusted_profits) if len(adjusted_profits) >= 3 else None

    # Adjusted metrics (after commission + position sizing)
    adj_return = round(sum(sized_profits), 2)
    adj_win_rate = round(sum(1 for p in adjusted_profits if p >= 0) / len(adjusted_profits), 3) if adjusted_profits else 0

    return {
        "ticker": result.ticker,
        "source": result.source,
        "date_from": result.date_from,
        "date_to": result.date_to,
        "candles_loaded": result.candles_loaded,
        "total_signals": result.total_signals,
        "filtered_by_wef": data.min_wef_score > 0,
        "min_wef_score": data.min_wef_score,
        "simulated_trades": result.simulated_trades,
        # Raw performance
        "raw": {
            "total_return_pct": result.total_return_pct,
            "win_rate": result.win_rate,
            "avg_profit_pct": result.avg_profit_pct,
            "avg_loss_pct": result.avg_loss_pct,
            "best_trade_pct": result.best_trade_pct,
            "worst_trade_pct": result.worst_trade_pct,
            "sharpe_ratio": result.sharpe_ratio,
            "profit_factor": result.profit_factor,
            "max_drawdown_pct": result.max_drawdown_pct,
        },
        # After commission + position sizing
        "adjusted": {
            "commission_pct": data.commission_pct,
            "position_size_pct": data.position_size_pct,
            "total_return_pct": adj_return,
            "win_rate": adj_win_rate,
        },
        # Exit breakdown
        "exits": {
            "tp_hits": result.tp_hits,
            "sl_hits": result.sl_hits,
            "expired": result.expired,
        },
        "avg_bars_held": result.avg_bars_held,
        # Buy & Hold comparison
        "buy_and_hold": buy_hold,
        "strategy_vs_hold": round(result.total_return_pct - buy_hold.get("return_pct", 0), 2),
        # Monthly P&L
        "monthly": monthly,
        # Monte Carlo (1000 simulations)
        "monte_carlo": monte_carlo,
        # Trades & equity
        "trades": result.trades,
        "equity_curve": result.equity_curve,
    }
