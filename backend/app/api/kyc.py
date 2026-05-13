"""KYC verification API — photo upload, status check, admin review."""

import os
import uuid
import shutil

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.kyc import KYCVerification, KYCStatus
from app.models.user import User, UserRole
from app.services.notifications import notification_service

router = APIRouter()

UPLOAD_DIR = "uploads/kyc"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(403, "Admin access required")
    return user


# ─── User endpoints ───────────────────────────────────────

@router.get("/status")
async def kyc_status(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get KYC verification status for current user."""
    kyc = (await db.execute(
        select(KYCVerification).where(KYCVerification.user_id == user.id)
    )).scalar_one_or_none()

    return {
        "kyc_verified": user.kyc_verified,
        "status": kyc.status.value if kyc else "none",
        "admin_comment": kyc.admin_comment if kyc else None,
        "submitted_at": kyc.created_at.isoformat() if kyc else None,
    }


@router.post("/upload")
async def upload_kyc_photo(
    photo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload selfie with passport for KYC verification.

    Accepted formats: JPG, PNG. Max size: 10MB.
    """
    # Validate file type
    if photo.content_type not in ("image/jpeg", "image/png", "image/jpg"):
        raise HTTPException(400, "Only JPG/PNG images are accepted")

    # Validate file size (10MB max)
    contents = await photo.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(400, "File too large. Maximum 10MB.")

    # Check if already pending/approved
    existing = (await db.execute(
        select(KYCVerification).where(KYCVerification.user_id == user.id)
    )).scalar_one_or_none()

    if existing and existing.status == KYCStatus.APPROVED:
        raise HTTPException(400, "Already verified")
    if existing and existing.status == KYCStatus.PENDING:
        raise HTTPException(400, "Verification already pending. Please wait for admin review.")

    # Save file — whitelist extensions to prevent malicious uploads
    ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}
    ext = (photo.filename.rsplit(".", 1)[-1].lower() if photo.filename and "." in photo.filename else "jpg")
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File extension '.{ext}' not allowed. Use JPG or PNG.")
    filename = f"{user.id}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(os.path.abspath(UPLOAD_DIR), filename)
    with open(filepath, "wb") as f:
        f.write(contents)

    # Create or update KYC record
    if existing:
        existing.photo_path = filepath
        existing.status = KYCStatus.PENDING
        existing.admin_comment = None
    else:
        kyc = KYCVerification(
            user_id=user.id,
            photo_path=filepath,
            status=KYCStatus.PENDING,
        )
        db.add(kyc)

    await db.commit()
    await notification_service.create(
        db, user_id=user.id, type="system",
        title="KYC submitted", message="Your verification photo has been submitted for review.",
    )

    return {"status": "pending", "message": "Photo uploaded. Admin will review within 24 hours."}


# ─── Admin endpoints ──────────────────────────────────────

@router.get("/admin/pending")
async def list_pending_kyc(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """List all pending KYC verifications (admin only)."""
    result = await db.execute(
        select(KYCVerification, User)
        .join(User, KYCVerification.user_id == User.id)
        .where(KYCVerification.status == KYCStatus.PENDING)
        .order_by(KYCVerification.created_at)
    )
    rows = result.all()
    return {
        "total": len(rows),
        "items": [
            {
                "kyc_id": str(kyc.id),
                "user_id": str(user.id),
                "username": user.username,
                "email": user.email,
                "photo_path": kyc.photo_path,
                "submitted_at": kyc.created_at.isoformat() if kyc.created_at else None,
            }
            for kyc, user in rows
        ],
    }


@router.patch("/admin/{kyc_id}/approve")
async def approve_kyc(
    kyc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Approve KYC verification (admin only)."""
    kyc = await db.get(KYCVerification, kyc_id)
    if not kyc:
        raise HTTPException(404, "KYC record not found")

    kyc.status = KYCStatus.APPROVED
    kyc.reviewed_by = admin.id

    # Mark user as verified
    user = await db.get(User, kyc.user_id)
    if user:
        user.kyc_verified = True

    await db.commit()

    if user:
        await notification_service.create(
            db, user_id=user.id, type="system",
            title="KYC Approved!", message="Your identity has been verified. Premium features are now available.",
        )

    return {"status": "approved", "user_id": str(kyc.user_id)}


@router.patch("/admin/{kyc_id}/reject")
async def reject_kyc(
    kyc_id: uuid.UUID,
    reason: str = "Photo does not meet requirements. Please resubmit.",
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Reject KYC verification with reason (admin only)."""
    kyc = await db.get(KYCVerification, kyc_id)
    if not kyc:
        raise HTTPException(404, "KYC record not found")

    kyc.status = KYCStatus.REJECTED
    kyc.admin_comment = reason
    kyc.reviewed_by = admin.id

    await db.commit()

    user = await db.get(User, kyc.user_id)
    if user:
        await notification_service.create(
            db, user_id=user.id, type="system",
            title="KYC Rejected", message=f"Reason: {reason}. Please upload a new photo.",
        )

    return {"status": "rejected", "reason": reason}
