"""Tests for signal endpoints: list, webhook, close, rating."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_signals_empty(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/signals", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_tradingview_webhook(client: AsyncClient):
    resp = await client.post("/api/v1/signals/webhook/tradingview", json={
        "ticker": "BTCUSDT",
        "action": "buy",
        "price": 65000.0,
        "take_profit": 70000.0,
        "stop_loss": 62000.0,
        "timeframe": "4h",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["ticker"] == "BTCUSDT"
    assert data["action"] == "buy"
    assert data["entry_price"] == 65000.0
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_list_signals_after_webhook(client: AsyncClient, auth_headers: dict):
    # Create signal via webhook — with TP/SL so it passes the quality gate (WEF >= 50%)
    await client.post("/api/v1/signals/webhook/tradingview", json={
        "ticker": "ETHUSDT", "action": "sell", "price": 3500.0,
        "take_profit": 3200.0, "stop_loss": 3650.0,
    })
    resp = await client.get("/api/v1/signals", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_get_signal(client: AsyncClient, auth_headers: dict):
    # Create
    create_resp = await client.post("/api/v1/signals/webhook/tradingview", json={
        "ticker": "SOLUSDT", "action": "buy", "price": 145.0,
    })
    signal_id = create_resp.json()["id"]
    # Get
    resp = await client.get(f"/api/v1/signals/{signal_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["ticker"] == "SOLUSDT"


@pytest.mark.asyncio
async def test_get_signal_rating(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/v1/signals/webhook/tradingview", json={
        "ticker": "BTCUSDT", "action": "buy", "price": 65000.0,
        "take_profit": 70000.0, "stop_loss": 62000.0,
    })
    signal_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/signals/{signal_id}/rating", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "final_confidence" in data
    assert "factors" in data


@pytest.mark.asyncio
async def test_close_signal(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/v1/signals/webhook/tradingview", json={
        "ticker": "BTCUSDT", "action": "buy", "price": 65000.0,
    })
    signal_id = create_resp.json()["id"]
    resp = await client.patch(f"/api/v1/signals/{signal_id}/close", headers=auth_headers, json={
        "close_price": 67000.0,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "closed_tp"
    assert data["profit_pct"] is not None
    assert data["profit_pct"] > 0
