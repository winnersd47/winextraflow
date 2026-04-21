"""Notifications API — list, read, unread count."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationList, NotificationResponse, UnreadCount

router = APIRouter()


@router.get("", response_model=NotificationList)
async def list_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    total = (await db.execute(
        select(func.count()).select_from(Notification).where(Notification.user_id == user.id)
    )).scalar() or 0
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .offset(skip).limit(limit)
    )
    return NotificationList(items=result.scalars().all(), total=total)


@router.get("/unread-count", response_model=UnreadCount)
async def unread_count(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    count = (await db.execute(
        select(func.count()).select_from(Notification).where(and_(
            Notification.user_id == user.id,
            Notification.is_read == False,
        ))
    )).scalar() or 0
    return UnreadCount(count=count)


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_read(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    n = (await db.execute(
        select(Notification).where(and_(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        ))
    )).scalar_one_or_none()
    if not n:
        raise HTTPException(404, "Notification not found")
    n.is_read = True
    await db.commit()
    await db.refresh(n)
    return n


@router.patch("/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Notification).where(and_(
            Notification.user_id == user.id,
            Notification.is_read == False,
        ))
    )
    for n in result.scalars().all():
        n.is_read = True
    await db.commit()
    return {"status": "ok"}
