import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.config import settings
from app.database import get_db
from app.models.referral import Referral, ReferralStatus
from app.models.user import User
from app.services.premium import grant_premium_days
from app.services.notifications import notification_service
from app.schemas.user import Token, UserLogin, UserRegister, UserResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    # Check existing
    result = await db.execute(
        select(User).where((User.email == data.email) | (User.username == data.username))
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email or username already taken")

    # Resolve referrer
    referrer = None
    if data.referral_code:
        result = await db.execute(
            select(User).where(User.referral_code == data.referral_code)
        )
        referrer = result.scalar_one_or_none()
        if not referrer:
            logger.warning(f"Invalid referral code: {data.referral_code}")

    user = User(
        email=data.email,
        username=data.username,
        hashed_password=hash_password(data.password),
        referral_code=secrets.token_urlsafe(8),
        referred_by=referrer.id if referrer else None,
    )
    db.add(user)
    await db.flush()  # Get user.id

    # Create referral records (multi-level)
    if referrer:
        # Level 1: direct referral
        db.add(Referral(
            referrer_id=referrer.id,
            referred_id=user.id,
            level=1,
            status=ReferralStatus.ACTIVE,
            reward_type=settings.referral_reward_type,
            reward_amount=settings.referral_level1_reward,
        ))
        logger.info(f"Referral L1: {referrer.username} -> {user.username}")

        # Grant premium days to referrer
        await grant_premium_days(db, referrer, settings.referral_level1_reward)
        await notification_service.notify_referral(
            referrer.id, user.username, settings.referral_level1_reward
        )

        # Level 2: indirect referral (referrer's referrer)
        if settings.referral_max_levels >= 2 and referrer.referred_by:
            db.add(Referral(
                referrer_id=referrer.referred_by,
                referred_id=user.id,
                level=2,
                status=ReferralStatus.ACTIVE,
                reward_type=settings.referral_reward_type,
                reward_amount=settings.referral_level2_reward,
            ))
            logger.info(f"Referral L2: {referrer.referred_by} -> {user.username}")

    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user
