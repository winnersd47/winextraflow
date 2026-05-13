from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.backtesting import BacktestRequest, BacktestResponse
from app.services.backtesting import backtesting_engine
from app.services.premium import is_premium

router = APIRouter()

# Free user: 1 backtest per day; premium: unlimited
FREE_DAILY_LIMIT = 1


@router.post("", response_model=BacktestResponse)
async def run_backtest(
    data: BacktestRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run a backtest on historical signals.

    Free users: limited to 1 backtest per day.
    Premium users: unlimited.
    """
    # Rate limit for free users
    if not is_premium(user):
        # Count backtests today (using a simple approach: check via achievement)
        # Since we don't have a dedicated counter, we use the backtest achievement progress
        # as a rough proxy, or we simply allow 1 per day via a lightweight check
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
            raise HTTPException(
                429,
                "Free users can run 1 backtest per day. Upgrade to Premium for unlimited backtesting."
            )

    result = await backtesting_engine.run_backtest(
        db,
        provider_id=data.provider_id,
        ticker=data.ticker,
        date_from=data.date_from,
        date_to=data.date_to,
        initial_capital=data.initial_capital,
    )

    # Track backtest run for rate limiting
    if not is_premium(user):
        from app.models.notification import Notification
        db.add(Notification(
            user_id=user.id,
            type="backtest_run",
            title="Backtest",
            message=f"Backtest run: {result.total_signals} signals",
        ))
        await db.commit()

    # Achievement: first_backtest
    try:
        from app.services.achievements import achievement_service
        await achievement_service.increment_progress(db, user.id, "first_backtest")
    except Exception:
        pass

    return result
