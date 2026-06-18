"""Social API — comments on signals, likes on strategies, trader profiles."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.social import SignalComment, StrategyLike
from app.models.signal import Signal
from app.models.journal import JournalEntry
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Comments ──────────────────────────────────────────────

class CommentCreate(BaseModel):
    text: str


@router.get("/signals/{signal_id}/comments")
async def list_comments(
    signal_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List comments for a signal."""
    stmt = (
        select(SignalComment)
        .where(SignalComment.signal_id == signal_id)
        .order_by(SignalComment.created_at.asc())
        .limit(50)
    )
    comments = (await db.execute(stmt)).scalars().all()
    return {
        "total": len(comments),
        "items": [
            {
                "id": c.id,
                "username": c.username,
                "text": c.text,
                "is_mine": str(c.user_id) == str(user.id),
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in comments
        ],
    }


@router.post("/signals/{signal_id}/comments", status_code=201)
async def create_comment(
    signal_id: str,
    data: CommentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Add a comment to a signal."""
    text = data.text.strip()
    if len(text) < 1 or len(text) > 500:
        raise HTTPException(400, "Comment must be 1-500 characters")

    # Verify signal exists
    signal = (await db.execute(select(Signal).where(Signal.id == signal_id))).scalar_one_or_none()
    if not signal:
        raise HTTPException(404, "Signal not found")

    comment = SignalComment(
        signal_id=signal_id,
        user_id=str(user.id),
        username=user.username,
        text=text,
    )
    db.add(comment)
    await db.commit()
    return {"id": comment.id, "status": "created"}


@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete own comment."""
    comment = (await db.execute(
        select(SignalComment).where(SignalComment.id == comment_id)
    )).scalar_one_or_none()
    if not comment:
        raise HTTPException(404, "Comment not found")
    if str(comment.user_id) != str(user.id) and user.role != "admin":
        raise HTTPException(403, "Not your comment")
    await db.delete(comment)
    await db.commit()
    return {"status": "deleted"}


# ─── Likes ─────────────────────────────────────────────────

@router.post("/strategies/{strategy_id}/like")
async def toggle_like(
    strategy_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Toggle like on a strategy (like/unlike)."""
    existing = (await db.execute(
        select(StrategyLike).where(
            StrategyLike.strategy_id == strategy_id,
            StrategyLike.user_id == str(user.id),
        )
    )).scalar_one_or_none()

    if existing:
        await db.delete(existing)
        await db.commit()
        return {"liked": False}

    like = StrategyLike(strategy_id=strategy_id, user_id=str(user.id))
    db.add(like)
    await db.commit()
    return {"liked": True}


@router.get("/strategies/{strategy_id}/likes")
async def get_likes(
    strategy_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get like count and whether current user liked."""
    count = (await db.execute(
        select(func.count(StrategyLike.id)).where(StrategyLike.strategy_id == strategy_id)
    )).scalar() or 0

    liked = (await db.execute(
        select(StrategyLike).where(
            StrategyLike.strategy_id == strategy_id,
            StrategyLike.user_id == str(user.id),
        )
    )).scalar_one_or_none() is not None

    return {"count": count, "liked": liked}


# ─── Trader Profile ───────────────────────────────────────

@router.get("/profile/{username}")
async def trader_profile(
    username: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Public trader profile with stats from journal."""
    target = (await db.execute(
        select(User).where(User.username == username)
    )).scalar_one_or_none()
    if not target:
        raise HTTPException(404, "User not found")

    # Journal stats
    entries = (await db.execute(
        select(JournalEntry).where(JournalEntry.user_id == str(target.id))
    )).scalars().all()

    closed = [e for e in entries if e.profit_pct is not None]
    total = len(closed)
    wins = sum(1 for e in closed if e.profit_pct > 0)
    win_rate = wins / total if total else 0
    avg_profit = sum(e.profit_pct for e in closed) / total if total else 0

    # Top tickers
    tickers: dict[str, int] = {}
    for e in entries:
        tickers[e.ticker] = tickers.get(e.ticker, 0) + 1
    top = sorted(tickers.items(), key=lambda x: x[1], reverse=True)[:5]

    # Comments count
    comments_count = (await db.execute(
        select(func.count(SignalComment.id)).where(SignalComment.user_id == str(target.id))
    )).scalar() or 0

    return {
        "username": target.username,
        "role": target.role.value if hasattr(target.role, "value") else str(target.role),
        "member_since": target.created_at.isoformat() if target.created_at else None,
        "total_trades": total,
        "win_rate": round(win_rate, 3),
        "avg_profit_pct": round(avg_profit, 2),
        "top_tickers": [{"ticker": t, "count": c} for t, c in top],
        "comments_count": comments_count,
    }
