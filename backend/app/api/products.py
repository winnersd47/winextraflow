"""Products API — additional revenue streams for self-employed operator.

Revenue sources:
1. API Access Keys — paid developer API access ($49-99/mo)
2. PDF Reports — per-provider analytics reports ($9.99 each)
3. Telegram Premium — premium signal channel access
4. Education — trading courses and guides
"""

import logging
import secrets
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_premium
from app.database import get_db
from app.models.user import User, UserRole
from app.services.premium import is_premium

logger = logging.getLogger(__name__)

router = APIRouter()


# ═══════════════════════════════════════════════════════════
# 1. API ACCESS KEYS — paid developer access
# ═══════════════════════════════════════════════════════════

# In-memory store for demo (production: DB model)
_api_keys: dict[str, dict] = {}

API_PLANS = {
    "basic": {"name": "Basic API", "price_usd": 49, "rate_limit": "100 req/min", "signals": True, "providers": True, "backtest": False, "websocket": False},
    "pro": {"name": "Pro API", "price_usd": 99, "rate_limit": "500 req/min", "signals": True, "providers": True, "backtest": True, "websocket": True},
}


class APIKeyRequest(BaseModel):
    plan: str = "basic"
    label: str = "My API Key"


@router.get("/api-keys/plans")
async def list_api_plans(user: User = Depends(get_current_user)):
    """List available API access plans."""
    return {"plans": [
        {"key": k, **v} for k, v in API_PLANS.items()
    ]}


@router.post("/api-keys")
async def create_api_key(
    data: APIKeyRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_premium),
):
    """Generate a new API access key (Premium required)."""
    if data.plan not in API_PLANS:
        raise HTTPException(400, f"Invalid plan. Choose: {', '.join(API_PLANS.keys())}")

    plan = API_PLANS[data.plan]
    key = f"wef_{secrets.token_urlsafe(32)}"
    key_id = str(uuid.uuid4())

    _api_keys[key_id] = {
        "id": key_id,
        "user_id": str(user.id),
        "key": key,
        "plan": data.plan,
        "label": data.label,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_active": True,
        "rate_limit": plan["rate_limit"],
    }

    logger.info(f"API key created: {data.plan} for user {user.username}")
    return {
        "id": key_id,
        "key": key,
        "plan": data.plan,
        "label": data.label,
        "rate_limit": plan["rate_limit"],
        "price_usd": plan["price_usd"],
        "message": "Save this key — it won't be shown again.",
    }


@router.get("/api-keys")
async def list_api_keys(user: User = Depends(get_current_user)):
    """List user's API keys (key value masked)."""
    user_keys = [
        {
            "id": v["id"],
            "key_preview": v["key"][:8] + "..." + v["key"][-4:],
            "plan": v["plan"],
            "label": v["label"],
            "is_active": v["is_active"],
            "rate_limit": v["rate_limit"],
            "created_at": v["created_at"],
        }
        for v in _api_keys.values() if v["user_id"] == str(user.id)
    ]
    return {"keys": user_keys}


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(key_id: str, user: User = Depends(get_current_user)):
    """Revoke an API key."""
    if key_id not in _api_keys or _api_keys[key_id]["user_id"] != str(user.id):
        raise HTTPException(404, "Key not found")
    _api_keys[key_id]["is_active"] = False
    return {"status": "revoked"}


# ═══════════════════════════════════════════════════════════
# 2. PDF REPORTS — per-provider analytics
# ═══════════════════════════════════════════════════════════

@router.get("/reports/providers")
async def list_report_providers(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List providers available for report generation."""
    from app.models.provider import Provider
    result = await db.execute(
        select(Provider).where(Provider.ai_score.isnot(None)).order_by(Provider.ai_score.desc())
    )
    providers = result.scalars().all()
    return {
        "providers": [
            {
                "id": str(p.id),
                "name": p.name,
                "total_signals": p.total_signals,
                "win_rate": p.win_rate,
                "ai_score": p.ai_score,
                "sharpe_ratio": p.sharpe_ratio,
            }
            for p in providers
        ],
        "price_per_report_usd": 9.99,
    }


@router.post("/reports/generate/{provider_id}")
async def generate_provider_report(
    provider_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_premium),
):
    """Generate an analytics report for a provider (Premium required).

    Returns structured JSON report (PDF generation can be added client-side or via wkhtmltopdf).
    """
    from app.models.provider import Provider
    from app.models.signal import Signal, SignalStatus
    from app.services.backtesting import backtesting_engine

    provider = await db.get(Provider, provider_id)
    if not provider:
        raise HTTPException(404, "Provider not found")

    # Run backtest for this provider
    backtest = await backtesting_engine.run_backtest(db, provider_id=provider_id)

    # Signal distribution
    from sqlalchemy import case
    status_counts = (await db.execute(
        select(
            Signal.status,
            func.count(),
        ).where(Signal.provider_id == provider_id)
        .group_by(Signal.status)
    )).all()

    # Ticker distribution
    ticker_counts = (await db.execute(
        select(
            Signal.ticker,
            func.count().label("count"),
        ).where(Signal.provider_id == provider_id)
        .group_by(Signal.ticker)
        .order_by(func.count().desc())
        .limit(10)
    )).all()

    report = {
        "report_type": "provider_analytics",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": user.username,
        "price_usd": 9.99,
        "provider": {
            "id": str(provider.id),
            "name": provider.name,
            "source": provider.source.value,
            "total_signals": provider.total_signals,
            "win_rate": provider.win_rate,
            "avg_profit": provider.avg_profit,
            "ai_score": provider.ai_score,
            "sharpe_ratio": provider.sharpe_ratio,
            "profit_factor": provider.profit_factor,
            "max_drawdown": provider.max_drawdown,
        },
        "performance": {
            "total_return_pct": backtest.total_return_pct,
            "win_rate": backtest.win_rate,
            "sharpe_ratio": backtest.sharpe_ratio,
            "profit_factor": backtest.profit_factor,
            "max_drawdown_pct": backtest.max_drawdown_pct,
            "avg_profit_pct": backtest.avg_profit_pct,
            "avg_loss_pct": backtest.avg_loss_pct,
            "best_trade_pct": backtest.best_trade_pct,
            "worst_trade_pct": backtest.worst_trade_pct,
            "max_consecutive_wins": backtest.max_consecutive_wins,
            "max_consecutive_losses": backtest.max_consecutive_losses,
            "closed_trades": backtest.closed_signals,
            "equity_curve": backtest.equity_curve,
        },
        "distribution": {
            "by_status": {str(s): c for s, c in status_counts},
            "by_ticker": [{"ticker": t, "count": c} for t, c in ticker_counts],
        },
        "disclaimer": "This report is for informational purposes only and does NOT constitute investment advice. Past performance does not guarantee future results.",
    }

    logger.info(f"Report generated: {provider.name} for {user.username}")
    return report


# ═══════════════════════════════════════════════════════════
# 3. TELEGRAM PREMIUM CHANNEL INFO
# ═══════════════════════════════════════════════════════════

@router.get("/telegram-premium")
async def telegram_premium_info(user: User = Depends(get_current_user)):
    """Get info about Telegram Premium signal channel."""
    premium = is_premium(user)
    return {
        "available": True,
        "is_subscribed": premium,
        "channel_name": "@WinExtraFlowVIP",
        "features": [
            "Real-time signal alerts (before free channel)",
            "AI confidence scores",
            "Entry/TP/SL levels",
            "Provider analytics summaries",
            "Priority support",
        ],
        "features_ru": [
            "Сигналы в реальном времени (раньше бесплатного канала)",
            "AI оценки уверенности",
            "Уровни входа/TP/SL",
            "Аналитика по провайдерам",
            "Приоритетная поддержка",
        ],
        "price_usd": 9.99,
        "price_rub": 899,
        "access": "Premium subscription includes Telegram VIP channel access",
        "access_ru": "Подписка Premium включает доступ к VIP-каналу Telegram",
    }


# ═══════════════════════════════════════════════════════════
# 4. EDUCATION — courses and guides catalog
# ═══════════════════════════════════════════════════════════

COURSES = [
    {
        "id": "course_signals_101",
        "title_ru": "Как читать торговые сигналы",
        "title_en": "How to Read Trading Signals",
        "description_ru": "Базовый курс: что такое BUY/SELL сигнал, как интерпретировать Entry/TP/SL, что означает AI-рейтинг, как выбирать провайдеров.",
        "description_en": "Basic course: what is a BUY/SELL signal, how to interpret Entry/TP/SL, what AI rating means, how to choose providers.",
        "lessons": 8,
        "duration_min": 45,
        "price_usd": 0,
        "price_rub": 0,
        "is_free": True,
        "level": "beginner",
        "topics_ru": [
            "Что такое торговый сигнал",
            "Entry, Take Profit, Stop Loss — объяснение",
            "Как работает AI-рейтинг WinExtraFlow",
            "Выбор провайдера по метрикам",
            "Что такое Win Rate и Sharpe Ratio",
            "Риск-менеджмент: правило 2%",
            "Бэктестинг: проверка стратегий",
            "Как начать торговать на демо-счёте",
        ],
        "topics_en": [
            "What is a trading signal",
            "Entry, Take Profit, Stop Loss — explained",
            "How WinExtraFlow AI rating works",
            "Choosing a provider by metrics",
            "What is Win Rate and Sharpe Ratio",
            "Risk management: the 2% rule",
            "Backtesting: strategy validation",
            "How to start trading on a demo account",
        ],
    },
    {
        "id": "course_risk_management",
        "title_ru": "Управление рисками для трейдера",
        "title_en": "Risk Management for Traders",
        "description_ru": "Продвинутый курс: позиционный менеджмент, дневной лимит убытков, корреляция активов, диверсификация по провайдерам.",
        "description_en": "Advanced course: position sizing, daily loss limits, asset correlation, provider diversification.",
        "lessons": 12,
        "duration_min": 90,
        "price_usd": 29,
        "price_rub": 2499,
        "is_free": False,
        "level": "intermediate",
        "topics_ru": [
            "Позиционный менеджмент",
            "Расчёт размера позиции",
            "Дневной лимит убытков",
            "Корреляция активов",
            "Диверсификация по провайдерам",
            "Drawdown и восстановление",
            "Профит-фактор и ожидаемое значение",
            "Автоматическое исполнение: настройка",
            "Копитрейдинг: выбор стратегий",
            "Психология торговли",
            "Ведение торгового журнала",
            "Когда остановиться: правила дисциплины",
        ],
        "topics_en": [
            "Position management",
            "Position size calculation",
            "Daily loss limit",
            "Asset correlation",
            "Provider diversification",
            "Drawdown and recovery",
            "Profit factor and expected value",
            "Auto-execution: setup",
            "Copy trading: choosing strategies",
            "Trading psychology",
            "Keeping a trade journal",
            "When to stop: discipline rules",
        ],
    },
    {
        "id": "course_crypto_analysis",
        "title_ru": "Криптовалютная аналитика",
        "title_en": "Cryptocurrency Analytics",
        "description_ru": "Спецкурс: особенности крипто-рынка, DeFi сигналы, on-chain метрики, волатильность 24/7, ликвидность.",
        "description_en": "Special course: crypto market specifics, DeFi signals, on-chain metrics, 24/7 volatility, liquidity.",
        "lessons": 10,
        "duration_min": 60,
        "price_usd": 49,
        "price_rub": 4499,
        "is_free": False,
        "level": "advanced",
        "topics_ru": [
            "Особенности крипто-рынка",
            "Биржи: Binance, Bybit, OKX, Kraken",
            "DeFi сигналы и on-chain аналитика",
            "Волатильность и ликвидность 24/7",
            "Фьючерсы и маржинальная торговля",
            "Стейблкоины и управление кэшем",
            "Регулирование криптовалют в РФ (ФЗ-259)",
            "Налогообложение крипто-операций",
            "Безопасность: хранение API-ключей",
            "Построение крипто-портфеля",
        ],
        "topics_en": [
            "Crypto market specifics",
            "Exchanges: Binance, Bybit, OKX, Kraken",
            "DeFi signals and on-chain analytics",
            "24/7 volatility and liquidity",
            "Futures and margin trading",
            "Stablecoins and cash management",
            "Crypto regulation in Russia (FZ-259)",
            "Crypto tax reporting",
            "Security: API key storage",
            "Building a crypto portfolio",
        ],
    },
]


@router.get("/education")
async def list_courses(user: User = Depends(get_current_user)):
    """List available educational courses."""
    premium = is_premium(user)
    return {
        "courses": [
            {
                **c,
                "is_accessible": c["is_free"] or premium,
            }
            for c in COURSES
        ],
        "total": len(COURSES),
        "free_count": sum(1 for c in COURSES if c["is_free"]),
        "premium_unlocks_all": True,
    }


@router.get("/education/{course_id}")
async def get_course(
    course_id: str,
    user: User = Depends(get_current_user),
):
    """Get course details. Free courses accessible to all, paid — Premium only."""
    course = next((c for c in COURSES if c["id"] == course_id), None)
    if not course:
        raise HTTPException(404, "Course not found")

    premium = is_premium(user)
    if not course["is_free"] and not premium:
        raise HTTPException(403, "Premium subscription required for this course")

    return {**course, "is_accessible": True}
