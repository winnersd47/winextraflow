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
    # ─── Trading ──────────────────────────────────────────
    {
        "code": "first_signal", "name": "First Signal", "icon": "📡",
        "description": "View your first trading signal. Every journey starts with a single step — open any signal to begin learning how the market works. Reward: +10 XP.",
        "category": "trading", "xp_reward": 10, "requirement_value": 1,
    },
    {
        "code": "signal_hunter", "name": "Signal Hunter", "icon": "🎯",
        "description": "View 50 signals. Consistent market analysis is key to profitable trading. The more signals you study, the better you understand patterns and provider quality. Reward: +50 XP.",
        "category": "trading", "xp_reward": 50, "requirement_value": 50,
    },
    {
        "code": "first_trade", "name": "First Trade", "icon": "💰",
        "description": "Execute your first trade on an exchange. Moving from theory to practice — place a real or demo order based on a signal. This unlocks the full power of the platform. Reward: +25 XP.",
        "category": "trading", "xp_reward": 25, "requirement_value": 1,
    },
    {
        "code": "trader_10", "name": "Active Trader", "icon": "📈",
        "description": "Execute 10 trades. You're building real trading experience. At this stage you start noticing which providers and strategies match your risk profile. Reward: +100 XP.",
        "category": "trading", "xp_reward": 100, "requirement_value": 10,
    },
    {
        "code": "trader_100", "name": "Pro Trader", "icon": "🏆",
        "description": "Execute 100 trades. You've reached professional-level activity. With this volume, your portfolio statistics become statistically significant. Providers notice active traders. Reward: +500 XP.",
        "category": "trading", "xp_reward": 500, "requirement_value": 100,
    },
    {
        "code": "win_streak_5", "name": "Hot Streak", "icon": "🔥",
        "description": "Achieve 5 winning trades in a row. Discipline and strategy alignment pay off — this streak proves you're following quality signals with good risk management. Reward: +200 XP.",
        "category": "trading", "xp_reward": 200, "requirement_value": 5,
    },

    # ─── Social ───────────────────────────────────────────
    {
        "code": "first_referral", "name": "Networker", "icon": "🤝",
        "description": "Invite your first friend to WinExtraFlow. You earn 7 days of Premium for each direct invite — your friend gets access, and you unlock advanced features for free. Reward: +30 XP + 7 Premium days.",
        "category": "social", "xp_reward": 30, "requirement_value": 1,
    },
    {
        "code": "referral_5", "name": "Influencer", "icon": "⭐",
        "description": "Invite 5 friends. You're building a trading community! With 5 referrals you've earned 35+ days of Premium — that's more than a month of full access completely free. Reward: +150 XP.",
        "category": "social", "xp_reward": 150, "requirement_value": 5,
    },
    {
        "code": "referral_25", "name": "Ambassador", "icon": "👑",
        "description": "Invite 25 friends. You're an official WinExtraFlow ambassador. Your network earns you 175+ days of Premium, and you help grow the community. Top ambassadors get featured on the leaderboard. Reward: +500 XP.",
        "category": "social", "xp_reward": 500, "requirement_value": 25,
    },
    {
        "code": "first_subscription", "name": "Follower", "icon": "📋",
        "description": "Subscribe to your first strategy on the marketplace. By following a proven provider, you receive their signals directly in your feed — and can enable auto-copy to trade hands-free. Reward: +20 XP.",
        "category": "social", "xp_reward": 20, "requirement_value": 1,
    },

    # ─── Learning ─────────────────────────────────────────
    {
        "code": "first_backtest", "name": "Analyst", "icon": "🧪",
        "description": "Run your first backtest. Before risking real money, test any strategy on historical data. See win rate, Sharpe ratio, max drawdown and equity curve — make data-driven decisions. Reward: +20 XP.",
        "category": "learning", "xp_reward": 20, "requirement_value": 1,
    },
    {
        "code": "strategy_creator", "name": "Strategist", "icon": "🧠",
        "description": "Publish a strategy on the marketplace. Share your trading approach with the community and earn 70% of subscription revenue. Top strategies attract hundreds of subscribers. Reward: +100 XP.",
        "category": "learning", "xp_reward": 100, "requirement_value": 1,
    },

    # ─── Milestones ───────────────────────────────────────
    {
        "code": "level_5", "name": "Rising Star", "icon": "🌟",
        "description": "Reach Level 5. You've consistently engaged with the platform — viewing signals, trading, inviting friends. Level 5 marks the transition from beginner to experienced user.",
        "category": "milestone", "xp_reward": 0, "requirement_value": 5,
    },
    {
        "code": "level_10", "name": "Veteran", "icon": "💎",
        "description": "Reach Level 10. You're among the most active users on WinExtraFlow. Veterans have deep platform knowledge, a track record of trades, and a strong referral network. Respect earned.",
        "category": "milestone", "xp_reward": 0, "requirement_value": 10,
    },
]
