"""Achievements & Gamification API."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.achievement import ProfileResponse
from app.services.achievements import achievement_service

router = APIRouter()


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get user profile with XP, level, and achievements."""
    xp = await achievement_service.get_user_xp(db, user.id)
    achievements = await achievement_service.get_user_achievements(db, user.id)
    unlocked = sum(1 for a in achievements if a["is_unlocked"])

    return ProfileResponse(
        xp=xp,
        achievements=achievements,
        unlocked_count=unlocked,
        total_count=len(achievements),
    )
