from pydantic import BaseModel


class PremiumStatus(BaseModel):
    is_premium: bool
    days_left: int
    role: str
    expires_at: str | None


class ActivatePremium(BaseModel):
    promo_code: str | None = None
    days: int | None = None  # Admin-only: grant days directly
