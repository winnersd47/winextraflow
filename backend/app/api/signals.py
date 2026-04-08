import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models.signal import Signal, SignalStatus
from app.models.user import User
from app.schemas.signal import SignalList, SignalResponse, TradingViewWebhook
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
    return signal
