"""Premium service — manage premium status, grant days, check limits."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole


def is_premium(user: User) -> bool:
    """Check if user has active premium access."""
    if user.role == UserRole.ADMIN:
        return True
    if user.role == UserRole.PREMIUM:
        return True
    if user.premium_expires_at and user.premium_expires_at > datetime.now(timezone.utc):
        return True
    return False


def premium_days_left(user: User) -> int:
    """Get number of premium days remaining."""
    if user.role in (UserRole.PREMIUM, UserRole.ADMIN):
        return 999
    if not user.premium_expires_at:
        return 0
    delta = user.premium_expires_at - datetime.now(timezone.utc)
    return max(0, delta.days)


async def grant_premium_days(db: AsyncSession, user: User, days: int) -> User:
    """Grant premium days to a user. Extends if already premium."""
    now = datetime.now(timezone.utc)
    if user.premium_expires_at and user.premium_expires_at > now:
        user.premium_expires_at = user.premium_expires_at + timedelta(days=days)
    else:
        user.premium_expires_at = now + timedelta(days=days)
    await db.commit()
    await db.refresh(user)
    return user


# Free tier limits
FREE_LIMITS = {
    "signals_visible": 10,
    "backtests_per_day": 1,
    "execution_allowed": False,
    "copy_trading_allowed": False,
    "premium_strategies_allowed": False,
}
