"""Tests for public API — stats, sample signal, data status (no auth)."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_public_stats(client: AsyncClient):
    """No auth required."""
    resp = await client.get("/api/v1/public/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "signals" in data
    assert "providers" in data
    assert "users" in data
    assert "exchanges" in data
    # 9 was a hardcoded constant. The field now reports the markets the platform
    # actually fetches candles for (MOEX shares, MOEX FORTS, US/EU stocks, Binance,
    # forex), so it is asserted as a real count rather than pinned to the old value.
    assert data["exchanges"] == data["markets"]
    assert 1 <= data["markets"] <= 20


@pytest.mark.asyncio
async def test_public_sample_signal(client: AsyncClient):
    resp = await client.get("/api/v1/public/sample-signal")
    assert resp.status_code == 200
    data = resp.json()
    assert "ticker" in data
    assert "action" in data
    assert "entry_price" in data
    assert "ai_confidence" in data


@pytest.mark.asyncio
async def test_public_fear_greed(client: AsyncClient):
    """Fear & Greed index — may fail if network blocked."""
    resp = await client.get("/api/v1/public/fear-greed")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_public_crypto_top(client: AsyncClient):
    resp = await client.get("/api/v1/public/crypto-top?limit=5")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
