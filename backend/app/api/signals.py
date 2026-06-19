import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.api.deps import get_current_user, require_analyst
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
from app.services.signal_aggregator import signal_aggregator
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

    # Quality gate: hide signals with WEF < 50% from non-admin users
    from app.models.user import UserRole
    if user.role != UserRole.ADMIN:
        quality_filter = (Signal.ai_confidence >= 0.5) | (Signal.ai_confidence.is_(None))
        query = query.where(quality_filter)
        count_query = count_query.where(quality_filter)

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


@router.get("/{signal_id}/quality")
async def signal_quality(
    signal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Check quality of a specific signal — TP/SL, R:R, WEF, provider WR."""
    from app.services.signal_quality import check_signal_quality, format_quality_report
    signal = (await db.execute(select(Signal).where(Signal.id == signal_id))).scalar_one_or_none()
    if not signal:
        raise HTTPException(404, "Signal not found")
    provider = None
    if signal.provider_id:
        from app.models.provider import Provider
        provider = await db.get(Provider, signal.provider_id)
    quality = await check_signal_quality(db, signal, provider)
    return format_quality_report(quality)


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
        pass  # Non-critical hook
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
        logger.warning(f"Webhook validation error: {e}")
        raise HTTPException(status_code=422, detail="Invalid webhook data")

    # Auto-rate the signal
    if settings.ai_rating_enabled:
        await ai_rating_service.rate_and_update_signal(db, signal)

    # Quality gate — check before broadcasting
    from app.services.signal_quality import check_signal_quality, format_quality_report
    provider = None
    if signal.provider_id:
        from app.models.provider import Provider
        provider = await db.get(Provider, signal.provider_id)
    quality = await check_signal_quality(db, signal, provider)

    # Store quality result in ai_reasoning
    if quality.issues:
        signal.ai_reasoning = (signal.ai_reasoning or "") + f" | Quality: {quality.tier} ({', '.join(quality.issues)})"
        await db.commit()

    # Only broadcast high-quality signals
    if quality.passed:
        try:
            await signal_aggregator._notify_listeners(signal)
        except Exception as e:
            logger.warning(f"WS broadcast failed: {e}")
    else:
        logger.info(f"Signal {signal.ticker} blocked by quality gate: {quality.issues}")

    # Return signal with quality info
    resp = signal
    return resp


@router.post("", response_model=SignalResponse, status_code=201)
async def create_signal(
    data: SignalCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_analyst),
):
    """Create a trading signal. Requires Analyst or Admin role."""
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

    # Notify WebSocket listeners (real-time broadcast)
    try:
        await signal_aggregator._notify_listeners(signal)
    except Exception as e:
        logger.warning(f"WS broadcast failed: {e}")

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
        logger.warning(f"Signal close error: {e}")
        raise HTTPException(status_code=400, detail="Invalid close parameters")

    # Feedback loop: record outcome for L3 readiness
    try:
        from app.services.quant.readiness import readiness_monitor
        outcome = "tp_hit" if signal.status.value == "closed_tp" else "sl_hit" if signal.status.value == "closed_sl" else "expired"
        readiness_monitor.record_feedback(
            signal_id=str(signal.id),
            predicted_quality=signal.ai_confidence or 0.5,
            actual_outcome=outcome,
        )
    except Exception:
        pass  # Non-critical hook

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
