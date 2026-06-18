"""Digest API — generate and send weekly digests."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User, UserRole
from app.services.email_digest import email_digest_service

router = APIRouter()


@router.get("/preview")
async def preview_digest(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Preview weekly digest (any user)."""
    data = await email_digest_service.generate_digest(db)
    text = email_digest_service.format_digest_text(data)
    return {"data": data, "text": text}


@router.post("/send-telegram")
async def send_digest_telegram(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Send digest to Telegram channels (admin only)."""
    if user.role != UserRole.ADMIN:
        from fastapi import HTTPException
        raise HTTPException(403, "Admin only")

    data = await email_digest_service.generate_digest(db)
    text = email_digest_service.format_digest_text(data)

    # Send to Telegram
    from app.services.telegram_bot import telegram_bot
    sent = False
    if telegram_bot.enabled:
        try:
            await telegram_bot.send_raw_message(text)
            sent = True
        except Exception:
            pass

    return {"sent": sent, "text": text}
