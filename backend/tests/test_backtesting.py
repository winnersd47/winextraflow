"""Tests for backtesting engine."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import Provider, ProviderSource
from app.models.signal import Signal, SignalAction, SignalStatus


@pytest.mark.asyncio
async def test_backtest_empty(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/backtest", headers=auth_headers, json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_signals"] == 0
    assert data["closed_signals"] == 0


@pytest.mark.asyncio
async def test_backtest_with_signals(client: AsyncClient, auth_headers: dict, db: AsyncSession):
    """Create closed signals and run backtest."""
    provider = Provider(name="BT_Provider", source=ProviderSource.MANUAL)
    db.add(provider)
    await db.flush()

    # Create closed signals
    for i, (profit, status) in enumerate([
        (5.0, SignalStatus.CLOSED_TP),
        (-3.0, SignalStatus.CLOSED_SL),
        (8.0, SignalStatus.CLOSED_TP),
        (2.0, SignalStatus.CLOSED_TP),
    ]):
        sig = Signal(
            provider_id=provider.id, ticker="BTCUSDT",
            action=SignalAction.BUY, entry_price=60000,
            close_price=60000 * (1 + profit / 100),
            profit_pct=profit, status=status,
        )
        db.add(sig)
    await db.commit()

    resp = await client.post("/api/v1/backtest", headers=auth_headers, json={
        "ticker": "BTCUSDT",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["closed_signals"] == 4
    assert data["win_rate"] == 0.75
    assert data["total_return_pct"] == 12.0
