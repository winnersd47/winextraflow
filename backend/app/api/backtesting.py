from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.backtesting import BacktestRequest, BacktestResponse
from app.services.backtesting import backtesting_engine

router = APIRouter()


@router.post("", response_model=BacktestResponse)
async def run_backtest(
    data: BacktestRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run a backtest on historical signals.

    Filter by provider_id, ticker, and/or date range.
    Returns performance metrics, risk analysis, and equity curve.
    """
    result = await backtesting_engine.run_backtest(
        db,
        provider_id=data.provider_id,
        ticker=data.ticker,
        date_from=data.date_from,
        date_to=data.date_to,
        initial_capital=data.initial_capital,
    )
    # Achievement: first_backtest
    try:
        from app.services.achievements import achievement_service
        await achievement_service.increment_progress(db, user.id, "first_backtest")
    except Exception:
        pass
    return result
