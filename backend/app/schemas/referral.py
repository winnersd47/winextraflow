import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.referral import ReferralStatus


class ReferralResponse(BaseModel):
    id: uuid.UUID
    referrer_id: uuid.UUID
    referred_id: uuid.UUID
    level: int
    status: ReferralStatus
    reward_type: str | None
    reward_amount: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReferralUserInfo(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ReferralTreeItem(BaseModel):
    user: ReferralUserInfo
    level: int
    status: ReferralStatus
    reward_type: str | None
    reward_amount: float | None
    created_at: datetime


class ReferralStats(BaseModel):
    referral_code: str
    share_link: str
    total_referrals: int
    level1_count: int
    level2_count: int
    total_rewards: float
    reward_type: str


class ReferralTree(BaseModel):
    referrals: list[ReferralTreeItem]
    total: int
