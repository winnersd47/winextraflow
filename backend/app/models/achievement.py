"""Achievement & UserAchievement models — gamification system."""

import enum
import uuid

from sqlalchemy import String, Enum, Integer, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AchievementCategory(str, enum.Enum):
    TRADING = "trading"
    SOCIAL = "social"
    LEARNING = "learning"
    MILESTONE = "milestone"


class Achievement(Base):
    __tablename__ = "achievements"

    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(500))
    icon: Mapped[str] = mapped_column(String(10))  # Emoji
    category: Mapped[AchievementCategory] = mapped_column(Enum(AchievementCategory))
    xp_reward: Mapped[int] = mapped_column(Integer, default=0)
    requirement_value: Mapped[int] = mapped_column(Integer, default=1)  # e.g. "reach 10 referrals"
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    achievement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("achievements.id"), index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    is_unlocked: Mapped[bool] = mapped_column(Boolean, default=False)


# ─── Seed achievements ─────────────────────────────────────

SEED_ACHIEVEMENTS = [
    # Trading
    {"code": "first_signal", "name": "First Signal", "description": "View your first trading signal", "icon": "📡", "category": "trading", "xp_reward": 10, "requirement_value": 1},
    {"code": "signal_hunter", "name": "Signal Hunter", "description": "View 50 signals", "icon": "🎯", "category": "trading", "xp_reward": 50, "requirement_value": 50},
    {"code": "first_trade", "name": "First Trade", "description": "Execute your first trade", "icon": "💰", "category": "trading", "xp_reward": 25, "requirement_value": 1},
    {"code": "trader_10", "name": "Active Trader", "description": "Execute 10 trades", "icon": "📈", "category": "trading", "xp_reward": 100, "requirement_value": 10},
    {"code": "trader_100", "name": "Pro Trader", "description": "Execute 100 trades", "icon": "🏆", "category": "trading", "xp_reward": 500, "requirement_value": 100},
    {"code": "win_streak_5", "name": "Hot Streak", "description": "5 winning trades in a row", "icon": "🔥", "category": "trading", "xp_reward": 200, "requirement_value": 5},
    # Social
    {"code": "first_referral", "name": "Networker", "description": "Invite your first friend", "icon": "🤝", "category": "social", "xp_reward": 30, "requirement_value": 1},
    {"code": "referral_5", "name": "Influencer", "description": "Invite 5 friends", "icon": "⭐", "category": "social", "xp_reward": 150, "requirement_value": 5},
    {"code": "referral_25", "name": "Ambassador", "description": "Invite 25 friends", "icon": "👑", "category": "social", "xp_reward": 500, "requirement_value": 25},
    {"code": "first_subscription", "name": "Follower", "description": "Subscribe to your first strategy", "icon": "📋", "category": "social", "xp_reward": 20, "requirement_value": 1},
    # Learning
    {"code": "first_backtest", "name": "Analyst", "description": "Run your first backtest", "icon": "🧪", "category": "learning", "xp_reward": 20, "requirement_value": 1},
    {"code": "strategy_creator", "name": "Strategist", "description": "Publish a strategy on the marketplace", "icon": "🧠", "category": "learning", "xp_reward": 100, "requirement_value": 1},
    # Milestones
    {"code": "level_5", "name": "Rising Star", "description": "Reach Level 5", "icon": "🌟", "category": "milestone", "xp_reward": 0, "requirement_value": 5},
    {"code": "level_10", "name": "Veteran", "description": "Reach Level 10", "icon": "💎", "category": "milestone", "xp_reward": 0, "requirement_value": 10},
]
