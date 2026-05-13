"""Payments API — Stripe checkout, webhook, history."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.payment import Payment, PaymentPlan
from app.models.user import User
from app.services.stripe_service import stripe_service

router = APIRouter()


class CheckoutRequest(BaseModel):
    plan: PaymentPlan
    success_url: str = "http://localhost:3000/dashboard/premium/success"
    cancel_url: str = "http://localhost:3000/dashboard/premium"


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str
    demo: bool


class PaymentResponse(BaseModel):
    id: str
    plan: str
    amount: float
    currency: str
    status: str
    stripe_session_id: str | None
    created_at: str

    model_config = {"from_attributes": True}


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    data: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a Stripe Checkout session for Premium subscription."""
    result = await stripe_service.create_checkout_session(
        db, user, data.plan, data.success_url, data.cancel_url
    )
    return result


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Stripe webhook handler — processes payment events."""
    from app.config import settings as cfg
    if not cfg.stripe_webhook_secret:
        raise HTTPException(503, "Webhook not configured")
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    if not signature:
        raise HTTPException(400, "Missing stripe-signature header")
    result = await stripe_service.handle_webhook(db, payload, signature)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/complete-demo")
async def complete_demo(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Complete a demo payment (for testing without real Stripe)."""
    payment = await stripe_service.complete_demo_payment(db, session_id)
    if not payment:
        raise HTTPException(404, "Payment not found or already completed")
    return {"status": "completed", "plan": payment.plan.value, "days": 30 if payment.plan == PaymentPlan.MONTHLY else 365}


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
                "stripe_session_id": p.stripe_session_id,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in payments
        ],
    }
