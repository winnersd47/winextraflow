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

    # Resolve referrer (required)
    result = await db.execute(
        select(User).where(User.referral_code == data.referral_code)
    )
    referrer = result.scalar_one_or_none()
    if not referrer:
        raise HTTPException(status_code=400, detail="Invalid referral code. A valid referral code is required to register.")

    user = User(
        email=data.email,
        username=data.username,
        hashed_password=hash_password(data.password),
        referral_code=secrets.token_urlsafe(8),
        referred_by=referrer.id,
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
        logger.info(f"Referral L1: {referrer.id} -> {user.id}")

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
            logger.info(f"Referral L2: {referrer.referred_by} -> {user.id}")

    await db.commit()
    await db.refresh(user)

    # Send welcome email + verification
    try:
        import secrets as _s
        from app.services.email_service import email_service
        token = _s.token_urlsafe(32)
        user.email_verification_token = token
        await db.commit()
        email_service.send_verification(user.email, user.username, token)
        email_service.send_welcome(user.email, user.username)
    except Exception as e:
        logger.warning(f"Failed to send welcome/verification email: {e}")

    # Achievement: referrer gets "first_referral" progress
    if referrer:
        try:
            from app.services.achievements import achievement_service
            await achievement_service.increment_progress(db, referrer.id, "first_referral")
            await achievement_service.increment_progress(db, referrer.id, "referral_5")
            await achievement_service.increment_progress(db, referrer.id, "referral_25")
        except Exception as e:
            logger.debug(f"Achievement hook error: {e}")

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


@router.get("/verify-email")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    """Verify email address via token from email link."""
    if not token:
        raise HTTPException(400, "Token required")
    user = (await db.execute(
        select(User).where(User.email_verification_token == token)
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(400, "Invalid or expired verification token")
    user.email_verified = True
    user.email_verification_token = None
    await db.commit()
    return {"status": "verified", "email": user.email}


@router.post("/resend-verification")
async def resend_verification(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Resend email verification link."""
    if user.email_verified:
        return {"status": "already_verified"}
    import secrets as _s
    from app.services.email_service import email_service
    token = _s.token_urlsafe(32)
    user.email_verification_token = token
    await db.commit()
    email_service.send_verification(user.email, user.username, token)
    return {"status": "sent"}


@router.patch("/profile")
async def update_profile(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    username: str | None = None,
    email: str | None = None,
    current_password: str | None = None,
    new_password: str | None = None,
):
    """Update user profile — username, email, password."""
    if username and username != user.username:
        existing = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
        if existing:
            raise HTTPException(400, "Username already taken")
        user.username = username
    if email and email != user.email:
        existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if existing:
            raise HTTPException(400, "Email already taken")
        user.email = email
    if new_password:
        if len(new_password) < 8:
            raise HTTPException(400, "Password must be at least 8 characters")
        if not current_password or not verify_password(current_password, user.hashed_password):
            raise HTTPException(400, "Current password is incorrect")
        user.hashed_password = hash_password(new_password)
    await db.commit()
    await db.refresh(user)
    return {"username": user.username, "email": user.email, "message": "Profile updated"}


@router.get("/stats")
async def user_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get user trading statistics."""
    from sqlalchemy import func, and_
    from app.models.order import Order, OrderStatus
    from app.models.signal import Signal
    from app.services.premium import is_premium as check_premium, premium_days_left
    from app.models.kyc import KYCVerification, KYCStatus

    total_orders = (await db.execute(
        select(func.count()).select_from(Order).where(Order.user_id == user.id)
    )).scalar() or 0

    filled_orders = (await db.execute(
        select(func.count()).select_from(Order).where(and_(
            Order.user_id == user.id, Order.status == OrderStatus.FILLED
        ))
    )).scalar() or 0

    # KYC status
    kyc = (await db.execute(
        select(KYCVerification).where(KYCVerification.user_id == user.id)
    )).scalar_one_or_none()

    return {
        "username": user.username,
        "email": user.email,
        "role": user.role.value,
        "referral_code": user.referral_code,
        "is_premium": check_premium(user),
        "premium_days_left": premium_days_left(user),
        "kyc_verified": user.kyc_verified,
        "kyc_status": kyc.status.value if kyc else "none",
        "total_orders": total_orders,
        "filled_orders": filled_orders,
        "member_since": user.created_at.isoformat() if user.created_at else None,
        "telegram_linked": user.telegram_chat_id is not None,
    }


@router.delete("/account")
async def delete_account(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete user account and all associated data per privacy policy."""
    from sqlalchemy import delete as sql_delete
    from app.models.notification import Notification
    from app.models.order import Order
    from app.models.copy_trade import CopyTrade
    from app.models.subscription import Subscription
    from app.models.referral import Referral
    from app.models.achievement import UserAchievement
    from app.models.kyc import KYCVerification
    from app.models.backtest_report import BacktestReport
    from app.models.course_access import CourseAccess
    import os

    uid = user.id

    # Delete KYC photos from disk
    kyc_records = (await db.execute(select(KYCVerification).where(KYCVerification.user_id == uid))).scalars().all()
    for kyc in kyc_records:
        if kyc.photo_path and os.path.exists(kyc.photo_path):
            try:
                os.remove(kyc.photo_path)
            except OSError:
                pass

    # Delete all associated records
    await db.execute(sql_delete(Notification).where(Notification.user_id == uid))
    await db.execute(sql_delete(Order).where(Order.user_id == uid))
    await db.execute(sql_delete(CopyTrade).where(CopyTrade.subscriber_id == uid))
    await db.execute(sql_delete(Subscription).where(Subscription.user_id == uid))
    await db.execute(sql_delete(Referral).where(Referral.referrer_id == uid))
    await db.execute(sql_delete(Referral).where(Referral.referred_id == uid))
    await db.execute(sql_delete(UserAchievement).where(UserAchievement.user_id == uid))
    await db.execute(sql_delete(KYCVerification).where(KYCVerification.user_id == uid))
    await db.execute(sql_delete(BacktestReport).where(BacktestReport.user_id == uid))
    await db.execute(sql_delete(CourseAccess).where(CourseAccess.user_id == uid))

    # Anonymize user record (keep for referral integrity, anonymized)
    user.is_active = False
    user.email = f"deleted_{uid}@deleted"
    user.username = f"deleted_{uid}"
    user.hashed_password = "DELETED"
    user.telegram_chat_id = None
    user.max_chat_id = None
    user.referral_code = None
    user.kyc_verified = False
    user.premium_expires_at = None

    await db.commit()
    logger.info(f"Account deleted: {uid} — all PII and associated data removed")
    return {"message": "Account and all personal data have been permanently deleted."}


@router.get("/telegram-link")
async def get_telegram_link(user: User = Depends(get_current_user)):
    """Get Telegram bot link for account linking."""
    from app.services.telegram_bot import telegram_bot
    if not telegram_bot.enabled:
        return {"enabled": False, "link": None, "linked": False}
    return {
        "enabled": True,
        "link": f"https://t.me/WinExtraFlowBot?start=link_{user.username}",
        "linked": user.telegram_chat_id is not None,
        "notifications": user.telegram_notifications,
    }


@router.get("/max-link")
async def get_max_link(user: User = Depends(get_current_user)):
    """Get MAX Messenger bot link for account linking."""
    from app.services.max_bot import max_bot
    if not max_bot.enabled:
        return {"enabled": False, "link": None, "linked": False}
    return {
        "enabled": True,
        "link": f"https://max.ru/WinExtraFlowBot?start=link_{user.username}",
        "linked": user.max_chat_id is not None,
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

    if len(data.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    user.hashed_password = hash_password(data.new_password)
    await db.commit()
    return {"message": "Password reset successfully"}
