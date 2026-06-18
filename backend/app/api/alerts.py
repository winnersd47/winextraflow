"""Price Alerts API — CRUD for user-defined price alerts."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.alert import PriceAlert
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


class AlertCreate(BaseModel):
    ticker: str
    condition: str  # "above" or "below"
    target_price: float
    note: str | None = None


@router.get("")
async def list_alerts(
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List user's price alerts."""
    stmt = select(PriceAlert).where(PriceAlert.user_id == str(user.id))
    if active_only:
        stmt = stmt.where(PriceAlert.is_active == True)
    stmt = stmt.order_by(PriceAlert.created_at.desc())
    alerts = (await db.execute(stmt)).scalars().all()

    return {
        "total": len(alerts),
        "items": [
            {
                "id": a.id,
                "ticker": a.ticker,
                "condition": a.condition,
                "target_price": a.target_price,
                "note": a.note,
                "is_active": a.is_active,
                "is_triggered": a.is_triggered,
                "triggered_at": a.triggered_at.isoformat() if a.triggered_at else None,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in alerts
        ],
    }


@router.post("", status_code=201)
async def create_alert(
    data: AlertCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new price alert."""
    if data.condition not in ("above", "below"):
        raise HTTPException(400, "Condition must be 'above' or 'below'")

    # Limit alerts per user
    count = (await db.execute(
        select(func.count(PriceAlert.id)).where(
            PriceAlert.user_id == str(user.id),
            PriceAlert.is_active == True,
        )
    )).scalar() or 0
    if count >= 20:
        raise HTTPException(400, "Maximum 20 active alerts")

    alert = PriceAlert(
        user_id=str(user.id),
        ticker=data.ticker.upper(),
        condition=data.condition,
        target_price=data.target_price,
        note=data.note,
    )
    db.add(alert)
    await db.commit()
    return {"id": alert.id, "status": "created"}


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete an alert."""
    alert = (await db.execute(
        select(PriceAlert).where(PriceAlert.id == alert_id, PriceAlert.user_id == str(user.id))
    )).scalar_one_or_none()
    if not alert:
        raise HTTPException(404, "Alert not found")
    await db.delete(alert)
    await db.commit()
    return {"status": "deleted"}


@router.patch("/{alert_id}/toggle")
async def toggle_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Toggle alert active/inactive."""
    alert = (await db.execute(
        select(PriceAlert).where(PriceAlert.id == alert_id, PriceAlert.user_id == str(user.id))
    )).scalar_one_or_none()
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.is_active = not alert.is_active
    await db.commit()
    return {"id": alert.id, "is_active": alert.is_active}
