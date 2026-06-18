"""Portfolio API — aggregated view of user's open positions and P&L."""

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.journal import JournalEntry
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/summary")
async def portfolio_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Portfolio overview: open positions, total P&L, allocation."""
    uid = str(user.id)

    # Get open journal entries (no exit_price)
    open_stmt = select(JournalEntry).where(
        JournalEntry.user_id == uid,
        JournalEntry.exit_price.is_(None),
    )
    open_entries = (await db.execute(open_stmt)).scalars().all()

    # Get closed journal entries
    closed_stmt = select(JournalEntry).where(
        JournalEntry.user_id == uid,
        JournalEntry.exit_price.isnot(None),
    )
    closed_entries = (await db.execute(closed_stmt)).scalars().all()

    # Open positions from journal
    positions = []
    total_invested = 0
    for e in open_entries:
        value = (e.entry_price or 0) * (e.quantity or 1)
        total_invested += value
        positions.append({
            "id": e.id,
            "ticker": e.ticker,
            "action": e.action,
            "entry_price": e.entry_price,
            "quantity": e.quantity or 1,
            "value": round(value, 2),
            "opened_at": e.opened_at.isoformat() if e.opened_at else None,
            "note": e.note,
        })

    # Closed P&L
    total_realized_pnl = sum(e.profit_abs or 0 for e in closed_entries)
    total_trades = len(closed_entries)
    wins = sum(1 for e in closed_entries if (e.profit_pct or 0) > 0)
    win_rate = wins / total_trades if total_trades > 0 else 0

    # Allocation by ticker
    allocation: dict[str, float] = {}
    for p in positions:
        allocation[p["ticker"]] = allocation.get(p["ticker"], 0) + p["value"]

    # Allocation as percentages
    alloc_pct = {}
    if total_invested > 0:
        for ticker, val in allocation.items():
            alloc_pct[ticker] = round(val / total_invested * 100, 1)

    # Equity curve from closed trades (cumulative P&L)
    equity_curve = []
    cum_pnl = 0
    sorted_closed = sorted(closed_entries, key=lambda e: e.closed_at or e.created_at or datetime.min)
    for e in sorted_closed:
        cum_pnl += e.profit_abs or 0
        equity_curve.append({
            "date": (e.closed_at or e.created_at).isoformat() if (e.closed_at or e.created_at) else None,
            "pnl": round(cum_pnl, 2),
            "ticker": e.ticker,
        })

    return {
        "open_positions": len(positions),
        "total_invested": round(total_invested, 2),
        "total_realized_pnl": round(total_realized_pnl, 2),
        "total_trades": total_trades,
        "win_rate": round(win_rate, 3),
        "filled_orders": 0,
        "pending_orders": 0,
        "positions": positions,
        "allocation": alloc_pct,
        "equity_curve": equity_curve[-50:],  # Last 50 points
    }
