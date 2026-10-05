"""Payments API — YooKassa checkout, webhook, history.

Supports:
- Bank cards (Visa, MasterCard, МИР)
- СБП (0.7% commission)
- ЮMoney, SberPay
- Demo mode (no real payments) when YOOKASSA_SHOP_ID not set
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models.payment import Payment, PaymentPlan
from app.models.user import User
from app.services.yookassa_service import yookassa_service, PLAN_CONFIG
from app.services.cryptocloud_service import cryptocloud_service
from app.services.prodamus_service import prodamus_service

router = APIRouter()


def require_paid_subscriptions_enabled() -> None:
    """Block every checkout path while paid subscriptions are switched off.

    Owner's decision (2026-08-07): no money is taken until the platform has a
    measured record of profitable signals. As of that date the honest record was
    7 closed trades, 0 profitable, and those came from a pipeline that was
    fabricating entry and stop levels (see services/signal_levels.py).

    To re-enable, set PAID_SUBSCRIPTIONS_ENABLED=true — but only once
    `scripts/wef_validation.py` reports a real sample with positive expectancy.
    The flag is deliberately one switch in one place so it cannot be half-on.
    """
    if not settings.paid_subscriptions_enabled:
        raise HTTPException(
            status_code=503,
            detail="Платные подписки пока отключены. Доступ к сигналам открыт "
                   "бесплатно, пока не наберётся подтверждённая статистика доходности.",
        )


class CheckoutRequest(BaseModel):
    plan: PaymentPlan
    return_url: str = "http://localhost:3000/dashboard/store"


class CheckoutResponse(BaseModel):
    payment_url: str
    payment_id: str
    demo: bool
    amount: float
    currency: str


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    data: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a YooKassa payment for Premium subscription."""
    require_paid_subscriptions_enabled()
    result = await yookassa_service.create_payment(
        db, user, data.plan, data.return_url,
    )
    return result


@router.post("/webhook")
async def yookassa_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """YooKassa webhook handler — processes payment notifications.

    YooKassa sends POST with JSON body containing event type and payment object.
    Docs: https://yookassa.ru/developers/using-api/webhooks
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")

    result = await yookassa_service.handle_webhook(db, body)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/complete-demo")
async def complete_demo(
    payment_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Complete a demo payment (for testing without real YooKassa)."""
    require_paid_subscriptions_enabled()
    payment = await yookassa_service.complete_demo_payment(db, payment_id)
    if not payment:
        raise HTTPException(404, "Payment not found or already completed")
    config = PLAN_CONFIG[payment.plan]
    return {
        "status": "completed",
        "plan": payment.plan.value,
        "days": config["days"],
        "amount": payment.amount,
        "currency": "RUB",
    }


@router.post("/checkout/crypto")
async def create_crypto_checkout(
    data: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a CryptoCloud payment (USDT/BTC/ETH) for international clients."""
    require_paid_subscriptions_enabled()
    result = await cryptocloud_service.create_payment(db, user, data.plan, data.return_url)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


class ProdamusCheckoutRequest(BaseModel):
    plan: PaymentPlan
    currency: str = "usd"  # usd or eur
    return_url: str = "http://localhost:3000/dashboard/store"


@router.post("/checkout/international")
async def create_international_checkout(
    data: ProdamusCheckoutRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a Prodamus payment (Visa/MC in USD/EUR) for international clients."""
    require_paid_subscriptions_enabled()
    result = await prodamus_service.create_payment(db, user, data.plan, data.currency, data.return_url)
    return result


@router.post("/webhook/crypto")
async def cryptocloud_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """CryptoCloud webhook handler."""
    body = await request.json()
    result = await cryptocloud_service.handle_webhook(db, body)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/webhook/prodamus")
async def prodamus_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Prodamus webhook handler."""
    body = await request.json()
    result = await prodamus_service.handle_webhook(db, body)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/plans")
async def get_plans(user: User = Depends(get_current_user)):
    """Available subscription plans with prices in all currencies.

    Stays readable while checkout is off so the pricing page can show what a
    subscription will cost — it just cannot be bought yet. `enabled` tells the
    frontend which state to render.
    """
    from app.services.cryptocloud_service import PLAN_CONFIG as CRYPTO_PLANS
    from app.services.prodamus_service import PLAN_CONFIG as INTL_PLANS

    return {
        "enabled": settings.paid_subscriptions_enabled,
        "disabled_reason_ru": None if settings.paid_subscriptions_enabled else (
            "Платные подписки откроются после подтверждённой статистики доходности. "
            "Пока все сигналы доступны бесплатно."
        ),
        "plans": {
            "rub": [
                {
                    "plan": plan.value,
                    "amount": config["amount"],
                    "currency": "RUB",
                    "days": config["days"],
                    "name_ru": config["name_ru"],
                    "name_en": config["name_en"],
                }
                for plan, config in PLAN_CONFIG.items()
            ],
            "usd": [
                {
                    "plan": plan.value,
                    "amount": config["amount_usd"],
                    "currency": "USD",
                    "days": config["days"],
                    "name": config["name"],
                }
                for plan, config in CRYPTO_PLANS.items()
            ],
        },
        "methods": {
            "ru": {"name": "ЮKassa", "methods": ["card", "sbp", "yoomoney", "sberpay"], "currency": "RUB"},
            "crypto": {"name": "CryptoCloud", "methods": ["usdt", "btc", "eth", "sol"], "currency": "USD", "commission": "0.4-1%"},
            "international": {"name": "Prodamus", "methods": ["visa", "mastercard", "maestro"], "currency": "USD/EUR", "commission": "3.5-5%"},
        },
    }


@router.get("/history")
async def payment_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get payment history for the current user."""
    total = (await db.execute(
        select(func.count()).select_from(Payment).where(Payment.user_id == user.id)
    )).scalar() or 0
    result = await db.execute(
        select(Payment).where(Payment.user_id == user.id)
        .order_by(Payment.created_at.desc()).offset(skip).limit(limit)
    )
    payments = result.scalars().all()
    return {
        "total": total,
        "items": [
            {
                "id": str(p.id),
                "plan": p.plan.value,
                "amount": p.amount,
                "currency": p.currency,
                "status": p.status.value,
                "payment_id": p.yookassa_payment_id,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in payments
        ],
    }
