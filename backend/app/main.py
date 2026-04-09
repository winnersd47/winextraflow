from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import logging

from app.api.auth import router as auth_router
from app.api.signals import router as signals_router
from app.api.providers import router as providers_router
from app.api.ws import router as ws_router
from app.api.backtesting import router as backtest_router
from app.api.referrals import router as referrals_router
from app.api.execution import router as execution_router
from app.config import settings
from app.workers.signal_fetcher import telegram_worker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
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


app = FastAPI(
    title="WinExtraFlow",
    description="Trading signal aggregator with AI rating",
    version="0.1.0",
    lifespan=lifespan,
)

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


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}
