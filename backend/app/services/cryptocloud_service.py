"""CryptoCloud payment service — accept USDT/BTC/ETH from international clients.

API docs: https://docs.cryptocloud.plus/
Commission: 0.4-1%
Supports: USDT, BTC, ETH, LTC, DOGE, MATIC, SOL, and 20+ more
Auto-conversion to RUB available.
"""

import logging
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
    PaymentPlan.MONTHLY: {"amount_usd": 33.0, "days": 30, "name": "Premium Monthly"},
    PaymentPlan.YEARLY: {"amount_usd": 264.0, "days": 365, "name": "Premium Yearly"},
}

PRO_CONFIG = {
    "monthly": {"amount_usd": 16.0, "days": 30, "name": "Pro Monthly"},
    "yearly": {"amount_usd": 128.0, "days": 365, "name": "Pro Yearly"},
}

CRYPTOCLOUD_API = "https://api.cryptocloud.plus/v2"


class CryptoCloudService:
    """CryptoCloud crypto payment integration."""

    def __init__(self):
        self.api_key = settings.cryptocloud_api_key
        self.shop_id = settings.cryptocloud_shop_id
        self._configured = bool(self.api_key and self.shop_id)
        if self._configured:
            logger.info("CryptoCloud configured")

    async def create_payment(
        self,
        db: AsyncSession,
        user: User,
        plan: PaymentPlan,
        return_url: str,
    ) -> dict:
        """Create a CryptoCloud invoice."""
        config = PLAN_CONFIG[plan]
        order_id = f"wef_{user.id}_{plan.value}_{uuid_lib.uuid4().hex[:8]}"

        if not self._configured:
            # Demo mode
            demo_id = f"crypto_demo_{order_id}"
            payment = Payment(
                user_id=user.id,
                yookassa_payment_id=demo_id,
                plan=plan,
                amount=config["amount_usd"],
                currency="usd",
                status=PaymentStatus.PENDING,
            )
            db.add(payment)
            await db.commit()
            return {
                "payment_url": f"{return_url}?payment_id={demo_id}",
                "payment_id": demo_id,
                "demo": True,
                "amount": config["amount_usd"],
                "currency": "USD",
                "method": "crypto",
            }

        # Real CryptoCloud invoice
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{CRYPTOCLOUD_API}/invoice/create",
                headers={
                    "Authorization": f"Token {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "amount": config["amount_usd"],
                    "shop_id": self.shop_id,
                    "currency": "USD",
                    "order_id": order_id,
                    "email": user.email,
                },
            )
            data = resp.json()

        if data.get("status") != "success":
            logger.error(f"CryptoCloud error: {data}")
            return {"error": data.get("message", "Payment creation failed")}

        invoice = data.get("result", {})
        invoice_id = invoice.get("uuid", order_id)
        pay_url = invoice.get("link", "")

        payment = Payment(
            user_id=user.id,
            yookassa_payment_id=f"cc_{invoice_id}",
            plan=plan,
            amount=config["amount_usd"],
            currency="usd",
            status=PaymentStatus.PENDING,
        )
        db.add(payment)
        await db.commit()

        return {
            "payment_url": pay_url,
            "payment_id": invoice_id,
            "demo": False,
            "amount": config["amount_usd"],
            "currency": "USD",
            "method": "crypto",
        }

    async def handle_webhook(self, db: AsyncSession, body: dict) -> dict:
        """Process CryptoCloud webhook (postback)."""
        status = body.get("status")
        order_id = body.get("order_id", "")
        invoice_id = body.get("invoice_id", "")

        payment_key = f"cc_{invoice_id}" if invoice_id else None
        if not payment_key:
            return {"error": "No invoice ID"}

        if status == "success":
            payment = (await db.execute(
                select(Payment).where(Payment.yookassa_payment_id == payment_key)
            )).scalar_one_or_none()

            if payment and payment.status == PaymentStatus.PENDING:
                payment.status = PaymentStatus.COMPLETED
                config = PLAN_CONFIG[payment.plan]
                user = await db.get(User, payment.user_id)
                if user:
                    await grant_premium_days(db, user, config["days"])
                    await notification_service.notify_premium(user.id, config["days"])
                await db.commit()
                logger.info(f"CryptoCloud payment completed: {payment.plan.value}")

            return {"status": "ok"}

        return {"status": "ignored", "event": status}


cryptocloud_service = CryptoCloudService()
