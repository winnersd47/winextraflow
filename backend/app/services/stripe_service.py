"""Stripe payment service — checkout sessions and webhook handling."""

import logging

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.payment import Payment, PaymentPlan, PaymentStatus
from app.models.user import User
from app.services.premium import grant_premium_days
from app.services.notifications import notification_service

logger = logging.getLogger(__name__)

PLAN_CONFIG = {
    PaymentPlan.MONTHLY: {"amount": 29.00, "days": 30, "name": "Premium Monthly"},
    PaymentPlan.YEARLY: {"amount": 249.00, "days": 365, "name": "Premium Yearly"},
}


class StripeService:
    def __init__(self):
        if settings.stripe_api_key:
            stripe.api_key = settings.stripe_api_key

    async def create_checkout_session(
        self,
        db: AsyncSession,
        user: User,
        plan: PaymentPlan,
        success_url: str,
        cancel_url: str,
    ) -> dict:
        """Create a Stripe Checkout Session and return the URL."""
        config = PLAN_CONFIG[plan]

        if not settings.stripe_api_key:
            # Demo mode: simulate checkout without real Stripe
            payment = Payment(
                user_id=user.id,
                stripe_session_id=f"demo_session_{user.id}_{plan.value}",
                plan=plan,
                amount=config["amount"],
                currency="usd",
                status=PaymentStatus.PENDING,
            )
            db.add(payment)
            await db.commit()
            await db.refresh(payment)
            return {
                "checkout_url": f"{success_url}?session_id=demo_session_{user.id}_{plan.value}",
                "session_id": payment.stripe_session_id,
                "demo": True,
            }

        # Real Stripe Checkout
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": config["name"]},
                    "unit_amount": int(config["amount"] * 100),
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=cancel_url,
            client_reference_id=str(user.id),
            customer_email=user.email,
            metadata={"plan": plan.value, "user_id": str(user.id)},
        )

        payment = Payment(
            user_id=user.id,
            stripe_session_id=session.id,
            plan=plan,
            amount=config["amount"],
            currency="usd",
            status=PaymentStatus.PENDING,
        )
        db.add(payment)
        await db.commit()

        return {
            "checkout_url": session.url,
            "session_id": session.id,
            "demo": False,
        }

    async def handle_webhook(self, db: AsyncSession, payload: bytes, signature: str) -> dict:
        """Process Stripe webhook event."""
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, settings.stripe_webhook_secret
            )
        except (ValueError, stripe.error.SignatureVerificationError) as e:
            logger.error(f"Stripe webhook error: {e}")
            return {"error": str(e)}

        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            await self._complete_payment(db, session)

        return {"status": "ok", "type": event["type"]}

    async def complete_demo_payment(self, db: AsyncSession, session_id: str) -> Payment | None:
        """Complete a demo payment (no real Stripe)."""
        payment = (await db.execute(
            select(Payment).where(Payment.stripe_session_id == session_id)
        )).scalar_one_or_none()
        if not payment or payment.status != PaymentStatus.PENDING:
            return None

        payment.status = PaymentStatus.COMPLETED
        payment.stripe_payment_id = f"demo_pi_{payment.id}"

        config = PLAN_CONFIG[payment.plan]
        user = await db.get(User, payment.user_id)
        if user:
            await grant_premium_days(db, user, config["days"])
            await notification_service.notify_premium(user.id, config["days"])

        await db.commit()
        await db.refresh(payment)
        logger.info(f"Demo payment completed: {payment.plan.value} for user {payment.user_id}")
        return payment

    async def _complete_payment(self, db: AsyncSession, session: dict):
        """Complete payment after Stripe webhook confirmation."""
        session_id = session["id"]
        payment = (await db.execute(
            select(Payment).where(Payment.stripe_session_id == session_id)
        )).scalar_one_or_none()
        if not payment:
            logger.warning(f"Payment not found for session {session_id}")
            return

        payment.status = PaymentStatus.COMPLETED
        payment.stripe_payment_id = session.get("payment_intent")

        config = PLAN_CONFIG[payment.plan]
        user = await db.get(User, payment.user_id)
        if user:
            await grant_premium_days(db, user, config["days"])
            await notification_service.notify_premium(user.id, config["days"])

        await db.commit()
        logger.info(f"Payment completed: {payment.plan.value} for user {payment.user_id}")


stripe_service = StripeService()
