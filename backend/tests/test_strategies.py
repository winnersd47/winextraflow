"""Tests for strategy marketplace."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import Provider, ProviderSource


@pytest.mark.asyncio
async def test_browse_strategies_empty(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/strategies", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_publish_and_browse(client: AsyncClient, auth_headers: dict, db: AsyncSession):
    # Create provider
    provider = Provider(name="Strat Provider", source=ProviderSource.MANUAL)
    db.add(provider)
    await db.commit()
    await db.refresh(provider)

    # Publish strategy
    resp = await client.post("/api/v1/strategies", headers=auth_headers, json={
        "provider_id": str(provider.id),
        "name": "Alpha Strategy",
        "description": "High frequency BTC signals",
        "tags": "crypto,btc,scalping",
        "price_type": "free",
    })
    assert resp.status_code == 201
    strategy_id = resp.json()["id"]

    # Browse
    resp = await client.get("/api/v1/strategies", headers=auth_headers)
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["name"] == "Alpha Strategy"


@pytest.mark.asyncio
async def test_subscribe_unsubscribe(client: AsyncClient, auth_headers: dict, db: AsyncSession):
    provider = Provider(name="Sub Provider", source=ProviderSource.MANUAL)
    db.add(provider)
    await db.commit()
    await db.refresh(provider)

    # Publish
    pub_resp = await client.post("/api/v1/strategies", headers=auth_headers, json={
        "provider_id": str(provider.id), "name": "Sub Test",
    })
    strategy_id = pub_resp.json()["id"]

    # Subscribe
    resp = await client.post(f"/api/v1/strategies/{strategy_id}/subscribe", headers=auth_headers)
    assert resp.status_code == 200

    # Unsubscribe
    resp = await client.delete(f"/api/v1/strategies/{strategy_id}/subscribe", headers=auth_headers)
    assert resp.status_code == 200
