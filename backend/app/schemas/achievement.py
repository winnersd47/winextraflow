from pydantic import BaseModel


class AchievementResponse(BaseModel):
    id: str
    code: str
    name: str
    description: str
    icon: str
    category: str
    xp_reward: int
    requirement_value: int
    is_hidden: bool
    progress: int
    is_unlocked: bool


class UserXP(BaseModel):
    total_xp: int
    level: int
    current_level_xp: int
    next_level_xp: int
    progress_pct: float


class ProfileResponse(BaseModel):
    xp: UserXP
    achievements: list[AchievementResponse]
    unlocked_count: int
    total_count: int
