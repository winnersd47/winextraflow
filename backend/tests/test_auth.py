"""Tests for auth endpoints: register, login, me."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register(client: AsyncClient, seed_referrer: str):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "new@test.com",
        "username": "newuser",
        "password": "pass123",
        "referral_code": seed_referrer,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "new@test.com"
    assert data["username"] == "newuser"
    assert data["referral_code"] is not None
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_without_referral_public(client: AsyncClient):
    """Public mode (default): registration without a referral code succeeds."""
    resp = await client.post("/api/v1/auth/register", json={
        "email": "noreferral@test.com",
        "username": "noreferral",
        "password": "pass123",
    })
    assert resp.status_code == 201
    assert resp.json()["referral_code"] is not None  # gets own code


@pytest.mark.asyncio
async def test_register_invalid_referral_public(client: AsyncClient):
    """Public mode: an unknown referral code is ignored (registers without referrer)."""
    resp = await client.post("/api/v1/auth/register", json={
        "email": "badref@test.com",
        "username": "badref",
        "password": "pass123",
        "referral_code": "INVALID_CODE_123",
    })
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_register_invite_only_requires_code(client: AsyncClient, monkeypatch):
    """Invite-only mode: registration without a valid referral code is rejected."""
    from app.config import settings
    monkeypatch.setattr(settings, "registration_invite_only", True)
    resp = await client.post("/api/v1/auth/register", json={
        "email": "inviteonly@test.com",
        "username": "inviteonly",
        "password": "pass123",
        "referral_code": "",
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, seed_referrer: str):
    await client.post("/api/v1/auth/register", json={
        "email": "dup@test.com", "username": "user1", "password": "pass123",
        "referral_code": seed_referrer,
    })
    resp = await client.post("/api/v1/auth/register", json={
        "email": "dup@test.com", "username": "user2", "password": "pass123",
        "referral_code": seed_referrer,
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_login(client: AsyncClient, registered_user: dict):
    resp = await client.post("/api/v1/auth/login", json={
        "email": registered_user["email"],
        "password": "testpass123",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_bad_password(client: AsyncClient, registered_user: dict):
    resp = await client.post("/api/v1/auth/login", json={
        "email": registered_user["email"],
        "password": "wrongpass",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me(client: AsyncClient, auth_headers: dict, registered_user: dict):
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == registered_user["email"]


@pytest.mark.asyncio
async def test_me_unauthorized(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 403
