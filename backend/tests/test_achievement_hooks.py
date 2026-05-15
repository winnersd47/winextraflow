"""Test that achievements progress correctly from real user actions.

Verifies every hook: signal view, trade execution, backtest, strategy publish,
strategy subscribe, referral registration.
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.achievement import Achievement, UserAchievement
from app.models.provider import Provider, ProviderSource
from app.services.achievements import AchievementService


async def _get_progress(db: AsyncSession, user_id, code: str) -> int:
    """Helper: get achievement progress for a user."""
    ach = (await db.execute(select(Achievement).where(Achievement.code == code))).scalar_one_or_none()
    if not ach:
        return -1
    ua = (await db.execute(select(UserAchievement).where(
        UserAchievement.user_id == user_id,
        UserAchievement.achievement_id == ach.id,
    ))).scalar_one_or_none()
    return ua.progress if ua else 0


async def _seed_achievements(db: AsyncSession):
    """Seed achievements if not already seeded."""
    svc = AchievementService()
    await svc.seed_achievements(db)


# ═══════════════════════════════════════════════════════════
# 1. VIEW SIGNAL → first_signal + signal_hunter
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_view_signal_achievement(client: AsyncClient, auth_headers: dict, db: AsyncSession, registered_user: dict):
    """Viewing a signal should increment first_signal and signal_hunter."""
    await _seed_achievements(db)

    # Create a signal to view
    sig = await client.post("/api/v1/signals/webhook/tradingview", json={
        "ticker": "BTCUSDT", "action": "buy", "price": 65000,
    })
    assert sig.status_code == 201
    signal_id = sig.json()["id"]

    # View the signal
    resp = await client.get(f"/api/v1/signals/{signal_id}", headers=auth_headers)
    assert resp.status_code == 200

    # Check progress
    from app.models.user import User
    user = (await db.execute(select(User).where(User.email == registered_user["email"]))).scalar_one()

    p1 = await _get_progress(db, user.id, "first_signal")
    p2 = await _get_progress(db, user.id, "signal_hunter")

    assert p1 >= 1, f"first_signal progress should be >= 1, got {p1}"
    assert p2 >= 1, f"signal_hunter progress should be >= 1, got {p2}"
    print(f"[HOOK] View signal: first_signal={p1}, signal_hunter={p2} PASSED")


# ═══════════════════════════════════════════════════════════
# 2. VIEW 3 SIGNALS → signal_hunter increments 3 times
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_multiple_signal_views(client: AsyncClient, auth_headers: dict, db: AsyncSession, registered_user: dict):
    """Viewing multiple signals should accumulate signal_hunter progress."""
    await _seed_achievements(db)

    signal_ids = []
    for i in range(3):
        sig = await client.post("/api/v1/signals/webhook/tradingview", json={
            "ticker": f"VIEW{i}USDT", "action": "buy", "price": 1000 + i,
        })
        signal_ids.append(sig.json()["id"])

    for sid in signal_ids:
        await client.get(f"/api/v1/signals/{sid}", headers=auth_headers)

    from app.models.user import User
    user = (await db.execute(select(User).where(User.email == registered_user["email"]))).scalar_one()

    p = await _get_progress(db, user.id, "signal_hunter")
    assert p >= 3, f"signal_hunter should be >= 3 after 3 views, got {p}"
    print(f"[HOOK] 3 signal views: signal_hunter={p} PASSED")


# ═══════════════════════════════════════════════════════════
# 3. EXECUTE TRADE → first_trade + trader_10 + trader_100
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_execute_trade_achievement(client: AsyncClient, premium_auth_headers: dict, db: AsyncSession, registered_user: dict):
    """Executing a trade should increment first_trade, trader_10, trader_100."""
    await _seed_achievements(db)

    # Create demo account
    acc = await client.post("/api/v1/execution/accounts", headers=premium_auth_headers, json={
        "exchange": "demo", "label": "AchTest", "api_key": "demo", "api_secret": "demo",
        "min_confidence": 0.1,
    })
    account_id = acc.json()["id"]

    # Create signal with TP/SL for higher confidence
    sig = await client.post("/api/v1/signals/webhook/tradingview", json={
        "ticker": "BTCUSDT", "action": "buy", "price": 65000,
        "take_profit": 70000, "stop_loss": 62000,
    })
    signal_id = sig.json()["id"]

    # Execute
    exec_resp = await client.post(f"/api/v1/execution/execute/{signal_id}",
        headers=premium_auth_headers, json={"exchange_account_id": account_id})
    assert exec_resp.status_code == 200

    from app.models.user import User
    user = (await db.execute(select(User).where(User.email == registered_user["email"]))).scalar_one()

    p1 = await _get_progress(db, user.id, "first_trade")
    p10 = await _get_progress(db, user.id, "trader_10")
    p100 = await _get_progress(db, user.id, "trader_100")

    assert p1 >= 1, f"first_trade should be >= 1, got {p1}"
    assert p10 >= 1, f"trader_10 should be >= 1, got {p10}"
    assert p100 >= 1, f"trader_100 should be >= 1, got {p100}"
    print(f"[HOOK] Execute trade: first_trade={p1}, trader_10={p10}, trader_100={p100} PASSED")


# ═══════════════════════════════════════════════════════════
# 4. RUN BACKTEST → first_backtest
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_backtest_achievement(client: AsyncClient, auth_headers: dict, db: AsyncSession, registered_user: dict):
    """Running a backtest should increment first_backtest."""
    await _seed_achievements(db)

    resp = await client.post("/api/v1/backtest", headers=auth_headers, json={})
    assert resp.status_code == 200

    from app.models.user import User
    user = (await db.execute(select(User).where(User.email == registered_user["email"]))).scalar_one()

    p = await _get_progress(db, user.id, "first_backtest")
    assert p >= 1, f"first_backtest should be >= 1, got {p}"
    print(f"[HOOK] Backtest: first_backtest={p} PASSED")


# ═══════════════════════════════════════════════════════════
# 5. PUBLISH STRATEGY → strategy_creator
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_publish_strategy_achievement(client: AsyncClient, premium_auth_headers: dict, db: AsyncSession, registered_user: dict):
    """Publishing a strategy should increment strategy_creator."""
    await _seed_achievements(db)

    # Create provider first (requires analyst/admin)
    prov = await client.post("/api/v1/providers", headers=premium_auth_headers, json={
        "name": f"AchProv_{uuid.uuid4().hex[:6]}", "source": "manual",
    })
    provider_id = prov.json()["id"]

    # Publish strategy
    strat = await client.post("/api/v1/strategies", headers=premium_auth_headers, json={
        "provider_id": provider_id,
        "name": f"AchStrat_{uuid.uuid4().hex[:6]}",
    })
    assert strat.status_code == 201

    from app.models.user import User
    user = (await db.execute(select(User).where(User.email == registered_user["email"]))).scalar_one()

    p = await _get_progress(db, user.id, "strategy_creator")
    assert p >= 1, f"strategy_creator should be >= 1, got {p}"
    print(f"[HOOK] Publish strategy: strategy_creator={p} PASSED")


# ═══════════════════════════════════════════════════════════
# 6. SUBSCRIBE TO STRATEGY → first_subscription
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_subscribe_strategy_achievement(client: AsyncClient, premium_auth_headers: dict, auth_headers: dict, db: AsyncSession, registered_user: dict):
    """Subscribing to a strategy should increment first_subscription."""
    await _seed_achievements(db)

    # Create provider + strategy (requires analyst/admin)
    prov = await client.post("/api/v1/providers", headers=premium_auth_headers, json={
        "name": f"SubProv_{uuid.uuid4().hex[:6]}", "source": "manual",
    })
    strat = await client.post("/api/v1/strategies", headers=premium_auth_headers, json={
        "provider_id": prov.json()["id"],
        "name": f"SubStrat_{uuid.uuid4().hex[:6]}",
    })
    strategy_id = strat.json()["id"]

    # Subscribe
    sub = await client.post(f"/api/v1/strategies/{strategy_id}/subscribe", headers=auth_headers)
    assert sub.status_code == 200

    from app.models.user import User
    user = (await db.execute(select(User).where(User.email == registered_user["email"]))).scalar_one()

    p = await _get_progress(db, user.id, "first_subscription")
    assert p >= 1, f"first_subscription should be >= 1, got {p}"
    print(f"[HOOK] Subscribe strategy: first_subscription={p} PASSED")


# ═══════════════════════════════════════════════════════════
# 7. REFERRAL REGISTRATION → referrer gets first_referral
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_referral_achievement(client: AsyncClient, seed_referrer: str, db: AsyncSession):
    """Registering with a referral code should give the referrer first_referral progress."""
    await _seed_achievements(db)

    # Register referrer
    r1 = await client.post("/api/v1/auth/register", json={
        "email": "ach_referrer@test.com", "username": "ach_referrer",
        "password": "Pass123", "referral_code": seed_referrer,
    })
    assert r1.status_code == 201
    referrer_code = r1.json()["referral_code"]
    referrer_id = uuid.UUID(r1.json()["id"])

    # Register referred user using referrer's code
    r2 = await client.post("/api/v1/auth/register", json={
        "email": "ach_referred@test.com", "username": "ach_referred",
        "password": "Pass123", "referral_code": referrer_code,
    })
    assert r2.status_code == 201

    p1 = await _get_progress(db, referrer_id, "first_referral")
    p5 = await _get_progress(db, referrer_id, "referral_5")
    p25 = await _get_progress(db, referrer_id, "referral_25")

    assert p1 >= 1, f"first_referral should be >= 1, got {p1}"
    assert p5 >= 1, f"referral_5 should be >= 1, got {p5}"
    assert p25 >= 1, f"referral_25 should be >= 1, got {p25}"
    print(f"[HOOK] Referral: first_referral={p1}, referral_5={p5}, referral_25={p25} PASSED")


# ═══════════════════════════════════════════════════════════
# 8. ACHIEVEMENT UNLOCKS AT THRESHOLD
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_achievement_unlocks_at_threshold(db: AsyncSession):
    """Achievement should unlock when progress reaches requirement_value."""
    await _seed_achievements(db)

    from app.models.user import User
    import secrets
    user = User(
        email="unlock_test@test.com", username="unlock_test",
        hashed_password="$2b$12$dummy", referral_code=secrets.token_urlsafe(8),
    )
    db.add(user)
    await db.flush()

    svc = AchievementService()

    # first_signal requires 1 — should unlock immediately
    unlocked = await svc.increment_progress(db, user.id, "first_signal")
    assert unlocked is True, "first_signal should unlock at progress=1"

    # Verify is_unlocked flag
    ach = (await db.execute(select(Achievement).where(Achievement.code == "first_signal"))).scalar_one()
    ua = (await db.execute(select(UserAchievement).where(
        UserAchievement.user_id == user.id,
        UserAchievement.achievement_id == ach.id,
    ))).scalar_one()
    assert ua.is_unlocked is True
    assert ua.progress == 1

    # Second increment should return False (already unlocked)
    unlocked2 = await svc.increment_progress(db, user.id, "first_signal")
    assert unlocked2 is False

    print("[HOOK] Achievement unlock at threshold: PASSED")


# ═══════════════════════════════════════════════════════════
# 9. XP ACCUMULATION
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_xp_accumulates(db: AsyncSession):
    """Unlocking achievements should accumulate XP."""
    await _seed_achievements(db)

    from app.models.user import User
    import secrets
    user = User(
        email="xp_test@test.com", username="xp_test",
        hashed_password="$2b$12$dummy", referral_code=secrets.token_urlsafe(8),
    )
    db.add(user)
    await db.flush()

    svc = AchievementService()

    # Unlock first_signal (+10 XP) and first_backtest (+20 XP)
    await svc.increment_progress(db, user.id, "first_signal")
    await svc.increment_progress(db, user.id, "first_backtest")

    xp_data = await svc.get_user_xp(db, user.id)
    assert xp_data["total_xp"] == 30, f"Expected 30 XP (10+20), got {xp_data['total_xp']}"
    assert xp_data["level"] >= 1

    print(f"[HOOK] XP accumulation: {xp_data['total_xp']} XP, level {xp_data['level']} PASSED")
