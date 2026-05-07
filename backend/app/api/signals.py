import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import settings
from app.services.premium import is_premium
from app.database import get_db
from app.models.signal import Signal, SignalStatus
from app.models.user import User
from app.schemas.signal import (
    RatingDetail,
    SignalClose,
    SignalCreate,
    SignalList,
    SignalResponse,
    TradingViewWebhook,
)
from app.services.ai_rating import ai_rating_service
from app.services.tradingview import tradingview_service

router = APIRouter()


@router.get("", response_model=SignalList)
async def list_signals(
    ticker: str | None = None,
    status: SignalStatus | None = None,
    provider_id: uuid.UUID | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Signal).order_by(Signal.created_at.desc())
    count_query = select(func.count()).select_from(Signal)

    if ticker:
        query = query.where(Signal.ticker == ticker.upper())
        count_query = count_query.where(Signal.ticker == ticker.upper())
    if status:
        query = query.where(Signal.status == status)
        count_query = count_query.where(Signal.status == status)
    if provider_id:
        query = query.where(Signal.provider_id == provider_id)
        count_query = count_query.where(Signal.provider_id == provider_id)

    # Free users: limited to 10 signals
    if not is_premium(user):
        limit = min(limit, 10)

    total = (await db.execute(count_query)).scalar()
    result = await db.execute(query.offset(skip).limit(limit))
    return SignalList(items=result.scalars().all(), total=total)


@router.get("/{signal_id}", response_model=SignalResponse)
async def get_signal(
    signal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Signal).where(Signal.id == signal_id))
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    # Achievement: first_signal, signal_hunter
    try:
        from app.services.achievements import achievement_service
        await achievement_service.increment_progress(db, user.id, "first_signal")
        await achievement_service.increment_progress(db, user.id, "signal_hunter")
    except Exception:
        pass
    return signal


@router.post("/webhook/tradingview", response_model=SignalResponse, status_code=201)
async def tradingview_webhook(
    data: TradingViewWebhook,
    db: AsyncSession = Depends(get_db),
):
    # Validate webhook secret
    if settings.tradingview_webhook_secret and data.secret != settings.tradingview_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    try:
        signal = await tradingview_service.process_webhook(
            db,
            ticker=data.ticker,
            action=data.action,
            price=data.price,
            timeframe=data.timeframe,
            take_profit=data.take_profit,
            stop_loss=data.stop_loss,
            raw_message=data.model_dump_json(),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Auto-rate the signal
    if settings.ai_rating_enabled:
        await ai_rating_service.rate_and_update_signal(db, signal)

    return signal


@router.post("", response_model=SignalResponse, status_code=201)
async def create_signal(
    data: SignalCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Manually create a trading signal (for signal providers)."""
    from app.models.signal import Signal as SignalModel, SignalAction
    from app.models.provider import Provider
    # Verify provider exists
    provider = await db.get(Provider, data.provider_id)
    if not provider:
        raise HTTPException(404, "Provider not found")

    signal = SignalModel(
        provider_id=data.provider_id,
        ticker=data.ticker.upper(),
        action=SignalAction(data.action.value),
        entry_price=data.entry_price,
        take_profit=data.take_profit,
        stop_loss=data.stop_loss,
        timeframe=data.timeframe,
        raw_message=data.raw_message,
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)

    if settings.ai_rating_enabled:
        await ai_rating_service.rate_and_update_signal(db, signal)

    return signal


@router.patch("/{signal_id}/close", response_model=SignalResponse)
async def close_signal(
    signal_id: uuid.UUID,
    data: SignalClose,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Close an active signal with a close price. Calculates profit and updates provider stats."""
    result = await db.execute(select(Signal).where(Signal.id == signal_id))
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    try:
        signal = await ai_rating_service.close_signal(
            db, signal, data.close_price, data.status
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return signal


@router.get("/{signal_id}/rating", response_model=RatingDetail)
async def get_signal_rating(
    signal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get detailed AI rating breakdown for a signal."""
    result = await db.execute(select(Signal).where(Signal.id == signal_id))
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    breakdown = await ai_rating_service.rate_signal(db, signal)
    return breakdown.to_dict()
