"""Tests for YooKassa payment system — demo mode checkout, plans, history."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_plans(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/payments/plans", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "plans" in data
    assert "methods" in data
    assert "ru" in data["methods"]
    assert "crypto" in data["methods"]
    assert "international" in data["methods"]


@pytest.mark.asyncio
async def test_demo_checkout(client: AsyncClient, auth_headers: dict, paid_subscriptions_on):
    resp = await client.post("/api/v1/payments/checkout", json={
        "plan": "monthly", "return_url": "http://test.com/store",
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["demo"] is True
    assert data["payment_id"].startswith("demo_")
    assert data["currency"] == "RUB"
    assert data["amount"] > 0


@pytest.mark.asyncio
async def test_demo_complete(client: AsyncClient, auth_headers: dict, paid_subscriptions_on):
    # Create demo payment
    r1 = await client.post("/api/v1/payments/checkout", json={
        "plan": "monthly", "return_url": "http://test.com",
    }, headers=auth_headers)
    payment_id = r1.json()["payment_id"]
    # Complete it
    r2 = await client.post(f"/api/v1/payments/complete-demo?payment_id={payment_id}", headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_complete_nonexistent_fails(client: AsyncClient, auth_headers: dict, paid_subscriptions_on):
    resp = await client.post("/api/v1/payments/complete-demo?payment_id=fake_id", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_payment_history(client: AsyncClient, auth_headers: dict, paid_subscriptions_on):
    # Create a payment first
    await client.post("/api/v1/payments/checkout", json={"plan": "monthly", "return_url": "http://test.com"}, headers=auth_headers)
    resp = await client.get("/api/v1/payments/history", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_crypto_checkout_demo(client: AsyncClient, auth_headers: dict, paid_subscriptions_on):
    resp = await client.post("/api/v1/payments/checkout/crypto", json={
        "plan": "monthly", "return_url": "http://test.com",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["demo"] is True
    assert resp.json()["currency"] == "USD"
