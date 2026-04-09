"""Tests for AI Rating service."""

import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import Provider, ProviderSource
from app.models.signal import Signal, SignalAction, SignalStatus
from app.services.ai_rating import AIRatingService


@pytest.mark.asyncio
async def test_rate_signal_with_tp_sl(db: AsyncSession):
    """Signal with TP and SL should score higher."""
    provider = Provider(name="TestProv", source=ProviderSource.MANUAL)
    db.add(provider)
    await db.flush()

    signal = Signal(
        provider_id=provider.id,
        ticker="BTCUSDT",
        action=SignalAction.BUY,
        entry_price=65000,
        take_profit=70000,
        stop_loss=62000,
    )
    db.add(signal)
    await db.flush()

    service = AIRatingService()
    breakdown = await service.rate_signal(db, signal)

    assert 0 <= breakdown.final_confidence <= 1
    assert breakdown.scores["risk_management"] == 1.0
    assert breakdown.scores["risk_reward"] > 0.5


@pytest.mark.asyncio
async def test_rate_signal_without_tp_sl(db: AsyncSession):
    """Signal without TP/SL should score lower."""
    provider = Provider(name="TestProv2", source=ProviderSource.MANUAL)
    db.add(provider)
    await db.flush()

    signal = Signal(
        provider_id=provider.id,
        ticker="ETHUSDT",
        action=SignalAction.SELL,
        entry_price=3500,
    )
    db.add(signal)
    await db.flush()

    service = AIRatingService()
    breakdown = await service.rate_signal(db, signal)

    assert breakdown.scores["risk_management"] == 0.1
    assert breakdown.final_confidence < 0.7


@pytest.mark.asyncio
async def test_close_signal_profit(db: AsyncSession):
    """Closing a BUY signal above entry should give positive profit."""
    provider = Provider(name="TestProv3", source=ProviderSource.MANUAL)
    db.add(provider)
    await db.flush()

    signal = Signal(
        provider_id=provider.id, ticker="BTCUSDT",
        action=SignalAction.BUY, entry_price=60000,
    )
    db.add(signal)
    await db.commit()

    service = AIRatingService()
    closed = await service.close_signal(db, signal, close_price=66000)
    assert closed.profit_pct == pytest.approx(10.0, rel=0.01)
    assert closed.status == SignalStatus.CLOSED_TP
