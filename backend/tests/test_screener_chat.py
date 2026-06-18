"""Tests for screener and AI chat."""

import pytest
from httpx import AsyncClient


# ═══ SCREENER ═══

@pytest.mark.asyncio
async def test_screener_scan(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/screener/scan?market=all", headers=auth_headers)
    assert resp.status_code == 200
    assert "items" in resp.json()
    assert "total" in resp.json()


@pytest.mark.asyncio
async def test_screener_markets(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/screener/markets", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "MOEX" in data
    assert "Crypto" in data
    assert "Forex" in data
    assert "US Stocks" in data


@pytest.mark.asyncio
async def test_screener_filter_by_market(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/screener/scan?market=MOEX", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["market"] == "MOEX"


# ═══ AI CHAT ═══

@pytest.mark.asyncio
async def test_ai_chat_help(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/ai-chat/ask", json={"message": "help"}, headers=auth_headers)
    assert resp.status_code == 200
    assert "WinExtraFlow" in resp.json()["answer"]


@pytest.mark.asyncio
async def test_ai_chat_market(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/ai-chat/ask", json={"message": "лучшие сигналы"}, headers=auth_headers)
    assert resp.status_code == 200
    assert "answer" in resp.json()


@pytest.mark.asyncio
async def test_ai_chat_top_signals(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/ai-chat/ask", json={"message": "top signals"}, headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_ai_chat_providers(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/ai-chat/ask", json={"message": "лучшие провайдеры"}, headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_ai_chat_short_rejected(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/ai-chat/ask", json={"message": "a"}, headers=auth_headers)
    assert resp.status_code == 400
