"""Tests for social features — comments, likes, trader profile."""

import pytest
from httpx import AsyncClient


async def _create_signal_via_api(client: AsyncClient, headers: dict) -> str:
    """Create signal via webhook API and return its ID."""
    resp = await client.post("/api/v1/signals/webhook/tradingview", json={
        "ticker": "BTCUSDT", "action": "buy", "price": 60000.0,
        "tp": 65000.0, "sl": 58000.0, "source": "test",
    })
    if resp.status_code == 201:
        return resp.json()["id"]
    # Fallback: get first signal from list
    r2 = await client.get("/api/v1/signals?limit=1", headers=headers)
    items = r2.json().get("items", [])
    if items:
        return items[0]["id"]
    return ""


@pytest.mark.asyncio
async def test_trader_profile(client: AsyncClient, auth_headers: dict, registered_user: dict):
    username = registered_user["username"]
    resp = await client.get(f"/api/v1/social/profile/{username}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == username


@pytest.mark.asyncio
async def test_trader_profile_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/social/profile/nonexistent_user_xyz", headers=auth_headers)
    assert resp.status_code == 404
