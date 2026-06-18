"""Trading Journal API — CRUD for personal trade diary."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.journal import JournalEntry
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


class JournalCreate(BaseModel):
    ticker: str
    action: str  # buy / sell
    entry_price: float
    exit_price: float | None = None
    quantity: float | None = None
    profit_pct: float | None = None
    profit_abs: float | None = None
    note: str | None = None
    tags: list[str] | None = None
    emotion: str | None = None
    rating: float | None = None
    signal_id: str | None = None
    opened_at: str | None = None
    closed_at: str | None = None


class JournalUpdate(BaseModel):
    exit_price: float | None = None
    profit_pct: float | None = None
    profit_abs: float | None = None
    note: str | None = None
    tags: list[str] | None = None
    emotion: str | None = None
    rating: float | None = None
    closed_at: str | None = None


@router.get("")
async def list_journal(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    ticker: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List user's journal entries."""
    stmt = select(JournalEntry).where(JournalEntry.user_id == str(user.id))
    if ticker:
        stmt = stmt.where(JournalEntry.ticker == ticker.upper())
    stmt = stmt.order_by(JournalEntry.created_at.desc()).offset(offset).limit(limit)

    entries = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(
        select(func.count(JournalEntry.id)).where(JournalEntry.user_id == str(user.id))
    )).scalar() or 0

    return {
        "total": total,
        "items": [
            {
                "id": e.id,
                "ticker": e.ticker,
                "action": e.action,
                "entry_price": e.entry_price,
                "exit_price": e.exit_price,
                "quantity": e.quantity,
                "profit_pct": e.profit_pct,
                "profit_abs": e.profit_abs,
                "note": e.note,
                "tags": e.tags or [],
                "emotion": e.emotion,
                "rating": e.rating,
                "signal_id": e.signal_id,
                "opened_at": e.opened_at.isoformat() if e.opened_at else None,
                "closed_at": e.closed_at.isoformat() if e.closed_at else None,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ],
    }


@router.post("", status_code=201)
async def create_journal_entry(
    data: JournalCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new journal entry."""
    entry = JournalEntry(
        user_id=str(user.id),
        ticker=data.ticker.upper(),
        action=data.action.lower(),
        entry_price=data.entry_price,
        exit_price=data.exit_price,
        quantity=data.quantity,
        profit_pct=data.profit_pct,
        profit_abs=data.profit_abs,
        note=data.note,
        tags=data.tags,
        emotion=data.emotion,
        rating=data.rating,
        signal_id=data.signal_id,
    )

    if data.opened_at:
        try:
            entry.opened_at = datetime.fromisoformat(data.opened_at)
        except ValueError:
            pass
    if data.closed_at:
        try:
            entry.closed_at = datetime.fromisoformat(data.closed_at)
        except ValueError:
            pass

    # Auto-calculate profit if exit_price provided
    if data.exit_price and data.entry_price and not data.profit_pct:
        if data.action.lower() == "buy":
            entry.profit_pct = ((data.exit_price - data.entry_price) / data.entry_price) * 100
        else:
            entry.profit_pct = ((data.entry_price - data.exit_price) / data.entry_price) * 100
        if data.quantity:
            entry.profit_abs = abs(data.exit_price - data.entry_price) * data.quantity
            if entry.profit_pct < 0:
                entry.profit_abs = -entry.profit_abs

    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    return {"id": entry.id, "status": "created"}


@router.patch("/{entry_id}")
async def update_journal_entry(
    entry_id: str,
    data: JournalUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update a journal entry (close trade, add notes)."""
    entry = (await db.execute(
        select(JournalEntry).where(
            JournalEntry.id == entry_id,
            JournalEntry.user_id == str(user.id),
        )
    )).scalar_one_or_none()

    if not entry:
        raise HTTPException(404, "Entry not found")

    if data.exit_price is not None:
        entry.exit_price = data.exit_price
        # Recalculate profit
        if entry.entry_price:
            if entry.action == "buy":
                entry.profit_pct = ((data.exit_price - entry.entry_price) / entry.entry_price) * 100
            else:
                entry.profit_pct = ((entry.entry_price - data.exit_price) / entry.entry_price) * 100
            if entry.quantity:
                entry.profit_abs = abs(data.exit_price - entry.entry_price) * entry.quantity
                if entry.profit_pct < 0:
                    entry.profit_abs = -entry.profit_abs

    if data.profit_pct is not None:
        entry.profit_pct = data.profit_pct
    if data.profit_abs is not None:
        entry.profit_abs = data.profit_abs
    if data.note is not None:
        entry.note = data.note
    if data.tags is not None:
        entry.tags = data.tags
    if data.emotion is not None:
        entry.emotion = data.emotion
    if data.rating is not None:
        entry.rating = data.rating
    if data.closed_at:
        try:
            entry.closed_at = datetime.fromisoformat(data.closed_at)
        except ValueError:
            entry.closed_at = datetime.now(timezone.utc)

    await db.commit()
    return {"id": entry.id, "status": "updated"}


@router.delete("/{entry_id}")
async def delete_journal_entry(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a journal entry."""
    entry = (await db.execute(
        select(JournalEntry).where(
            JournalEntry.id == entry_id,
            JournalEntry.user_id == str(user.id),
        )
    )).scalar_one_or_none()

    if not entry:
        raise HTTPException(404, "Entry not found")

    await db.delete(entry)
    await db.commit()
    return {"status": "deleted"}


@router.get("/stats")
async def journal_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Aggregated journal statistics for the user."""
    stmt = select(JournalEntry).where(JournalEntry.user_id == str(user.id))
    entries = (await db.execute(stmt)).scalars().all()

    total = len(entries)
    closed = [e for e in entries if e.profit_pct is not None]
    wins = sum(1 for e in closed if e.profit_pct > 0)
    losses = len(closed) - wins
    win_rate = wins / len(closed) if closed else 0
    avg_profit = sum(e.profit_pct for e in closed) / len(closed) if closed else 0
    best_trade = max((e.profit_pct for e in closed), default=0)
    worst_trade = min((e.profit_pct for e in closed), default=0)
    total_profit_abs = sum(e.profit_abs or 0 for e in closed)

    # By ticker
    tickers: dict[str, dict] = {}
    for e in closed:
        if e.ticker not in tickers:
            tickers[e.ticker] = {"count": 0, "wins": 0, "total_pct": 0}
        tickers[e.ticker]["count"] += 1
        tickers[e.ticker]["total_pct"] += e.profit_pct
        if e.profit_pct > 0:
            tickers[e.ticker]["wins"] += 1

    top_tickers = sorted(
        [{"ticker": t, "trades": d["count"], "win_rate": d["wins"] / d["count"], "avg_pct": d["total_pct"] / d["count"]}
         for t, d in tickers.items()],
        key=lambda x: x["avg_pct"], reverse=True,
    )[:10]

    # By emotion
    emotions: dict[str, dict] = {}
    for e in closed:
        em = e.emotion or "none"
        if em not in emotions:
            emotions[em] = {"count": 0, "wins": 0}
        emotions[em]["count"] += 1
        if e.profit_pct > 0:
            emotions[em]["wins"] += 1

    return {
        "total_trades": total,
        "closed_trades": len(closed),
        "open_trades": total - len(closed),
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 3),
        "avg_profit_pct": round(avg_profit, 2),
        "best_trade_pct": round(best_trade, 2),
        "worst_trade_pct": round(worst_trade, 2),
        "total_profit_abs": round(total_profit_abs, 2),
        "top_tickers": top_tickers,
        "by_emotion": {k: {"count": v["count"], "win_rate": round(v["wins"] / v["count"], 2)} for k, v in emotions.items()},
    }
