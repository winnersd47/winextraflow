"""Tests for referral system."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_with_referral(client: AsyncClient):
    # Register referrer
    resp1 = await client.post("/api/v1/auth/register", json={
        "email": "referrer@test.com", "username": "referrer", "password": "pass123",
    })
    referral_code = resp1.json()["referral_code"]

    # Register with referral code
    resp2 = await client.post("/api/v1/auth/register", json={
        "email": "referred@test.com", "username": "referred", "password": "pass123",
        "referral_code": referral_code,
    })
    assert resp2.status_code == 201


@pytest.mark.asyncio
async def test_referral_stats(client: AsyncClient):
    # Register referrer
    resp1 = await client.post("/api/v1/auth/register", json={
        "email": "ref_stats@test.com", "username": "ref_stats", "password": "pass123",
    })
    code = resp1.json()["referral_code"]

    # Login referrer
    login = await client.post("/api/v1/auth/login", json={
        "email": "ref_stats@test.com", "password": "pass123",
    })
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Register referred user
    await client.post("/api/v1/auth/register", json={
        "email": "ref_child@test.com", "username": "ref_child", "password": "pass123",
        "referral_code": code,
    })

    # Check stats
    resp = await client.get("/api/v1/referrals/stats", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["level1_count"] == 1
    assert data["total_referrals"] == 1


@pytest.mark.asyncio
async def test_referral_tree(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/referrals/tree", headers=auth_headers)
    assert resp.status_code == 200
    assert "referrals" in resp.json()
