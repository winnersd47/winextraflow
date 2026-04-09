"""Copy Trading API — status, history, settings."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.copy_trade import CopyTrade, CopyTradeStatus
from app.models.exchange_account import ExchangeAccount
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User
from app.schemas.copy_trading import (
    CopyTradeList,
    CopyTradeResponse,
    CopyTradingStatus,
)

router = APIRouter()


@router.get("/status", response_model=CopyTradingStatus)
async def copy_trading_status(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get copy trading status for the current user."""
    # Active subscriptions with auto_execute
    active_subs = (await db.execute(
        select(func.count()).select_from(Subscription).where(and_(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.auto_execute == True,
        ))
    )).scalar() or 0

    # Auto-execute exchange accounts
    auto_accounts = (await db.execute(
        select(func.count()).select_from(ExchangeAccount).where(and_(
            ExchangeAccount.user_id == user.id,
            ExchangeAccount.is_active == True,
            ExchangeAccount.auto_execute == True,
        ))
    )).scalar() or 0

    # Trade counts
    total = (await db.execute(
        select(func.count()).select_from(CopyTrade).where(CopyTrade.subscriber_id == user.id)
    )).scalar() or 0

    successful = (await db.execute(
        select(func.count()).select_from(CopyTrade).where(and_(
            CopyTrade.subscriber_id == user.id,
            CopyTrade.status == CopyTradeStatus.EXECUTED,
        ))
    )).scalar() or 0

    failed = (await db.execute(
        select(func.count()).select_from(CopyTrade).where(and_(
            CopyTrade.subscriber_id == user.id,
            CopyTrade.status == CopyTradeStatus.FAILED,
        ))
    )).scalar() or 0

    return CopyTradingStatus(
        enabled=active_subs > 0 and auto_accounts > 0,
        active_subscriptions=active_subs,
        auto_execute_accounts=auto_accounts,
        total_copied_trades=total,
        successful_trades=successful,
        failed_trades=failed,
    )


@router.get("/history", response_model=CopyTradeList)
async def copy_trade_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get copy trade history for the current user."""
    total = (await db.execute(
        select(func.count()).select_from(CopyTrade).where(CopyTrade.subscriber_id == user.id)
    )).scalar() or 0

    result = await db.execute(
        select(CopyTrade)
        .where(CopyTrade.subscriber_id == user.id)
        .order_by(CopyTrade.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return CopyTradeList(items=result.scalars().all(), total=total)


@router.patch("/subscriptions/{subscription_id}/auto-execute")
async def toggle_auto_execute(
    subscription_id: uuid.UUID,
    enable: bool,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Toggle auto-execute for a specific subscription."""
    sub = (await db.execute(
        select(Subscription).where(and_(
            Subscription.id == subscription_id,
            Subscription.user_id == user.id,
        ))
    )).scalar_one_or_none()
    if not sub:
        raise HTTPException(404, "Subscription not found")

    sub.auto_execute = enable
    await db.commit()
    return {"subscription_id": str(sub.id), "auto_execute": sub.auto_execute}
