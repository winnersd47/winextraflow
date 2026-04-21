"""Notification service — create and dispatch in-app notifications."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.notification import Notification, NotificationType

logger = logging.getLogger(__name__)


class NotificationService:
    async def create(
        self,
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        type: NotificationType,
        title: str,
        message: str,
    ) -> Notification:
        n = Notification(user_id=user_id, type=type, title=title, message=message)
        db.add(n)
        await db.commit()
        await db.refresh(n)
        return n

    async def notify_signal(self, user_id: uuid.UUID, ticker: str, action: str):
        async with async_session() as db:
            await self.create(
                db, user_id=user_id, type=NotificationType.SIGNAL,
                title=f"{action.upper()} {ticker}",
                message=f"New signal: {action.upper()} {ticker}",
            )

    async def notify_trade(self, user_id: uuid.UUID, symbol: str, status: str):
        async with async_session() as db:
            await self.create(
                db, user_id=user_id, type=NotificationType.TRADE,
                title=f"Order {status}: {symbol}",
                message=f"Your order for {symbol} has been {status}",
            )

    async def notify_achievement(self, user_id: uuid.UUID, name: str, xp: int):
        async with async_session() as db:
            await self.create(
                db, user_id=user_id, type=NotificationType.ACHIEVEMENT,
                title=f"Achievement: {name}",
                message=f"You unlocked '{name}'! +{xp} XP",
            )

    async def notify_referral(self, user_id: uuid.UUID, username: str, days: int):
        async with async_session() as db:
            await self.create(
                db, user_id=user_id, type=NotificationType.REFERRAL,
                title=f"New referral: {username}",
                message=f"{username} joined via your link! +{days} Premium days",
            )

    async def notify_premium(self, user_id: uuid.UUID, days: int):
        async with async_session() as db:
            await self.create(
                db, user_id=user_id, type=NotificationType.PREMIUM,
                title=f"Premium activated",
                message=f"You received {days} days of Premium access",
            )


notification_service = NotificationService()
