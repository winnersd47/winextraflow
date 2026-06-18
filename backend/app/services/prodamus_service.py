"""Prodamus payment service — accept USD/EUR cards from international clients.

Docs: https://help.prodamus.ru/payform/integracii/rest-api
Features:
- Visa/MasterCard/Maestro in USD, EUR, RUB
- Works with self-employed (самозанятый) — 1₽ setup
- Auto-integration with "Мой налог" app
- Built-in fiscal receipts (онлайн-касса)
- Commission: 3.5-5%
"""

import logging
import hashlib
import hmac
import uuid as uuid_lib

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.payment import Payment, PaymentPlan, PaymentStatus
from app.models.user import User
from app.services.premium import grant_premium_days
from app.services.notifications import notification_service

logger = logging.getLogger(__name__)

PLAN_CONFIG = {
    PaymentPlan.MONTHLY: {"amount_usd": 33.0, "amount_eur": 30.0, "days": 30, "name": "Premium Monthly"},
    PaymentPlan.YEARLY: {"amount_usd": 264.0, "amount_eur": 240.0, "days": 365, "name": "Premium Yearly"},
}

PRO_CONFIG = {
    "monthly": {"amount_usd": 16.0, "amount_eur": 15.0, "days": 30, "name": "Pro Monthly"},
    "yearly": {"amount_usd": 128.0, "amount_eur": 120.0, "days": 365, "name": "Pro Yearly"},
}


class ProdamusService:
    """Prodamus fiat payment integration for international clients."""

    def __init__(self):
        self.secret = settings.prodamus_secret_key
        self.payform_url = settings.prodamus_payform_url  # e.g. "https://winextraflow.payform.ru"
        self._configured = bool(self.secret and self.payform_url)
        if self._configured:
            logger.info("Prodamus configured")

    async def create_payment(
        self,
        db: AsyncSession,
        user: User,
        plan: PaymentPlan,
        currency: str = "usd",
        return_url: str = "",
    ) -> dict:
        """Create a Prodamus payment link."""
        config = PLAN_CONFIG[plan]
        order_id = f"wef_{user.id}_{plan.value}_{uuid_lib.uuid4().hex[:8]}"

        if currency.lower() == "eur":
            amount = config["amount_eur"]
            curr = "EUR"
        else:
            amount = config["amount_usd"]
            curr = "USD"

        if not self._configured:
            # Demo mode
            demo_id = f"prodamus_demo_{order_id}"
            payment = Payment(
                user_id=user.id,
                yookassa_payment_id=demo_id,
                plan=plan,
                amount=amount,
                currency=curr.lower(),
                status=PaymentStatus.PENDING,
            )
            db.add(payment)
            await db.commit()
            return {
                "payment_url": f"{return_url}?payment_id={demo_id}",
                "payment_id": demo_id,
                "demo": True,
                "amount": amount,
                "currency": curr,
                "method": "card_international",
            }

        # Real Prodamus payment link
        params = {
            "order_id": order_id,
            "products[0][name]": config["name"],
            "products[0][price]": str(amount),
            "products[0][quantity]": "1",
            "products[0][sku]": plan.value,
            "currency": curr.lower(),
            "customer_email": user.email,
            "do": "link",
            "urlReturn": return_url,
            "urlSuccess": return_url,
            "urlNotification": f"{settings.frontend_url}/api/v1/payments/prodamus-webhook",
        }

        pay_url = f"{self.payform_url}?" + "&".join(f"{k}={v}" for k, v in params.items())

        payment = Payment(
            user_id=user.id,
            yookassa_payment_id=f"pd_{order_id}",
            plan=plan,
            amount=amount,
            currency=curr.lower(),
            status=PaymentStatus.PENDING,
        )
        db.add(payment)
        await db.commit()

        return {
            "payment_url": pay_url,
            "payment_id": order_id,
            "demo": False,
            "amount": amount,
            "currency": curr,
            "method": "card_international",
        }

    def verify_signature(self, data: dict, signature: str) -> bool:
        """Verify Prodamus webhook signature."""
        if not self.secret:
            return False
        # Prodamus signs with HMAC-SHA256
        sorted_data = "&".join(f"{k}={v}" for k, v in sorted(data.items()) if k != "signature")
        expected = hmac.new(self.secret.encode(), sorted_data.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def handle_webhook(self, db: AsyncSession, body: dict) -> dict:
        """Process Prodamus webhook notification."""
        order_id = body.get("order_id", "")
        status = body.get("payment_status", "")

        payment_key = f"pd_{order_id}"
        payment = (await db.execute(
            select(Payment).where(Payment.yookassa_payment_id == payment_key)
        )).scalar_one_or_none()

        if not payment:
            return {"error": f"Payment not found: {order_id}"}

        if status == "success" and payment.status == PaymentStatus.PENDING:
            payment.status = PaymentStatus.COMPLETED
            config = PLAN_CONFIG[payment.plan]
            user = await db.get(User, payment.user_id)
            if user:
                await grant_premium_days(db, user, config["days"])
                await notification_service.notify_premium(user.id, config["days"])
            await db.commit()
            logger.info(f"Prodamus payment completed: {payment.plan.value}, {payment.amount} {payment.currency}")
            return {"status": "ok"}

        return {"status": "ignored"}


prodamus_service = ProdamusService()
