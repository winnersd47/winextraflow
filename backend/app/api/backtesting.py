from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.backtest_report import BacktestReport
from app.schemas.backtesting import BacktestRequest, BacktestResponse
from app.services.backtesting import backtesting_engine
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
