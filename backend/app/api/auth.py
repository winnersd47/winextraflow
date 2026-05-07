import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
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
limiter = Limiter(key_func=get_remote_address, enabled=settings.app_env != "test")


@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit("5/minute")
async def register(request: Request, data: UserRegister, db: AsyncSession = Depends(get_db)):
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

    # Send welcome email
    try:
        from app.services.email_service import email_service
        email_service.send_welcome(user.email, user.username)
    except Exception as e:
        logger.warning(f"Failed to send welcome email: {e}")

    return user


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
async def login(request: Request, data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user


@router.get("/telegram-link")
async def get_telegram_link(user: User = Depends(get_current_user)):
    """Get Telegram bot link for account linking."""
    from app.services.telegram_bot import telegram_bot
    if not telegram_bot.enabled:
        return {"enabled": False, "link": None, "linked": False}
    bot_link = f"https://t.me/{settings.telegram_bot_token.split(':')[0]}?start=link_{user.username}" if telegram_bot.enabled else None
    # Get bot username properly
    return {
        "enabled": True,
        "link": f"https://t.me/WinExtraFlowBot?start=link_{user.username}",
        "linked": user.telegram_chat_id is not None,
        "notifications": user.telegram_notifications,
    }


@router.patch("/telegram-notifications")
async def toggle_telegram_notifications(
    enabled: bool,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Toggle Telegram notifications."""
    user.telegram_notifications = enabled
    await db.commit()
    return {"telegram_notifications": user.telegram_notifications}


# ─── Password Reset ───────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

@router.post("/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(request: Request, data: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Send password reset email."""
    from app.services.email_service import email_service
    import jwt as pyjwt
    from datetime import datetime, timedelta, timezone

    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user:
        # Don't reveal whether email exists
        return {"message": "If the email exists, a reset link has been sent"}

    # Create reset token (expires in 1 hour)
    token = pyjwt.encode(
        {"sub": str(user.id), "type": "reset", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    email_service.send_password_reset(user.email, user.username, token)
    return {"message": "If the email exists, a reset link has been sent"}


@router.post("/reset-password")
@limiter.limit("5/minute")
async def reset_password(request: Request, data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Reset password using token from email."""
    import jwt as pyjwt

    try:
        payload = pyjwt.decode(data.token, settings.secret_key, algorithms=[settings.algorithm])
        if payload.get("type") != "reset":
            raise HTTPException(400, "Invalid token type")
        user_id = payload["sub"]
    except pyjwt.PyJWTError:
        raise HTTPException(400, "Invalid or expired reset token")

    from uuid import UUID
    user = await db.get(User, UUID(user_id))
    if not user:
        raise HTTPException(404, "User not found")

    user.hashed_password = hash_password(data.new_password)
    await db.commit()
    return {"message": "Password reset successfully"}
