"""Tests for trading journal — CRUD, auto-calc profit, stats."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_journal_entry(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/journal", json={
        "ticker": "SBER", "action": "buy", "entry_price": 312.5,
        "exit_price": 328.0, "quantity": 10, "note": "Test trade", "emotion": "confident",
    }, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["status"] == "created"


@pytest.mark.asyncio
async def test_auto_calc_profit(client: AsyncClient, auth_headers: dict):
    await client.post("/api/v1/journal", json={
        "ticker": "GAZP", "action": "buy", "entry_price": 100.0, "exit_price": 110.0, "quantity": 5,
    }, headers=auth_headers)
    stats = await client.get("/api/v1/journal/stats", headers=auth_headers)
    assert stats.status_code == 200
    data = stats.json()
    assert data["total_trades"] >= 1
    assert data["avg_profit_pct"] > 0  # 10% profit


@pytest.mark.asyncio
async def test_list_journal(client: AsyncClient, auth_headers: dict):
    await client.post("/api/v1/journal", json={
        "ticker": "LKOH", "action": "sell", "entry_price": 500.0,
    }, headers=auth_headers)
    resp = await client.get("/api/v1/journal", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_delete_journal_entry(client: AsyncClient, auth_headers: dict):
    r = await client.post("/api/v1/journal", json={
        "ticker": "YNDX", "action": "buy", "entry_price": 200.0,
    }, headers=auth_headers)
    entry_id = r.json()["id"]
    r2 = await client.delete(f"/api/v1/journal/{entry_id}", headers=auth_headers)
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_journal_stats_empty(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/journal/stats", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total_trades"] == 0
