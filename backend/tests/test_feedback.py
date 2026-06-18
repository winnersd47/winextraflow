"""Tests for feedback system — reviews, feature requests, bug reports, NPS, upvotes."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_submit_review(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/feedback", json={
        "type": "review", "text": "Great platform!", "rating": 5, "category": "signals",
    }, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["status"] == "submitted"


@pytest.mark.asyncio
async def test_submit_feature_request(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/feedback", json={
        "type": "feature_request", "title": "Dark charts", "text": "Please add darker candlestick charts", "category": "ui",
    }, headers=auth_headers)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_submit_bug_report(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/feedback", json={
        "type": "bug_report", "text": "Login fails on mobile Safari",
    }, headers=auth_headers)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_submit_nps(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/feedback", json={
        "type": "nps", "text": "Would recommend", "nps_score": 9,
    }, headers=auth_headers)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_invalid_type_rejected(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/feedback", json={
        "type": "invalid_type", "text": "test",
    }, headers=auth_headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_short_text_rejected(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/feedback", json={
        "type": "review", "text": "ab",
    }, headers=auth_headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_feedback(client: AsyncClient, auth_headers: dict):
    # Submit one first
    await client.post("/api/v1/feedback", json={"type": "review", "text": "Nice!", "rating": 4}, headers=auth_headers)
    resp = await client.get("/api/v1/feedback", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_upvote_toggle(client: AsyncClient, auth_headers: dict):
    # Submit
    r = await client.post("/api/v1/feedback", json={"type": "feature_request", "text": "Add crypto alerts"}, headers=auth_headers)
    fb_id = r.json()["id"]
    # Upvote
    r2 = await client.post(f"/api/v1/feedback/{fb_id}/upvote", headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["upvotes"] == 1
    # Toggle off
    r3 = await client.post(f"/api/v1/feedback/{fb_id}/upvote", headers=auth_headers)
    assert r3.json()["upvotes"] == 0


@pytest.mark.asyncio
async def test_delete_own_feedback(client: AsyncClient, auth_headers: dict):
    r = await client.post("/api/v1/feedback", json={"type": "suggestion", "text": "Just an idea"}, headers=auth_headers)
    fb_id = r.json()["id"]
    r2 = await client.delete(f"/api/v1/feedback/{fb_id}", headers=auth_headers)
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_feedback_stats(client: AsyncClient, auth_headers: dict):
    await client.post("/api/v1/feedback", json={"type": "review", "text": "Excellent", "rating": 5}, headers=auth_headers)
    resp = await client.get("/api/v1/feedback/stats", headers=auth_headers)
    assert resp.status_code == 200
    assert "avg_rating" in resp.json()
    assert "nps_score" in resp.json()
