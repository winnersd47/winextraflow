"""Tests for execution layer: accounts and orders."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_demo_account(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/execution/accounts", headers=auth_headers, json={
        "exchange": "demo",
        "label": "My Demo",
        "api_key": "demo",
        "api_secret": "demo",
        "auto_execute": False,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["exchange"] == "demo"
    assert data["label"] == "My Demo"


@pytest.mark.asyncio
async def test_list_accounts(client: AsyncClient, auth_headers: dict):
    await client.post("/api/v1/execution/accounts", headers=auth_headers, json={
        "exchange": "demo", "label": "Test", "api_key": "d", "api_secret": "d",
    })
    resp = await client.get("/api/v1/execution/accounts", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_execute_signal_on_demo(client: AsyncClient, premium_auth_headers: dict):
    # Create demo account (premium user)
    acc_resp = await client.post("/api/v1/execution/accounts", headers=premium_auth_headers, json={
        "exchange": "demo", "label": "Exec Test", "api_key": "demo", "api_secret": "demo",
    })
    account_id = acc_resp.json()["id"]

    # Create signal
    sig_resp = await client.post("/api/v1/signals/webhook/tradingview", json={
        "ticker": "BTCUSDT", "action": "buy", "price": 65000.0,
    })
    signal_id = sig_resp.json()["id"]

    # Execute (requires premium)
    resp = await client.post(f"/api/v1/execution/execute/{signal_id}", headers=premium_auth_headers, json={
        "exchange_account_id": account_id,
        "order_type": "market",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("filled", "failed")
    assert data["symbol"] == "BTCUSDT"


@pytest.mark.asyncio
async def test_list_orders(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/execution/orders", headers=auth_headers)
    assert resp.status_code == 200
    assert "items" in resp.json()
