"""Deep AI analysis endpoints — SWOT, BCG portfolio matrix, period review."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.signal import Signal
from app.models.user import User
from app.services.deep_analysis import deep_analysis_service

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class SwotRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=20)
    entry_price: float = Field(..., gt=0)
    current_price: float = Field(..., gt=0)
    take_profit: float | None = None
    stop_loss: float | None = None
    provider_win_rate: float | None = Field(None, ge=0, le=1)
    recent_news: str = Field("", max_length=2000)


class SwotResponse(BaseModel):
    ticker: str
    analysis: dict[str, Any]
    provider: str
    model: str


class PortfolioPosition(BaseModel):
    ticker: str
    weight: float = Field(..., ge=0, le=1, description="Portfolio weight 0-1")
    pnl_pct: float = Field(..., description="P&L percentage")
    volume_rank: int = Field(1, ge=1, description="Volume rank in sector (1=highest)")


class BcgRequest(BaseModel):
    positions: list[PortfolioPosition] = Field(..., min_length=1, max_length=50)
    market_growth_rates: dict[str, float] | None = None


class BcgResponse(BaseModel):
    analysis: dict[str, Any]
    provider: str
    model: str


class PeriodReviewRequest(BaseModel):
    period: str = Field(..., description="e.g. 'January 2026', 'Q1 2026', '2025'")
    provider_name: str = Field("", max_length=100)


class PeriodReviewResponse(BaseModel):
    period: str
    analysis: dict[str, Any]
    provider: str
    model: str


class SignalDeepAnalyzeResponse(BaseModel):
    signal_id: uuid.UUID
    ticker: str
    swot: dict[str, Any]
    provider: str
    model: str


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/swot", response_model=SwotResponse, summary="SWOT analysis for a ticker/signal")
async def swot_analysis(
    body: SwotRequest,
    user: User = Depends(get_current_user),
) -> SwotResponse:
    result = await deep_analysis_service.swot_analysis(
        ticker=body.ticker,
        entry_price=body.entry_price,
        current_price=body.current_price,
        take_profit=body.take_profit,
        stop_loss=body.stop_loss,
        provider_win_rate=body.provider_win_rate,
        recent_news=body.recent_news,
    )
    return SwotResponse(
        ticker=body.ticker,
        analysis=result.content,
        provider=result.provider,
        model=result.model,
    )


@router.post("/portfolio/bcg", response_model=BcgResponse, summary="BCG matrix for portfolio")
async def bcg_portfolio(
    body: BcgRequest,
    user: User = Depends(get_current_user),
) -> BcgResponse:
    positions = [p.model_dump() for p in body.positions]
    result = await deep_analysis_service.bcg_portfolio(
        positions=positions,
        market_growth_rates=body.market_growth_rates,
    )
    return BcgResponse(analysis=result.content, provider=result.provider, model=result.model)


@router.post("/period-review", response_model=PeriodReviewResponse, summary="AI period performance review")
async def period_review(
    body: PeriodReviewRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PeriodReviewResponse:
    from app.models.signal import SignalStatus
    from sqlalchemy import func, and_
    from datetime import datetime, timezone

    # Build summary stats for the user's signals
    closed = [SignalStatus.CLOSED_TP, SignalStatus.CLOSED_SL, SignalStatus.CLOSED_MANUAL]
    total_q = await db.execute(
        select(func.count()).select_from(Signal).where(Signal.status.in_(closed))
    )
    tp_q = await db.execute(
        select(func.count()).select_from(Signal).where(Signal.status == SignalStatus.CLOSED_TP)
    )
    avg_q = await db.execute(
        select(func.avg(Signal.profit_pct)).where(
            and_(Signal.status.in_(closed), Signal.profit_pct.isnot(None))
        )
    )

    total = total_q.scalar() or 0
    tp_count = tp_q.scalar() or 0
    avg_profit = avg_q.scalar()

    signals_summary = {
        "total_closed": total,
        "win_count": tp_count,
        "loss_count": total - tp_count,
        "win_rate": round(tp_count / total, 3) if total > 0 else None,
        "avg_profit_pct": round(float(avg_profit), 2) if avg_profit else None,
        "period": body.period,
    }

    result = await deep_analysis_service.period_review(
        period=body.period,
        signals_summary=signals_summary,
        provider_name=body.provider_name,
    )
    return PeriodReviewResponse(period=body.period, analysis=result.content, provider=result.provider, model=result.model)


@router.post("/signals/{signal_id}/deep-analyze", response_model=SignalDeepAnalyzeResponse)
async def deep_analyze_signal(
    signal_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SignalDeepAnalyzeResponse:
    """Full deep analysis of an existing signal — runs SWOT automatically."""
    signal = await db.get(Signal, signal_id)
    if not signal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signal not found")

    result = await deep_analysis_service.swot_analysis(
        ticker=signal.symbol,
        entry_price=float(signal.entry_price),
        current_price=float(signal.entry_price),
        take_profit=float(signal.take_profit) if signal.take_profit else None,
        stop_loss=float(signal.stop_loss) if signal.stop_loss else None,
    )
    return SignalDeepAnalyzeResponse(
        signal_id=signal_id,
        ticker=signal.symbol,
        swot=result.content,
        provider=result.provider,
        model=result.model,
    )
