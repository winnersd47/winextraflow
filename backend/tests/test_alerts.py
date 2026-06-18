"""Tests for price alerts — CRUD, toggle, limit."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_alert(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/alerts", json={
        "ticker": "SBER", "condition": "above", "target_price": 330.0, "note": "Breakout level",
    }, headers=auth_headers)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_invalid_condition_rejected(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/alerts", json={
        "ticker": "SBER", "condition": "equals", "target_price": 300.0,
    }, headers=auth_headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_alerts(client: AsyncClient, auth_headers: dict):
    await client.post("/api/v1/alerts", json={"ticker": "GAZP", "condition": "below", "target_price": 200.0}, headers=auth_headers)
    resp = await client.get("/api/v1/alerts", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_toggle_alert(client: AsyncClient, auth_headers: dict):
    r = await client.post("/api/v1/alerts", json={"ticker": "LKOH", "condition": "above", "target_price": 600.0}, headers=auth_headers)
    alert_id = r.json()["id"]
    # Toggle off
    r2 = await client.patch(f"/api/v1/alerts/{alert_id}/toggle", headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["is_active"] is False
    # Toggle on
    r3 = await client.patch(f"/api/v1/alerts/{alert_id}/toggle", headers=auth_headers)
    assert r3.json()["is_active"] is True


@pytest.mark.asyncio
async def test_delete_alert(client: AsyncClient, auth_headers: dict):
    r = await client.post("/api/v1/alerts", json={"ticker": "NVDA", "condition": "above", "target_price": 1000.0}, headers=auth_headers)
    alert_id = r.json()["id"]
    r2 = await client.delete(f"/api/v1/alerts/{alert_id}", headers=auth_headers)
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_max_alerts_limit(client: AsyncClient, auth_headers: dict):
    """Max 20 active alerts per user."""
    for i in range(20):
        r = await client.post("/api/v1/alerts", json={"ticker": f"T{i}", "condition": "above", "target_price": 100.0}, headers=auth_headers)
        assert r.status_code == 201
    # 21st should fail
    r21 = await client.post("/api/v1/alerts", json={"ticker": "EXTRA", "condition": "above", "target_price": 100.0}, headers=auth_headers)
    assert r21.status_code == 400
