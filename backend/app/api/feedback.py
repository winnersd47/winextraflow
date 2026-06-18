"""Feedback API — reviews, feature requests, bug reports, NPS.

Public endpoints for users + admin management.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.feedback import Feedback
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)
router = APIRouter()


# ═══ SCHEMAS ═══

class FeedbackCreate(BaseModel):
    type: str  # review, feature_request, bug_report, suggestion, nps
    text: str
    title: str | None = None
    rating: int | None = None  # 1-5 for reviews
    nps_score: int | None = None  # 0-10 for NPS
    category: str | None = None
    page: str | None = None
    browser_info: str | None = None
    is_public: bool = True


class AdminReply(BaseModel):
    reply: str
    status: str = "reviewed"  # reviewed, in_progress, resolved, wont_fix


# ═══ USER ENDPOINTS ═══

@router.post("", status_code=201)
async def submit_feedback(
    data: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Submit feedback (review, feature request, bug report, NPS)."""
    if data.type not in ("review", "feature_request", "bug_report", "suggestion", "nps"):
        raise HTTPException(400, "Type must be: review, feature_request, bug_report, suggestion, nps")
    if len(data.text.strip()) < 3:
        raise HTTPException(400, "Text too short (min 3 chars)")
    if len(data.text) > 2000:
        raise HTTPException(400, "Text too long (max 2000 chars)")
    if data.rating is not None and (data.rating < 1 or data.rating > 5):
        raise HTTPException(400, "Rating must be 1-5")
    if data.nps_score is not None and (data.nps_score < 0 or data.nps_score > 10):
        raise HTTPException(400, "NPS score must be 0-10")

    # Rate limit: max 5 feedback per day per user
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    count = (await db.execute(
        select(func.count(Feedback.id)).where(
            Feedback.user_id == str(user.id),
            Feedback.created_at >= today_start,
        )
    )).scalar() or 0
    if count >= 5:
        raise HTTPException(429, "Max 5 feedback per day")

    fb = Feedback(
        user_id=str(user.id),
        username=user.username,
        type=data.type,
        text=data.text.strip(),
        title=data.title,
        rating=data.rating,
        nps_score=data.nps_score,
        category=data.category,
        page=data.page,
        browser_info=data.browser_info,
        is_public=data.is_public,
    )

    # Auto-set priority for bug reports
    if data.type == "bug_report":
        fb.priority = "high"

    db.add(fb)
    await db.commit()
    return {"id": fb.id, "status": "submitted"}


@router.get("")
async def list_feedback(
    type: str | None = Query(None),
    status: str | None = Query(None),
    category: str | None = Query(None),
    sort: str = Query("newest"),  # newest, top_voted, highest_rated
    limit: int = Query(20, le=50),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List public feedback with filters."""
    stmt = select(Feedback).where(Feedback.is_public == True)

    if type:
        stmt = stmt.where(Feedback.type == type)
    if status:
        stmt = stmt.where(Feedback.status == status)
    if category:
        stmt = stmt.where(Feedback.category == category)

    if sort == "top_voted":
        stmt = stmt.order_by(Feedback.upvotes.desc())
    elif sort == "highest_rated":
        stmt = stmt.order_by(Feedback.rating.desc().nullslast())
    else:
        stmt = stmt.order_by(Feedback.created_at.desc())

    total = (await db.execute(
        select(func.count(Feedback.id)).where(Feedback.is_public == True)
    )).scalar() or 0

    items = (await db.execute(stmt.offset(offset).limit(limit))).scalars().all()

    return {
        "total": total,
        "items": [_format(f, str(user.id)) for f in items],
    }


@router.get("/my")
async def my_feedback(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List current user's feedback."""
    items = (await db.execute(
        select(Feedback).where(Feedback.user_id == str(user.id)).order_by(Feedback.created_at.desc())
    )).scalars().all()
    return {"items": [_format(f, str(user.id)) for f in items]}


@router.post("/{feedback_id}/upvote")
async def upvote_feedback(
    feedback_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upvote a feedback item (toggle)."""
    fb = (await db.execute(select(Feedback).where(Feedback.id == feedback_id))).scalar_one_or_none()
    if not fb:
        raise HTTPException(404, "Not found")

    uid = str(user.id)
    voters = fb.upvoted_by or []

    if uid in voters:
        voters.remove(uid)
        fb.upvotes = max(0, (fb.upvotes or 0) - 1)
    else:
        voters.append(uid)
        fb.upvotes = (fb.upvotes or 0) + 1

    fb.upvoted_by = voters
    await db.commit()
    return {"upvotes": fb.upvotes, "voted": uid in fb.upvoted_by}


@router.delete("/{feedback_id}")
async def delete_feedback(
    feedback_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete own feedback."""
    fb = (await db.execute(select(Feedback).where(Feedback.id == feedback_id))).scalar_one_or_none()
    if not fb:
        raise HTTPException(404, "Not found")
    if str(fb.user_id) != str(user.id) and user.role != UserRole.ADMIN:
        raise HTTPException(403, "Not your feedback")
    await db.delete(fb)
    await db.commit()
    return {"status": "deleted"}


# ═══ ADMIN ENDPOINTS ═══

@router.post("/{feedback_id}/reply")
async def admin_reply(
    feedback_id: str,
    data: AdminReply,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Admin reply to feedback."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(403, "Admin only")

    fb = (await db.execute(select(Feedback).where(Feedback.id == feedback_id))).scalar_one_or_none()
    if not fb:
        raise HTTPException(404, "Not found")

    fb.admin_reply = data.reply
    fb.admin_reply_at = datetime.now(timezone.utc)
    fb.status = data.status
    await db.commit()
    return {"status": fb.status}


@router.get("/stats")
async def feedback_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Feedback statistics (available to all, detailed to admin)."""
    all_fb = (await db.execute(select(Feedback))).scalars().all()

    total = len(all_fb)
    by_type = {}
    by_status = {}
    ratings = []
    nps_scores = []
    by_category = {}

    for f in all_fb:
        by_type[f.type] = by_type.get(f.type, 0) + 1
        by_status[f.status] = by_status.get(f.status, 0) + 1
        if f.rating:
            ratings.append(f.rating)
        if f.nps_score is not None:
            nps_scores.append(f.nps_score)
        cat = f.category or "other"
        by_category[cat] = by_category.get(cat, 0) + 1

    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None

    # NPS = % promoters (9-10) - % detractors (0-6)
    nps = None
    if nps_scores:
        promoters = sum(1 for s in nps_scores if s >= 9) / len(nps_scores) * 100
        detractors = sum(1 for s in nps_scores if s <= 6) / len(nps_scores) * 100
        nps = round(promoters - detractors)

    # Top voted feature requests
    top_requests = sorted(
        [f for f in all_fb if f.type == "feature_request" and f.is_public],
        key=lambda x: x.upvotes or 0, reverse=True,
    )[:5]

    return {
        "total": total,
        "by_type": by_type,
        "by_status": by_status,
        "by_category": by_category,
        "avg_rating": avg_rating,
        "nps_score": nps,
        "nps_responses": len(nps_scores),
        "top_feature_requests": [
            {"id": f.id, "title": f.title or f.text[:50], "upvotes": f.upvotes, "status": f.status}
            for f in top_requests
        ],
    }


def _format(f: Feedback, current_user_id: str) -> dict:
    return {
        "id": f.id,
        "type": f.type,
        "username": f.username,
        "title": f.title,
        "text": f.text,
        "rating": f.rating,
        "nps_score": f.nps_score,
        "category": f.category,
        "page": f.page,
        "priority": f.priority,
        "status": f.status,
        "upvotes": f.upvotes or 0,
        "voted": current_user_id in (f.upvoted_by or []),
        "is_mine": str(f.user_id) == current_user_id,
        "admin_reply": f.admin_reply,
        "admin_reply_at": f.admin_reply_at.isoformat() if f.admin_reply_at else None,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }
