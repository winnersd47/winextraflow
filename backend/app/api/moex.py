"""MOEX API — real-time Moscow Exchange data.

Endpoints:
  GET /moex/overview   — indices + quotes + top movers
  GET /moex/quotes     — live prices for tracked securities
  GET /moex/indices    — main MOEX indices
  GET /moex/candles/{ticker} — candle data for charts
"""

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.models.user import User
from app.services.moex import moex_service

router = APIRouter()


@router.get("/overview")
async def moex_overview(user: User = Depends(get_current_user)):
    """Full MOEX market overview: indices, quotes, top movers."""
    return await moex_service.get_market_overview()


@router.get("/quotes")
async def moex_quotes(user: User = Depends(get_current_user)):
    """Live quotes for tracked RU securities."""
    return {"quotes": await moex_service.get_live_quotes()}


@router.get("/indices")
async def moex_indices(user: User = Depends(get_current_user)):
    """Main MOEX indices (IMOEX, RTS, etc)."""
    return {"indices": await moex_service.get_indices()}


@router.get("/candles/{ticker}")
async def moex_candles(
    ticker: str,
    interval: int = Query(60, description="1, 10, 60 min or 24=daily"),
    count: int = Query(50, ge=1, le=500),
    user: User = Depends(get_current_user),
):
    """Candle data for a MOEX security."""
    return {"ticker": ticker.upper(), "interval": interval, "candles": await moex_service.get_candles(ticker.upper(), interval, count)}
