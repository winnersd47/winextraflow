"""Tests for gamification: achievements, XP, levels."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.achievements import AchievementService, calculate_level


def test_calculate_level():
    assert calculate_level(0) == 1
    assert calculate_level(50) == 2
    assert calculate_level(200) == 3
    assert calculate_level(800) == 5


@pytest.mark.asyncio
async def test_seed_achievements(db: AsyncSession):
    service = AchievementService()
    await service.seed_achievements(db)

    from sqlalchemy import select, func
    from app.models.achievement import Achievement

    count = (await db.execute(select(func.count()).select_from(Achievement))).scalar()
    assert count >= 10


@pytest.mark.asyncio
async def test_profile_endpoint(client: AsyncClient, auth_headers: dict, db: AsyncSession):
    # Seed first
    service = AchievementService()
    await service.seed_achievements(db)

    resp = await client.get("/api/v1/achievements/profile", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["xp"]["level"] >= 1
    assert data["total_count"] >= 10
    assert data["unlocked_count"] == 0


@pytest.mark.asyncio
async def test_increment_achievement(db: AsyncSession, registered_user: dict):
    service = AchievementService()
    await service.seed_achievements(db)

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == registered_user["email"]))).scalar_one()

    unlocked = await service.increment_progress(db, user.id, "first_signal")
    assert unlocked is True

    # Second increment should return False (already unlocked)
    unlocked2 = await service.increment_progress(db, user.id, "first_signal")
    assert unlocked2 is False
