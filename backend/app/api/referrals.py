"""Referral system API — stats, share links, referral tree."""

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models.referral import Referral
from app.models.user import User
from app.schemas.referral import (
    ReferralStats,
    ReferralTree,
    ReferralTreeItem,
    ReferralUserInfo,
)

router = APIRouter()


@router.get("/stats", response_model=ReferralStats)
async def referral_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get referral statistics for the current user."""
    # Count by level
    l1_count = (await db.execute(
        select(func.count()).select_from(Referral).where(
            and_(Referral.referrer_id == user.id, Referral.level == 1)
        )
    )).scalar() or 0

    l2_count = (await db.execute(
        select(func.count()).select_from(Referral).where(
            and_(Referral.referrer_id == user.id, Referral.level == 2)
        )
    )).scalar() or 0

    # Total rewards
    total_rewards = (await db.execute(
        select(func.coalesce(func.sum(Referral.reward_amount), 0.0)).where(
            Referral.referrer_id == user.id
        )
    )).scalar() or 0.0

    return ReferralStats(
        referral_code=user.referral_code or "",
        share_link=f"{settings.referral_base_url}?ref={user.referral_code}",
        total_referrals=l1_count + l2_count,
        level1_count=l1_count,
        level2_count=l2_count,
        total_rewards=total_rewards,
        reward_type=settings.referral_reward_type,
    )


@router.get("/my-code")
async def my_code(user: User = Depends(get_current_user)):
    """Get the current user's referral code and share link."""
    return {
        "referral_code": user.referral_code,
        "share_link": f"{settings.referral_base_url}?ref={user.referral_code}",
    }


@router.get("/tree", response_model=ReferralTree)
async def referral_tree(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get the referral tree for the current user (all levels)."""
    result = await db.execute(
        select(Referral)
        .where(Referral.referrer_id == user.id)
        .order_by(Referral.level, Referral.created_at.desc())
    )
    referrals = result.scalars().all()

    items = []
    for ref in referrals:
        referred_user = await db.get(User, ref.referred_id)
        if referred_user:
            items.append(ReferralTreeItem(
                user=ReferralUserInfo(
                    id=referred_user.id,
                    username=referred_user.username,
                    email=referred_user.email,
                    created_at=referred_user.created_at,
                ),
                level=ref.level,
                status=ref.status,
                reward_type=ref.reward_type,
                reward_amount=ref.reward_amount,
                created_at=ref.created_at,
            ))

    return ReferralTree(referrals=items, total=len(items))
