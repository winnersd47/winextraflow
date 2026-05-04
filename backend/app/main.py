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
from app.services.achievements import achievement_service
from app.database import async_session as get_async_session, create_tables
from app.models import *  # noqa: F401,F403 — ensure all models registered for create_tables
from app.config import settings
from app.services.copy_trading import copy_trading_service
from app.services.signal_aggregator import signal_aggregator
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

    # Startup: seed admin user (winnersd47)
    try:
        async with get_async_session() as db:
            from sqlalchemy import select as sel
            from app.models.user import User, UserRole
            from app.api.deps import hash_password
            import secrets
            existing = (await db.execute(sel(User).where(User.username == "winnersd47"))).scalar_one_or_none()
            if not existing:
                admin = User(
                    email="winnersd47@gmail.com",
                    username="winnersd47",
                    hashed_password=hash_password("Yjhnljcn/95"),
                    role=UserRole.ADMIN,
                    referral_code=secrets.token_urlsafe(8),
                )
                db.add(admin)
                await db.commit()
                logger.info("Admin user winnersd47 created")
            else:
                # Update email, password and role if needed
                existing.email = "winnersd47@gmail.com"
                existing.hashed_password = hash_password("Yjhnljcn/95")
                if existing.role != UserRole.ADMIN:
                    existing.role = UserRole.ADMIN
                await db.commit()
                logger.info("Admin user winnersd47 updated")
    except Exception as e:
        logger.warning(f"Could not seed admin: {e}")

    # Startup: register copy trading listener
    if settings.execution_enabled:
        signal_aggregator.on_new_signal(copy_trading_service.on_new_signal)
        logger.info("Copy trading listener registered")

    # Startup: launch Telegram worker if configured
    if settings.telegram_api_id and settings.telegram_api_hash:
        try:
            await telegram_worker.start()
            logger.info("Telegram worker started")
        except Exception as e:
            logger.warning(f"Telegram worker failed to start: {e}")
    yield
    # Shutdown: stop Telegram worker
    await telegram_worker.stop()


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
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}
