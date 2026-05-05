"""Load & capacity tests — measure system limits and throughput.

Tests data volume handling, concurrent operations, and identifies bottlenecks.
"""

import asyncio
import time
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal import Signal, SignalAction, SignalStatus
from app.models.provider import Provider, ProviderSource
from app.models.user import User
from app.services.ai_rating import AIRatingService
from app.services.backtesting import BacktestingEngine
from app.services.telegram import TelegramParser


# ─── Volume Tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_bulk_signal_creation(db: AsyncSession):
    """Test: create 1000 signals and measure throughput."""
    provider = Provider(name=f"BulkProv_{uuid.uuid4().hex[:6]}", source=ProviderSource.MANUAL)
    db.add(provider)
    await db.flush()

    start = time.perf_counter()
    for i in range(1000):
        db.add(Signal(
            provider_id=provider.id,
            ticker=f"TEST{i % 50}USDT",
            action=SignalAction.BUY if i % 2 == 0 else SignalAction.SELL,
            entry_price=50000 + i,
            take_profit=55000 + i,
            stop_loss=48000 + i,
        ))
    await db.commit()
    elapsed = time.perf_counter() - start

    count = (await db.execute(select(func.count()).select_from(Signal))).scalar()
    assert count == 1000
    print(f"\n[METRIC] BULK INSERT: 1000 signals in {elapsed:.2f}s ({1000/elapsed:.0f} signals/sec)")
    assert elapsed < 10, f"Too slow: {elapsed:.2f}s for 1000 signals"


@pytest.mark.asyncio
async def test_bulk_signal_query_performance(db: AsyncSession):
    """Test: query signals with filters on 1000+ records."""
    provider = Provider(name=f"QueryProv_{uuid.uuid4().hex[:6]}", source=ProviderSource.MANUAL)
    db.add(provider)
    await db.flush()

    # Insert 1000 signals
    for i in range(1000):
        db.add(Signal(
            provider_id=provider.id,
            ticker="BTCUSDT" if i % 3 == 0 else "ETHUSDT",
            action=SignalAction.BUY,
            entry_price=60000 + i,
            status=SignalStatus.ACTIVE if i % 2 == 0 else SignalStatus.CLOSED_TP,
            profit_pct=float(i % 20 - 10) if i % 2 != 0 else None,
        ))
    await db.commit()

    # Query with filters
    start = time.perf_counter()
    result = await db.execute(
        select(Signal)
        .where(Signal.ticker == "BTCUSDT", Signal.status == SignalStatus.ACTIVE)
        .order_by(Signal.created_at.desc())
        .limit(50)
    )
    signals = result.scalars().all()
    elapsed = time.perf_counter() - start

    print(f"\n[METRIC] FILTERED QUERY: {len(signals)} results from 1000 signals in {elapsed*1000:.1f}ms")
    assert elapsed < 1, f"Query too slow: {elapsed:.2f}s"


@pytest.mark.asyncio
async def test_bulk_user_registration(client: AsyncClient):
    """Test: register 100 users concurrently."""
    start = time.perf_counter()
    tasks = []
    for i in range(100):
        tasks.append(client.post("/api/v1/auth/register", json={
            "email": f"load_{i}_{uuid.uuid4().hex[:4]}@test.com",
            "username": f"loaduser_{i}_{uuid.uuid4().hex[:4]}",
            "password": "TestPass123",
        }))
    results = await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - start

    success = sum(1 for r in results if r.status_code == 201)
    print(f"\n[METRIC] BULK REGISTER: {success}/100 users in {elapsed:.2f}s ({success/elapsed:.0f} users/sec)")
    assert success >= 95, f"Too many failures: {success}/100"


# ─── AI Rating Performance ─────────────────────────────────

@pytest.mark.asyncio
async def test_ai_rating_throughput(db: AsyncSession):
    """Test: rate 500 signals and measure throughput."""
    provider = Provider(name=f"RatingProv_{uuid.uuid4().hex[:6]}", source=ProviderSource.MANUAL, total_signals=100, win_rate=0.65)
    db.add(provider)
    await db.flush()

    signals = []
    for i in range(500):
        sig = Signal(
            provider_id=provider.id,
            ticker="BTCUSDT",
            action=SignalAction.BUY,
            entry_price=60000 + i,
            take_profit=65000 + i if i % 2 == 0 else None,
            stop_loss=58000 + i if i % 3 == 0 else None,
        )
        db.add(sig)
        signals.append(sig)
    await db.flush()

    service = AIRatingService()
    start = time.perf_counter()
    for sig in signals:
        breakdown = await service.rate_signal(db, sig)
        assert 0 <= breakdown.final_confidence <= 1
    elapsed = time.perf_counter() - start

    print(f"\n[METRIC] AI RATING: 500 signals in {elapsed:.2f}s ({500/elapsed:.0f} ratings/sec)")
    assert elapsed < 30, f"Too slow: {elapsed:.2f}s"


@pytest.mark.asyncio
async def test_provider_stats_recalculation(db: AsyncSession):
    """Test: recalculate stats for provider with 500 closed signals."""
    provider = Provider(name=f"StatsProv_{uuid.uuid4().hex[:6]}", source=ProviderSource.MANUAL)
    db.add(provider)
    await db.flush()

    for i in range(500):
        db.add(Signal(
            provider_id=provider.id,
            ticker="BTCUSDT",
            action=SignalAction.BUY,
            entry_price=60000,
            close_price=60000 + (i % 30 - 10) * 100,
            profit_pct=float(i % 30 - 10),
            status=SignalStatus.CLOSED_TP if i % 3 != 0 else SignalStatus.CLOSED_SL,
        ))
    await db.commit()

    service = AIRatingService()
    start = time.perf_counter()
    updated = await service.recalculate_provider_stats(db, provider.id)
    elapsed = time.perf_counter() - start

    print(f"\n[METRIC] PROVIDER STATS: 500 signals recalculated in {elapsed*1000:.1f}ms")
    print(f"   win_rate={updated.win_rate:.2f}, sharpe={updated.sharpe_ratio}, pf={updated.profit_factor}, dd={updated.max_drawdown}")
    assert updated.win_rate is not None
    assert updated.sharpe_ratio is not None
    assert elapsed < 5


# ─── Backtesting Performance ──────────────────────────────

@pytest.mark.asyncio
async def test_backtest_large_dataset(db: AsyncSession, client: AsyncClient, auth_headers: dict):
    """Test: backtest with 1000 closed signals."""
    provider = Provider(name=f"BacktestProv_{uuid.uuid4().hex[:6]}", source=ProviderSource.MANUAL)
    db.add(provider)
    await db.flush()

    for i in range(1000):
        db.add(Signal(
            provider_id=provider.id,
            ticker="BTCUSDT",
            action=SignalAction.BUY,
            entry_price=60000,
            close_price=60000 + (i % 40 - 15) * 100,
            profit_pct=float(i % 40 - 15) / 3,
            status=SignalStatus.CLOSED_TP if i % 3 != 0 else SignalStatus.CLOSED_SL,
        ))
    await db.commit()

    start = time.perf_counter()
    resp = await client.post("/api/v1/backtest", headers=auth_headers, json={"ticker": "BTCUSDT"})
    elapsed = time.perf_counter() - start

    assert resp.status_code == 200
    data = resp.json()
    print(f"\n[METRIC] BACKTEST: {data['closed_signals']} trades in {elapsed:.2f}s")
    print(f"   return={data['total_return_pct']:.1f}%, sharpe={data['sharpe_ratio']}, wr={data['win_rate']:.0%}")
    assert data["closed_signals"] == 1000
    assert elapsed < 10


# ─── Telegram Parser Performance ───────────────────────────

@pytest.mark.asyncio
async def test_telegram_parser_throughput():
    """Test: parse 10000 messages and measure throughput."""
    messages = [
        "🟢 BUY BTCUSDT @ 65000 TP: 67000 SL: 63000",
        "ETHUSDT SELL\nEntry: 3500\nTP: 3200\nSL: 3700",
        "#SOLUSDT 🟢 Entry: 145 | TP1: 160 | SL: 135",
        "Buy DOGEUSDT 0.12",
        "Random message that is not a signal at all",
        "Just chatting about market conditions today",
        "🔴 SELL BNBUSDT @ 580 TP: 550 SL: 600",
        "XRPUSDT BUY\nEntry: 0.55\nTP: 0.65\nSL: 0.50",
    ]

    parser = TelegramParser()
    start = time.perf_counter()
    parsed = 0
    skipped = 0
    for i in range(10000):
        msg = messages[i % len(messages)]
        result = parser.parse_message(msg)
        if result:
            parsed += 1
        else:
            skipped += 1
    elapsed = time.perf_counter() - start

    print(f"\n[METRIC] TELEGRAM PARSER: 10000 messages in {elapsed:.2f}s ({10000/elapsed:.0f} msg/sec)")
    print(f"   parsed={parsed}, skipped={skipped}")
    assert elapsed < 5, f"Parser too slow: {elapsed:.2f}s"
    assert parsed > 5000  # At least 6/8 formats should parse


# ─── Concurrent API Requests ──────────────────────────────

@pytest.mark.asyncio
async def test_concurrent_signal_list(client: AsyncClient, auth_headers: dict, db: AsyncSession):
    """Test: 50 concurrent GET /signals requests."""
    # Seed some signals
    provider = Provider(name=f"ConcProv_{uuid.uuid4().hex[:6]}", source=ProviderSource.MANUAL)
    db.add(provider)
    await db.flush()
    for i in range(100):
        db.add(Signal(provider_id=provider.id, ticker="BTCUSDT", action=SignalAction.BUY, entry_price=60000+i))
    await db.commit()

    start = time.perf_counter()
    tasks = [client.get("/api/v1/signals?limit=50", headers=auth_headers) for _ in range(50)]
    results = await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - start

    success = sum(1 for r in results if r.status_code == 200)
    print(f"\n[METRIC] CONCURRENT READS: 50 requests in {elapsed:.2f}s ({50/elapsed:.0f} req/sec)")
    assert success == 50


@pytest.mark.asyncio
async def test_concurrent_webhook_ingestion(client: AsyncClient):
    """Test: 100 concurrent TradingView webhook submissions."""
    start = time.perf_counter()
    tasks = []
    for i in range(100):
        tasks.append(client.post("/api/v1/signals/webhook/tradingview", json={
            "ticker": f"PAIR{i}USDT",
            "action": "buy",
            "price": 50000 + i * 10,
            "take_profit": 55000 + i * 10,
            "stop_loss": 48000 + i * 10,
        }))
    results = await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - start

    success = sum(1 for r in results if r.status_code == 201)
    print(f"\n[METRIC] CONCURRENT WEBHOOKS: {success}/100 in {elapsed:.2f}s ({success/elapsed:.0f} webhooks/sec)")
    assert success >= 90


# ─── Database Size Estimation ──────────────────────────────

@pytest.mark.asyncio
async def test_database_size_estimation(db: AsyncSession):
    """Estimate DB size for different user scales."""
    # Create realistic dataset
    provider = Provider(name=f"SizeProv_{uuid.uuid4().hex[:6]}", source=ProviderSource.MANUAL)
    db.add(provider)
    await db.flush()

    # 500 signals with full data
    for i in range(500):
        db.add(Signal(
            provider_id=provider.id,
            ticker="BTCUSDT",
            action=SignalAction.BUY,
            entry_price=60000,
            take_profit=65000,
            stop_loss=58000,
            timeframe="4h",
            ai_confidence=0.75,
            ai_reasoning="Test reasoning for signal quality assessment with multiple factors",
            raw_message=f"Sample raw message from Telegram channel with signal data #{i}",
            status=SignalStatus.CLOSED_TP,
            close_price=65000,
            profit_pct=8.33,
        ))
    await db.commit()

    # Estimate row size
    count = (await db.execute(select(func.count()).select_from(Signal))).scalar()

    # SQLite doesn't have pg_relation_size, estimate manually
    # Average signal row: ~500 bytes (UUID + strings + floats + timestamps)
    avg_row_bytes = 500
    total_bytes = count * avg_row_bytes

    print(f"\n[METRIC] DATABASE SIZE ESTIMATION:")
    print(f"   Signals in DB: {count}")
    print(f"   Estimated row size: ~{avg_row_bytes} bytes")
    print(f"   Current data: ~{total_bytes/1024:.0f} KB")
    print(f"")
    print(f"   === PROJECTIONS ===")
    for users, signals_per_user, signals_per_day in [
        (100, 50, 500),
        (1_000, 50, 5_000),
        (10_000, 50, 50_000),
        (100_000, 50, 500_000),
        (1_000_000, 50, 5_000_000),
    ]:
        total_signals = users * signals_per_user
        daily_bytes = signals_per_day * avg_row_bytes
        monthly_gb = daily_bytes * 30 / (1024**3)
        total_gb = total_signals * avg_row_bytes / (1024**3)
        print(f"   {users:>10,} users: {total_signals:>12,} signals = {total_gb:.2f} GB "
              f"(+{monthly_gb:.3f} GB/month @ {signals_per_day:,}/day)")

    assert count == 500
