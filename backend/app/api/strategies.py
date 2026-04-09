"""Strategy Marketplace API — browse, publish, subscribe to strategies."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.provider import Provider
from app.models.strategy import PriceType, Strategy
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User
from app.schemas.strategy import (
    StrategyCreate,
    StrategyList,
    StrategyResponse,
    SubscriptionResponse,
)

router = APIRouter()


def _enrich_strategy(strategy: Strategy, provider: Provider | None) -> dict:
    """Add provider stats to strategy response."""
    data = {c.name: getattr(strategy, c.name) for c in strategy.__table__.columns}
    if provider:
        data["win_rate"] = provider.win_rate
        data["avg_profit"] = provider.avg_profit
        data["ai_score"] = provider.ai_score
        data["sharpe_ratio"] = provider.sharpe_ratio
        data["total_signals"] = provider.total_signals
    return data


# ─── Marketplace (browse) ─────────────────────────────────

@router.get("", response_model=StrategyList)
async def browse_strategies(
    price_type: PriceType | None = None,
    tags: str | None = None,
    sort_by: str = Query("ai_score", regex="^(ai_score|subscriber_count|created_at)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Browse published strategies on the marketplace."""
    query = select(Strategy, Provider).join(
        Provider, Strategy.provider_id == Provider.id
    ).where(Strategy.is_published == True)

    count_query = select(func.count()).select_from(Strategy).where(Strategy.is_published == True)

    if price_type:
        query = query.where(Strategy.price_type == price_type)
        count_query = count_query.where(Strategy.price_type == price_type)
    if tags:
        query = query.where(Strategy.tags.ilike(f"%{tags}%"))
        count_query = count_query.where(Strategy.tags.ilike(f"%{tags}%"))

    # Sort
    if sort_by == "subscriber_count":
        query = query.order_by(Strategy.subscriber_count.desc())
    elif sort_by == "created_at":
        query = query.order_by(Strategy.created_at.desc())
    else:
        query = query.order_by(Provider.ai_score.desc().nulls_last())

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(query.offset(skip).limit(limit))

    items = [_enrich_strategy(s, p) for s, p in result.all()]
    return StrategyList(items=items, total=total)


@router.get("/my", response_model=StrategyList)
async def my_strategies(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get strategies authored by the current user."""
    result = await db.execute(
        select(Strategy, Provider)
        .join(Provider, Strategy.provider_id == Provider.id)
        .where(Strategy.author_id == user.id)
        .order_by(Strategy.created_at.desc())
    )
    items = [_enrich_strategy(s, p) for s, p in result.all()]
    return StrategyList(items=items, total=len(items))


@router.get("/subscriptions", response_model=list[SubscriptionResponse])
async def my_subscriptions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get strategies the current user is subscribed to."""
    result = await db.execute(
        select(Subscription)
        .where(and_(Subscription.user_id == user.id, Subscription.status == SubscriptionStatus.ACTIVE))
        .order_by(Subscription.created_at.desc())
    )
    return result.scalars().all()


# ─── Strategy CRUD ─────────────────────────────────────────

@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Strategy, Provider)
        .join(Provider, Strategy.provider_id == Provider.id)
        .where(Strategy.id == strategy_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(404, "Strategy not found")
    return _enrich_strategy(row[0], row[1])


@router.post("", response_model=StrategyResponse, status_code=201)
async def publish_strategy(
    data: StrategyCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Publish a new strategy on the marketplace."""
    # Verify provider exists
    provider = (await db.execute(
        select(Provider).where(Provider.id == data.provider_id)
    )).scalar_one_or_none()
    if not provider:
        raise HTTPException(404, "Provider not found")

    # Check if strategy already exists for this provider
    existing = (await db.execute(
        select(Strategy).where(Strategy.provider_id == data.provider_id)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(400, "Strategy already exists for this provider")

    strategy = Strategy(
        author_id=user.id,
        provider_id=data.provider_id,
        name=data.name,
        description=data.description,
        tags=data.tags,
        price_type=data.price_type,
        price_monthly=data.price_monthly,
        is_published=True,
    )
    db.add(strategy)
    await db.commit()
    await db.refresh(strategy)
    return _enrich_strategy(strategy, provider)


# ─── Subscribe / Unsubscribe ──────────────────────────────

@router.post("/{strategy_id}/subscribe", response_model=SubscriptionResponse)
async def subscribe(
    strategy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Subscribe to a strategy."""
    strategy = (await db.execute(
        select(Strategy).where(Strategy.id == strategy_id, Strategy.is_published == True)
    )).scalar_one_or_none()
    if not strategy:
        raise HTTPException(404, "Strategy not found")

    # Check existing subscription
    existing = (await db.execute(
        select(Subscription).where(and_(
            Subscription.user_id == user.id,
            Subscription.strategy_id == strategy_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        ))
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(400, "Already subscribed")

    sub = Subscription(
        user_id=user.id,
        strategy_id=strategy_id,
        status=SubscriptionStatus.ACTIVE,
    )
    db.add(sub)

    # Increment subscriber count
    strategy.subscriber_count += 1

    await db.commit()
    await db.refresh(sub)
    return sub


@router.delete("/{strategy_id}/subscribe", status_code=200)
async def unsubscribe(
    strategy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Unsubscribe from a strategy."""
    sub = (await db.execute(
        select(Subscription).where(and_(
            Subscription.user_id == user.id,
            Subscription.strategy_id == strategy_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        ))
    )).scalar_one_or_none()
    if not sub:
        raise HTTPException(404, "Subscription not found")

    sub.status = SubscriptionStatus.CANCELLED

    # Decrement subscriber count
    strategy = await db.get(Strategy, strategy_id)
    if strategy and strategy.subscriber_count > 0:
        strategy.subscriber_count -= 1

    await db.commit()
    return {"status": "unsubscribed"}
