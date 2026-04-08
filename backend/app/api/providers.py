import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel

from app.api.deps import get_current_user
from app.database import get_db
from app.models.provider import Provider, ProviderSource
from app.models.user import User
from app.schemas.provider import ProviderCreate, ProviderList, ProviderResponse
from app.workers.signal_fetcher import telegram_worker


class TelegramSubscribe(BaseModel):
    channel_id: str
    channel_name: str | None = None

router = APIRouter()


@router.get("", response_model=ProviderList)
async def list_providers(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    total = (await db.execute(select(func.count()).select_from(Provider))).scalar()
    result = await db.execute(
        select(Provider)
        .order_by(Provider.ai_score.desc().nulls_last())
        .offset(skip)
        .limit(limit)
    )
    return ProviderList(items=result.scalars().all(), total=total)


@router.get("/{provider_id}", response_model=ProviderResponse)
async def get_provider(
    provider_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Provider).where(Provider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.post("", response_model=ProviderResponse, status_code=201)
async def create_provider(
    data: ProviderCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    provider = Provider(**data.model_dump())
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return provider


@router.post("/{provider_id}/subscribe", response_model=ProviderResponse)
async def subscribe_telegram_channel(
    provider_id: uuid.UUID,
    data: TelegramSubscribe,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Subscribe a provider to a Telegram channel for signal monitoring."""
    result = await db.execute(select(Provider).where(Provider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    if provider.source != ProviderSource.TELEGRAM:
        raise HTTPException(status_code=400, detail="Provider is not a Telegram source")

    provider.telegram_channel_id = data.channel_id
    if data.channel_name:
        provider.description = f"Telegram: {data.channel_name}"
    provider.is_active = True
    await db.commit()
    await db.refresh(provider)

    # Reload worker channels
    await telegram_worker.reload_channels()

    return provider


@router.delete("/{provider_id}/subscribe", response_model=ProviderResponse)
async def unsubscribe_telegram_channel(
    provider_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Unsubscribe a provider from its Telegram channel."""
    result = await db.execute(select(Provider).where(Provider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    provider.telegram_channel_id = None
    provider.is_active = False
    await db.commit()
    await db.refresh(provider)

    await telegram_worker.reload_channels()

    return provider


@router.get("/{provider_id}/status")
async def provider_status(
    provider_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get connection status for a provider."""
    result = await db.execute(select(Provider).where(Provider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    is_connected = False
    if provider.source == ProviderSource.TELEGRAM and provider.telegram_channel_id:
        is_connected = provider.telegram_channel_id in telegram_worker._monitored_channels

    return {
        "provider_id": str(provider.id),
        "name": provider.name,
        "source": provider.source.value,
        "is_active": provider.is_active,
        "is_connected": is_connected,
        "total_signals": provider.total_signals,
    }
