"""Achievement service — tracks progress and unlocks achievements."""

import logging
import math
import uuid

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.achievement import (
    Achievement,
    AchievementCategory,
    UserAchievement,
    SEED_ACHIEVEMENTS,
)

logger = logging.getLogger(__name__)

# XP per level: level N requires N * 100 XP (cumulative)
XP_PER_LEVEL = 100


def calculate_level(total_xp: int) -> int:
    """Calculate user level from total XP. Level = floor(sqrt(xp / 50)) + 1."""
    if total_xp <= 0:
        return 1
    return int(math.sqrt(total_xp / 50)) + 1


def xp_for_next_level(current_level: int) -> int:
    """XP required to reach next level."""
    return (current_level ** 2) * 50


class AchievementService:
    """Manages achievements, progress tracking, and XP."""

    async def seed_achievements(self, db: AsyncSession):
        """Insert seed achievements if they don't exist."""
        for data in SEED_ACHIEVEMENTS:
            existing = (await db.execute(
                select(Achievement).where(Achievement.code == data["code"])
            )).scalar_one_or_none()
            if not existing:
                db.add(Achievement(
                    code=data["code"],
                    name=data["name"],
                    description=data["description"],
                    icon=data["icon"],
                    category=AchievementCategory(data["category"]),
                    xp_reward=data["xp_reward"],
                    requirement_value=data["requirement_value"],
                ))
        await db.commit()
        logger.info(f"Seeded {len(SEED_ACHIEVEMENTS)} achievements")

    async def get_user_achievements(
        self, db: AsyncSession, user_id: uuid.UUID
    ) -> list[dict]:
        """Get all achievements with user progress."""
        # Get all achievements
        result = await db.execute(select(Achievement).order_by(Achievement.category))
        all_achievements = result.scalars().all()

        # Get user progress
        result = await db.execute(
            select(UserAchievement).where(UserAchievement.user_id == user_id)
        )
        user_progress = {ua.achievement_id: ua for ua in result.scalars().all()}

        items = []
        for ach in all_achievements:
            ua = user_progress.get(ach.id)
            items.append({
                "id": str(ach.id),
                "code": ach.code,
                "name": ach.name,
                "description": ach.description,
                "icon": ach.icon,
                "category": ach.category.value,
                "xp_reward": ach.xp_reward,
                "requirement_value": ach.requirement_value,
                "is_hidden": ach.is_hidden,
                "progress": ua.progress if ua else 0,
                "is_unlocked": ua.is_unlocked if ua else False,
            })
        return items

    async def get_user_xp(self, db: AsyncSession, user_id: uuid.UUID) -> dict:
        """Get user's total XP, level, and progress to next level."""
        result = await db.execute(
            select(func.coalesce(func.sum(Achievement.xp_reward), 0))
            .select_from(UserAchievement)
            .join(Achievement, UserAchievement.achievement_id == Achievement.id)
            .where(and_(
                UserAchievement.user_id == user_id,
                UserAchievement.is_unlocked == True,
            ))
        )
        total_xp = result.scalar() or 0
        level = calculate_level(total_xp)
        next_level_xp = xp_for_next_level(level)
        current_level_xp = xp_for_next_level(level - 1) if level > 1 else 0

        return {
            "total_xp": total_xp,
            "level": level,
            "current_level_xp": total_xp - current_level_xp,
            "next_level_xp": next_level_xp - current_level_xp,
            "progress_pct": round(
                (total_xp - current_level_xp) / max(1, next_level_xp - current_level_xp) * 100, 1
            ),
        }

    async def increment_progress(
        self, db: AsyncSession, user_id: uuid.UUID, achievement_code: str, amount: int = 1
    ) -> bool:
        """Increment progress for an achievement. Returns True if newly unlocked."""
        achievement = (await db.execute(
            select(Achievement).where(Achievement.code == achievement_code)
        )).scalar_one_or_none()
        if not achievement:
            return False

        # Get or create user achievement
        ua = (await db.execute(
            select(UserAchievement).where(and_(
                UserAchievement.user_id == user_id,
                UserAchievement.achievement_id == achievement.id,
            ))
        )).scalar_one_or_none()

        if not ua:
            ua = UserAchievement(
                user_id=user_id,
                achievement_id=achievement.id,
                progress=0,
                is_unlocked=False,
            )
            db.add(ua)

        if ua.is_unlocked:
            return False  # Already unlocked

        ua.progress = min(ua.progress + amount, achievement.requirement_value)

        newly_unlocked = False
        if ua.progress >= achievement.requirement_value:
            ua.is_unlocked = True
            newly_unlocked = True
            logger.info(f"Achievement unlocked: {achievement.name} for user {user_id}")

        await db.commit()
        return newly_unlocked


achievement_service = AchievementService()
