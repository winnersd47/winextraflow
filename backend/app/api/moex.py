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


# Sector mapping for heatmap
MOEX_SECTORS = {
    "SBER": "Finance", "VTBR": "Finance", "TCSG": "Finance", "MOEX": "Finance",
    "GAZP": "Energy", "LKOH": "Energy", "ROSN": "Energy", "NVTK": "Energy", "SNGS": "Energy", "TATN": "Energy",
    "GMKN": "Metals", "NLMK": "Metals", "CHMF": "Metals", "ALRS": "Metals", "PLZL": "Metals", "RUAL": "Metals", "POLY": "Metals",
    "YNDX": "Tech", "OZON": "Tech", "FIVE": "Retail", "MGNT": "Retail",
    "MTSS": "Telecom", "AFLT": "Transport", "PHOR": "Chemicals",
}


@router.get("/heatmap")
async def moex_heatmap(user: User = Depends(get_current_user)):
    """Heatmap data: all MOEX tickers with change%, grouped by sector."""
    quotes = await moex_service.get_live_quotes()
    result = []
    for q in quotes:
        ticker = q.get("ticker", "")
        result.append({
            "ticker": ticker,
            "price": q.get("price") or 0,   # service key is "price", not "last_price"
            "change_pct": q.get("change_pct", 0) or 0,
            "volume": q.get("volume", 0),
            "sector": MOEX_SECTORS.get(ticker, "Other"),
        })
    # Sort by sector, then by volume desc
    result.sort(key=lambda x: (x["sector"], -(x["volume"] or 0)))
    return {"tickers": result, "total": len(result)}
