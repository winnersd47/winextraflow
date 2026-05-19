from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import logging

from app.api.auth import router as auth_router
from app.api.signals import router as signals_router
from app.api.providers import router as providers_router
from app.api.ws import router as ws_router
from app.api.backtesting import router as backtest_router
from app.api.referrals import router as referrals_router
from app.api.execution import router as execution_router
from app.api.strategies import router as strategies_router
from app.api.copy_trading import router as copy_trading_router
from app.api.achievements import router as achievements_router
from app.api.premium import router as premium_router
from app.api.notifications import router as notifications_router
from app.api.admin import router as admin_router
from app.api.payments import router as payments_router
from app.api.kyc import router as kyc_router
from app.api.compliance import router as compliance_router
from app.api.products import router as products_router
from app.api.quant import router as quant_router
from app.api.advisors import router as advisors_router
from app.api.moex import router as moex_router
from app.services.achievements import achievement_service
from app.database import async_session as get_async_session, create_tables
from app.models import *  # noqa: F401,F403 — ensure all models registered for create_tables
from app.config import settings
from app.services.copy_trading import copy_trading_service
from app.services.signal_aggregator import signal_aggregator
from app.services.telegram_bot import telegram_bot
from app.services.max_bot import max_bot
from app.workers.signal_fetcher import telegram_worker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables (for SQLite local dev)
    try:
        await create_tables()
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.warning(f"Could not create tables: {e}")

    # Startup: seed achievements (skip if DB not available)
    try:
        async with get_async_session() as db:
            await achievement_service.seed_achievements(db)
        logger.info("Achievements seeded")
    except Exception as e:
        logger.warning(f"Could not seed achievements (DB not ready?): {e}")

    # Startup: seed admin user from env vars — BEFORE test data so admin exists
    if settings.admin_username and settings.admin_password:
        try:
            async with get_async_session() as db:
                from sqlalchemy import select as sel
                from app.models.user import User, UserRole
                from app.api.deps import hash_password
                import secrets
                existing = (await db.execute(sel(User).where(User.username == settings.admin_username))).scalar_one_or_none()
                if not existing:
                    admin = User(
                        email=settings.admin_email or f"{settings.admin_username}@admin.local",
                        username=settings.admin_username,
                        hashed_password=hash_password(settings.admin_password),
                        role=UserRole.ADMIN,
                        referral_code=secrets.token_urlsafe(8),
                    )
                    db.add(admin)
                    await db.commit()
                    logger.info(f"Admin user {settings.admin_username} created")
                else:
                    if existing.role != UserRole.ADMIN:
                        existing.role = UserRole.ADMIN
                        await db.commit()
                    logger.info(f"Admin user {settings.admin_username} verified")
        except Exception as e:
            logger.warning(f"Could not seed admin: {e}")
    else:
        logger.info("No ADMIN_USERNAME/ADMIN_PASSWORD env vars — skipping admin seed")

    # Startup: seed test data (development only) — AFTER admin exists
    if settings.app_env == "development":
        try:
            from app.services.seed_data import seed_test_data
            async with get_async_session() as db:
                await seed_test_data(db)
        except Exception as e:
            logger.warning(f"Could not seed test data: {e}")

    # Startup: register copy trading listener
    if settings.execution_enabled:
        signal_aggregator.on_new_signal(copy_trading_service.on_new_signal)
        logger.info("Copy trading listener registered")

    # Startup: register bot signal broadcaster
    if telegram_bot.enabled:
        async def _bot_signal_hook(signal):
            await telegram_bot.broadcast_signal(
                signal.ticker, signal.action.value, signal.entry_price, signal.ai_confidence,
                tp=signal.take_profit, sl=signal.stop_loss,
            )
        signal_aggregator.on_new_signal(_bot_signal_hook)
        logger.info("Telegram bot signal broadcaster registered")

    # Startup: register MAX bot signal broadcaster
    if max_bot.enabled:
        async def _max_signal_hook(signal):
            await max_bot.broadcast_signal(
                signal.ticker, signal.action.value, signal.entry_price, signal.ai_confidence,
                tp=signal.take_profit, sl=signal.stop_loss,
            )
        signal_aggregator.on_new_signal(_max_signal_hook)
        logger.info("MAX bot signal broadcaster registered")

    # Startup: launch Telegram channel worker if configured
    if settings.telegram_api_id and settings.telegram_api_hash:
        try:
            await telegram_worker.start()
            logger.info("Telegram worker started")
        except Exception as e:
            logger.warning(f"Telegram worker failed to start: {e}")

    # Startup: launch Telegram bot polling
    if telegram_bot.enabled:
        import asyncio
        asyncio.create_task(telegram_bot.start_polling())
        logger.info("Telegram bot polling started")

    # Startup: launch MAX bot polling
    if max_bot.enabled:
        import asyncio
        asyncio.create_task(max_bot.start_polling())
        logger.info("MAX bot polling started")

    yield

    # Shutdown
    await telegram_worker.stop()
    await telegram_bot.stop_polling()
    await max_bot.stop_polling()


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
    enabled=settings.app_env != "test",
)

app = FastAPI(
    title="WinExtraFlow",
    description="Trading signal aggregator with AI rating",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.allowed_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

# ─── Security headers middleware ──────────────────────────
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.app_env != "development":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(signals_router, prefix="/api/v1/signals", tags=["signals"])
app.include_router(providers_router, prefix="/api/v1/providers", tags=["providers"])
app.include_router(ws_router, prefix="/api/v1/ws")
app.include_router(backtest_router, prefix="/api/v1/backtest", tags=["backtesting"])
app.include_router(referrals_router, prefix="/api/v1/referrals", tags=["referrals"])
app.include_router(execution_router, prefix="/api/v1/execution", tags=["execution"])
app.include_router(strategies_router, prefix="/api/v1/strategies", tags=["marketplace"])
app.include_router(copy_trading_router, prefix="/api/v1/copy-trading", tags=["copy-trading"])
app.include_router(achievements_router, prefix="/api/v1/achievements", tags=["gamification"])
app.include_router(premium_router, prefix="/api/v1/premium", tags=["premium"])
app.include_router(notifications_router, prefix="/api/v1/notifications", tags=["notifications"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(payments_router, prefix="/api/v1/payments", tags=["payments"])
app.include_router(kyc_router, prefix="/api/v1/kyc", tags=["kyc"])
app.include_router(compliance_router, prefix="/api/v1/compliance", tags=["compliance"])
app.include_router(products_router, prefix="/api/v1/products", tags=["products"])
app.include_router(quant_router, prefix="/api/v1/quant", tags=["quant-intelligence"])
app.include_router(advisors_router, prefix="/api/v1/advisors", tags=["advisors"])
app.include_router(moex_router, prefix="/api/v1/moex", tags=["moex"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}
