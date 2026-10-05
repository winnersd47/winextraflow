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
    """Add provider stats to strategy response.

    All ten published strategies belong to seed providers, so their win rate,
    Sharpe and ai_score are generated numbers — and `subscriber_count` claimed
    38-134 subscribers each on a platform with twelve registered users. Fabricated
    subscriber counts are social proof, which is exactly what a buyer weighs, so
    they are not passed through: `is_demo` marks the row and the count is dropped
    rather than invented.
    """
    data = {c.name: getattr(strategy, c.name) for c in strategy.__table__.columns}
    is_demo = bool(provider and provider.is_seed)
    data["is_demo"] = is_demo
    if is_demo:
        data["subscriber_count"] = None
        data["demo_notice_ru"] = ("Демонстрационная стратегия. Показатели "
                                  "сгенерированы для примера и не являются "
                                  "результатами реальной торговли.")
    if provider:
        data["win_rate"] = None if is_demo else provider.win_rate
        data["avg_profit"] = None if is_demo else provider.avg_profit
        data["ai_score"] = None if is_demo else provider.ai_score
        data["sharpe_ratio"] = None if is_demo else provider.sharpe_ratio
        data["total_signals"] = provider.total_signals
    return data


# ─── Marketplace (browse) ─────────────────────────────────

@router.get("", response_model=StrategyList)
async def browse_strategies(
    price_type: PriceType | None = None,
    tags: str | None = None,
    sort_by: str = Query("ai_score", pattern="^(ai_score|subscriber_count|created_at)$"),
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


# ─── Unified Marketplace (MUST be before /{strategy_id}) ──

@router.get("/unified-marketplace")
async def unified_marketplace(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """All strategies from all sources in one unified list."""
    return await _build_unified_marketplace(db)


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
    # Achievement: strategy_creator
    try:
        from app.services.achievements import achievement_service
        await achievement_service.increment_progress(db, user.id, "strategy_creator")
    except Exception:
        pass  # Achievement tracking is non-critical
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
    # Achievement: first_subscription
    try:
        from app.services.achievements import achievement_service
        await achievement_service.increment_progress(db, user.id, "first_subscription")
    except Exception:
        pass  # Achievement tracking is non-critical
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


# ─── Unified Marketplace (implementation) ────────

async def _build_unified_marketplace(db: AsyncSession) -> dict:
    from app.api.advisors import (ADVISORS_CATALOG, STATS_AS_OF, STRATEGY_NAMES_RU,
                              STRATEGY_NAMES_EN, RISK_RU)
    from app.api.tv_strategies import TV_STRATEGIES
    from app.api.tv_strategies import STRATEGY_NAMES_RU as TV_NAMES_RU, STRATEGY_NAMES_EN as TV_NAMES_EN, RISK_RU as TV_RISK_RU

    items = []

    # 1. Provider strategies from DB
    result = await db.execute(
        select(Strategy, Provider).join(Provider, Strategy.provider_id == Provider.id)
        .where(Strategy.is_published == True).order_by(Provider.ai_score.desc().nulls_last())
    )
    for s, p in result.all():
        data = {c.name: getattr(s, c.name) for c in s.__table__.columns}
        name = data["name"].replace("[TEST] ", "")
        # This endpoint builds its own dicts and therefore bypassed the fix in
        # _enrich_strategy — and it is the one the marketplace page actually calls.
        # Two separate inventions were reaching the UI from here:
        #   rating  = ai_score x 5, where ai_score is a seeded provider's generated
        #             number, rendered as a 4.3/5 star rating
        #   reviews = total_signals, i.e. a count of signals relabelled as reviews.
        #             Nobody reviewed anything.
        is_demo = bool(p.is_seed)
        items.append({
            "id": str(data["id"]),
            "source": "provider",
            "name": name,
            "description": data.get("description") or "",
            "strategy_type_ru": _classify_tags_ru(data.get("tags")),
            "strategy_type_en": _classify_tags_en(data.get("tags")),
            "risk": _calc_risk(p.win_rate, p.sharpe_ratio),
            "risk_ru": RISK_RU.get(_calc_risk(p.win_rate, p.sharpe_ratio), "Средний"),
            # No star rating: the platform has no reviews, so there is nothing to
            # average. Sorting falls back to WEF, which at least means something.
            "rating": None,
            "reviews": None,
            "signals_count": p.total_signals or 0,
            "price_usd": data.get("price_monthly") or 0,
            "price_type": data.get("price_type", "free"),
            "tickers": (data.get("tags") or "").split(",")[:3],
            "subscriber_count": None if is_demo else data.get("subscriber_count", 0),
            "win_rate": None if is_demo else p.win_rate,
            "sharpe_ratio": None if is_demo else p.sharpe_ratio,
            "ai_score": None if is_demo else p.ai_score,
            "avg_profit": None if is_demo else p.avg_profit,
            "is_demo": is_demo,
            "demo_notice_ru": ("Демонстрационная стратегия. Показатели сгенерированы "
                               "для примера и не являются результатами торговли."
                               if is_demo else None),
            "url": None,
            "can_simulate": True,
            "provider_id": str(p.id),
        })

    # 2. MT5 Advisors
    for ea in ADVISORS_CATALOG:
        items.append({
            "id": ea["id"],
            "source": "mt5",
            "name": ea["name"],
            "description": ea.get("description_ru", ""),
            "strategy_type_ru": STRATEGY_NAMES_RU.get(ea["strategy_id"], "?"),
            "strategy_type_en": STRATEGY_NAMES_EN.get(ea["strategy_id"], "?"),
            "risk": ea.get("risk", "medium"),
            "risk_ru": RISK_RU.get(ea.get("risk", "medium"), "Средний"),
            # A real MQL5 rating, but a hand-copied snapshot — dated so the UI can
            # say so instead of implying it is current.
            "rating": ea.get("rating", 0),
            "reviews": ea.get("reviews", 0),
            "stats_as_of": STATS_AS_OF,
            "stats_are_live": False,
            "signals_count": None,
            "price_usd": ea.get("price_usd", 0),
            "price_type": "paid" if ea.get("price_usd") else "free",
            "tickers": ea.get("tickers", []),
            "subscriber_count": None,
            "win_rate": None,
            "sharpe_ratio": None,
            "ai_score": None,
            "avg_profit": None,
            "url": ea.get("mql5_url"),
            "can_simulate": False,
            "provider_id": None,
        })

    # 3. TradingView
    for tv in TV_STRATEGIES:
        items.append({
            "id": tv["id"],
            "source": "tradingview",
            "name": tv["name"],
            "description": tv.get("description_ru", ""),
            "strategy_type_ru": TV_NAMES_RU.get(tv["strategy_id"], "?"),
            "strategy_type_en": TV_NAMES_EN.get(tv["strategy_id"], "?"),
            "risk": tv.get("risk", "medium"),
            "risk_ru": TV_RISK_RU.get(tv.get("risk", "medium"), "Средний"),
            "rating": min(5.0, (tv.get("likes", 0) / 5) + 3),  # Convert likes to pseudo-rating
            "reviews": tv.get("likes", 0),
            "price_usd": 0,
            "price_type": "free",
            "tickers": tv.get("tickers", []),
            "subscriber_count": 0,
            "win_rate": None,
            "sharpe_ratio": None,
            "ai_score": None,
            "avg_profit": None,
            "url": tv.get("tv_url"),
            "can_simulate": False,
            "provider_id": None,
            "webhook_template": tv.get("webhook_template"),
            "moex_compatible": tv.get("moex_compatible", False),
        })

    demo_count = sum(1 for i in items if i.get("is_demo"))
    return {
        "items": items,
        "total": len(items),
        "demo_count": demo_count,
        # Provenance for the whole list, so the UI never has to guess which numbers
        # are measured. Ratings come only from the MQL5 snapshot; the platform has
        # no reviews of its own and therefore shows no stars for its strategies.
        "stats_as_of": STATS_AS_OF,
        "ratings_source": "MQL5 Market snapshot",
        "notice_ru": (
            f"Рейтинг и отзывы есть только у советников MQL5 — это снимок на "
            f"{STATS_AS_OF}, не живые данные. У стратегий платформы отзывов нет, "
            f"поэтому звёзды не показываются."
            + (f" Демонстрационных стратегий в списке: {demo_count} — их показатели "
               f"сгенерированы." if demo_count else "")
        ),
    }


def _classify_tags_ru(tags: str | None) -> str:
    t = (tags or "").lower()
    if "scalp" in t: return "Скальпинг"
    if "breakout" in t: return "Пробой"
    if "trend" in t or "momentum" in t: return "Тренд"
    if "defi" in t or "research" in t: return "Аналитика"
    if "value" in t: return "Стоимостная"
    if "ai" in t: return "ML/AI"
    if "crypto" in t or "altcoin" in t: return "Крипто"
    if "forex" in t: return "Форекс"
    if "indices" in t: return "Индексы"
    return "Мульти"

def _classify_tags_en(tags: str | None) -> str:
    t = (tags or "").lower()
    if "scalp" in t: return "Scalping"
    if "breakout" in t: return "Breakout"
    if "trend" in t or "momentum" in t: return "Trend"
    if "defi" in t or "research" in t: return "Analytics"
    if "value" in t: return "Value"
    if "ai" in t: return "ML/AI"
    if "crypto" in t or "altcoin" in t: return "Crypto"
    if "forex" in t: return "Forex"
    if "indices" in t: return "Indices"
    return "Multi"

def _calc_risk(wr: float | None, sharpe: float | None) -> str:
    score = 0
    if wr and wr >= 0.7: score += 2
    elif wr and wr >= 0.55: score += 1
    if sharpe and sharpe >= 8: score += 2
    elif sharpe and sharpe >= 4: score += 1
    if score >= 3: return "low"
    if score >= 1: return "medium"
    return "high"


# ─── Simulation ──────────────────────────────────

@router.post("/{strategy_id}/simulate")
async def simulate_strategy(
    strategy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate simulated signals for a strategy (admin only)."""
    from app.models.user import UserRole
    if user.role != UserRole.ADMIN:
        raise HTTPException(403, "Admin only")

    strategy = (await db.execute(
        select(Strategy).where(Strategy.id == strategy_id)
    )).scalar_one_or_none()
    if not strategy:
        raise HTTPException(404, "Strategy not found")

    provider = (await db.execute(
        select(Provider).where(Provider.id == strategy.provider_id)
    )).scalar_one_or_none()

    import random
    from app.models.signal import Signal, SignalAction
    from app.services.ai_rating import ai_rating_service
    from app.services.signal_aggregator import signal_aggregator
    from app.config import settings

    tickers = ["BTCUSDT", "ETHUSDT", "SBER", "GAZP", "EURUSD", "XAUUSD", "SOLUSDT", "AAPL"]
    actions = [SignalAction.BUY, SignalAction.SELL]
    prices = {"BTCUSDT": 67000, "ETHUSDT": 3500, "SBER": 325, "GAZP": 122, "EURUSD": 1.085, "XAUUSD": 2350, "SOLUSDT": 145, "AAPL": 192}

    signals_created = []
    for i in range(5):
        ticker = random.choice(tickers)
        action = random.choice(actions)
        price = prices.get(ticker, 100) * random.uniform(0.98, 1.02)
        tp_dist = price * random.uniform(0.02, 0.05)
        sl_dist = price * random.uniform(0.01, 0.03)
        tp = price + tp_dist if action == SignalAction.BUY else price - tp_dist
        sl = price - sl_dist if action == SignalAction.BUY else price + sl_dist

        signal = Signal(
            provider_id=strategy.provider_id,
            ticker=ticker,
            action=action,
            entry_price=round(price, 6),
            take_profit=round(tp, 6),
            stop_loss=round(sl, 6),
            timeframe="1h",
            raw_message=f"[SIMULATION] {strategy.name} — simulated signal #{i+1}",
        )
        db.add(signal)
        await db.flush()

        if settings.ai_rating_enabled:
            await ai_rating_service.rate_and_update_signal(db, signal)

        signals_created.append({"id": str(signal.id), "ticker": ticker, "action": action.value, "price": round(price, 2)})

    await db.commit()

    # Notify WebSocket
    for sig_data in signals_created:
        try:
            from app.models.signal import Signal as SigModel
            sig = await db.get(SigModel, sig_data["id"])
            if sig:
                await signal_aggregator._notify_listeners(sig)
        except Exception:
            pass

    return {"status": "simulated", "signals": signals_created, "strategy": strategy.name}
