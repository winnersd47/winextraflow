"""YooKassa payment service — create payments, handle webhooks.

YooKassa (ЮKassa) — Russian payment system supporting:
- Bank cards (Visa, MasterCard, МИР)
- СБП (Система быстрых платежей) — 0.7% commission
- ЮMoney wallet
- SberPay
- Installments (Яндекс Сплит)

API docs: https://yookassa.ru/developers/api
"""

import logging
import uuid as uuid_lib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.payment import Payment, PaymentPlan, PaymentStatus
from app.models.user import User
from app.services.premium import grant_premium_days
from app.services.notifications import notification_service

logger = logging.getLogger(__name__)

# Pricing in RUB (3-tier system)
PLAN_CONFIG = {
    PaymentPlan.MONTHLY: {"amount": 2990, "days": 30, "name_ru": "Premium Месяц", "name_en": "Premium Monthly"},
    PaymentPlan.YEARLY: {"amount": 23900, "days": 365, "name_ru": "Premium Год", "name_en": "Premium Yearly"},
}

# Pro tier (lower price, limited features)
PRO_CONFIG = {
    "monthly": {"amount": 1490, "days": 30, "name_ru": "Pro Месяц", "name_en": "Pro Monthly"},
    "yearly": {"amount": 11900, "days": 365, "name_ru": "Pro Год", "name_en": "Pro Yearly"},
}


class YooKassaService:
    """YooKassa payment integration."""

    def __init__(self):
        self._configured = False
        if settings.yookassa_shop_id and settings.yookassa_secret_key:
            try:
                from yookassa import Configuration
                Configuration.account_id = settings.yookassa_shop_id
                Configuration.secret_key = settings.yookassa_secret_key
                self._configured = True
                logger.info("YooKassa configured")
            except ImportError:
                logger.warning("yookassa package not installed. Run: pip install yookassa")

    async def create_payment(
        self,
        db: AsyncSession,
        user: User,
        plan: PaymentPlan,
        return_url: str,
    ) -> dict:
        """Create a YooKassa payment and return confirmation URL."""
        config = PLAN_CONFIG[plan]
        idempotency_key = str(uuid_lib.uuid4())

        if not self._configured:
            # Demo mode
            demo_id = f"demo_{user.id}_{plan.value}_{idempotency_key[:8]}"
            payment = Payment(
                user_id=user.id,
                yookassa_payment_id=demo_id,
                plan=plan,
                amount=config["amount"],
                currency="rub",
                status=PaymentStatus.PENDING,
            )
            db.add(payment)
            await db.commit()
            await db.refresh(payment)
            return {
                "payment_url": f"{return_url}?payment_id={demo_id}",
                "payment_id": demo_id,
                "demo": True,
                "amount": config["amount"],
                "currency": "RUB",
            }

        # Real YooKassa payment
        from yookassa import Payment as YKPayment

        yk_payment = YKPayment.create({
            "amount": {
                "value": f"{config['amount']:.2f}",
                "currency": "RUB",
            },
            "confirmation": {
                "type": "redirect",
                "return_url": return_url,
            },
            "capture": True,
            "description": config["name_ru"],
            "metadata": {
                "user_id": str(user.id),
                "plan": plan.value,
            },
        }, idempotency_key)

        payment = Payment(
            user_id=user.id,
            yookassa_payment_id=yk_payment.id,
            plan=plan,
            amount=config["amount"],
            currency="rub",
            status=PaymentStatus.PENDING,
        )
        db.add(payment)
        await db.commit()

        return {
            "payment_url": yk_payment.confirmation.confirmation_url,
            "payment_id": yk_payment.id,
            "demo": False,
            "amount": config["amount"],
            "currency": "RUB",
        }

    async def handle_webhook(self, db: AsyncSession, body: dict) -> dict:
        """Process YooKassa webhook notification."""
        event_type = body.get("event")
        payment_data = body.get("object", {})
        payment_id = payment_data.get("id")

        if not payment_id:
            return {"error": "No payment ID"}

        if event_type == "payment.succeeded":
            await self._complete_payment(db, payment_id, payment_data)
            return {"status": "ok", "event": event_type}
        elif event_type == "payment.canceled":
            await self._fail_payment(db, payment_id)
            return {"status": "ok", "event": event_type}

        return {"status": "ignored", "event": event_type}

    async def complete_demo_payment(self, db: AsyncSession, payment_id: str) -> Payment | None:
        """Complete a demo payment (for testing)."""
        payment = (await db.execute(
            select(Payment).where(Payment.yookassa_payment_id == payment_id)
        )).scalar_one_or_none()

        if not payment or payment.status != PaymentStatus.PENDING:
            return None

        payment.status = PaymentStatus.COMPLETED
        config = PLAN_CONFIG[payment.plan]
        user = await db.get(User, payment.user_id)
        if user:
            await grant_premium_days(db, user, config["days"])
            await notification_service.notify_premium(user.id, config["days"])

        await db.commit()
        await db.refresh(payment)
        logger.info(f"Demo payment completed: {payment.plan.value} for user {payment.user_id}")
        return payment

    async def _complete_payment(self, db: AsyncSession, payment_id: str, data: dict):
        """Complete payment after YooKassa webhook."""
        payment = (await db.execute(
            select(Payment).where(Payment.yookassa_payment_id == payment_id)
        )).scalar_one_or_none()

        if not payment:
            logger.warning(f"Payment not found: {payment_id}")
            return

        payment.status = PaymentStatus.COMPLETED
        config = PLAN_CONFIG[payment.plan]
        user = await db.get(User, payment.user_id)
        if user:
            await grant_premium_days(db, user, config["days"])
            await notification_service.notify_premium(user.id, config["days"])

        await db.commit()
        logger.info(f"YooKassa payment completed: {payment.plan.value} for user {payment.user_id}, amount={payment.amount} RUB")

    async def _fail_payment(self, db: AsyncSession, payment_id: str):
        """Mark payment as failed."""
        payment = (await db.execute(
            select(Payment).where(Payment.yookassa_payment_id == payment_id)
        )).scalar_one_or_none()

        if payment:
            payment.status = PaymentStatus.FAILED
            await db.commit()
            logger.info(f"YooKassa payment failed: {payment_id}")


yookassa_service = YooKassaService()
