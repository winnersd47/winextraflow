"""Tests for provider endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_provider(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/providers", headers=auth_headers, json={
        "name": "Test Provider",
        "source": "manual",
        "description": "Test description",
    })
    assert resp.status_code == 201
    assert resp.json()["name"] == "Test Provider"


@pytest.mark.asyncio
async def test_list_providers(client: AsyncClient, auth_headers: dict):
    await client.post("/api/v1/providers", headers=auth_headers, json={
        "name": "Provider A", "source": "tradingview",
    })
    resp = await client.get("/api/v1/providers", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_leaderboard_empty(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/providers/leaderboard", headers=auth_headers)
    assert resp.status_code == 200
    # No providers with ai_score yet
    assert resp.json()["total"] == 0
