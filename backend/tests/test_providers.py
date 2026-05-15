"""Tests for provider endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_provider(client: AsyncClient, premium_auth_headers: dict):
    """Create provider requires analyst/admin role."""
    resp = await client.post("/api/v1/providers", headers=premium_auth_headers, json={
        "name": "Test Provider",
        "source": "manual",
        "description": "Test description",
    })
    assert resp.status_code == 201
    assert resp.json()["name"] == "Test Provider"


@pytest.mark.asyncio
async def test_create_provider_forbidden_for_user(client: AsyncClient, auth_headers: dict):
    """Regular users cannot create providers."""
    resp = await client.post("/api/v1/providers", headers=auth_headers, json={
        "name": "Forbidden Provider", "source": "manual",
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_providers(client: AsyncClient, premium_auth_headers: dict, auth_headers: dict):
    await client.post("/api/v1/providers", headers=premium_auth_headers, json={
        "name": "Provider A", "source": "tradingview",
    })
    resp = await client.get("/api/v1/providers", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_leaderboard_empty(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/providers/leaderboard", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
