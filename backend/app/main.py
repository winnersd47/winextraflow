from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.signals import router as signals_router
from app.api.providers import router as providers_router
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


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


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}
