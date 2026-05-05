"""Admin API — user management, role assignment."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User, UserRole

router = APIRouter()


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(403, "Admin access required")
    return user


@router.get("/users")
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """List all users (admin only)."""
    total = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
    )
    users = result.scalars().all()
    return {
        "total": total,
        "items": [
            {
                "id": str(u.id),
                "email": u.email,
                "username": u.username,
                "role": u.role.value,
                "is_active": u.is_active,
                "premium_expires_at": u.premium_expires_at.isoformat() if u.premium_expires_at else None,
                "referral_code": u.referral_code,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
    }


@router.patch("/users/{user_id}/role")
async def set_user_role(
    user_id: uuid.UUID,
    role: UserRole,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Set user role (admin only)."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    user.role = role
    await db.commit()
    await db.refresh(user)
    return {"id": str(user.id), "username": user.username, "role": user.role.value}


@router.patch("/users/{user_id}/active")
async def toggle_user_active(
    user_id: uuid.UUID,
    is_active: bool,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Activate/deactivate user (admin only)."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    user.is_active = is_active
    await db.commit()
    return {"id": str(user.id), "username": user.username, "is_active": user.is_active}


@router.get("/capacity")
async def capacity_report(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Full system capacity report with scaling recommendations (admin only)."""
    from app.services.capacity import capacity_monitor
    return await capacity_monitor.get_full_report(db)


@router.get("/capacity/alert")
async def capacity_alert(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Check if scaling alert is needed (admin only)."""
    from app.services.capacity import capacity_monitor
    alert = await capacity_monitor.check_capacity(db)
    if not alert:
        return {"alert": None}
    return {
        "alert": {
            "level": alert.level,
            "title": alert.title,
            "message": alert.message,
            "current_tier": alert.current_tier,
            "next_tier": alert.next_tier,
            "action_required": alert.action_required,
        }
    }
