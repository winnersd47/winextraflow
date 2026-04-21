"""Premium API — status, activation."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.premium import ActivatePremium, PremiumStatus
from app.services.premium import grant_premium_days, is_premium, premium_days_left
from app.services.notifications import notification_service

router = APIRouter()

PROMO_CODES = {
    "WELCOME7": 7,
    "PREMIUM30": 30,
    "TRIAL3": 3,
}


@router.get("/status", response_model=PremiumStatus)
async def premium_status(user: User = Depends(get_current_user)):
    return PremiumStatus(
        is_premium=is_premium(user),
        days_left=premium_days_left(user),
        role=user.role.value,
        expires_at=user.premium_expires_at.isoformat() if user.premium_expires_at else None,
    )


@router.post("/activate", response_model=PremiumStatus)
async def activate_premium(
    data: ActivatePremium,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    days = 0

    if data.promo_code:
        days = PROMO_CODES.get(data.promo_code.upper(), 0)
        if not days:
            raise HTTPException(400, "Invalid promo code")

    if data.days and user.role == UserRole.ADMIN:
        days = data.days

    if days <= 0:
        raise HTTPException(400, "No days to activate")

    user = await grant_premium_days(db, user, days)
    await notification_service.notify_premium(user.id, days)

    return PremiumStatus(
        is_premium=is_premium(user),
        days_left=premium_days_left(user),
        role=user.role.value,
        expires_at=user.premium_expires_at.isoformat() if user.premium_expires_at else None,
    )
