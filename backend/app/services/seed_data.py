"""Seed realistic test data — providers, signals, strategies, users.

All test data is marked with [TEST] prefix for easy identification.
Call seed_test_data(db) on startup when APP_ENV=development.
"""

import logging
import random
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import Provider, ProviderSource
from app.models.signal import Signal, SignalAction, SignalStatus
from app.models.strategy import Strategy, PriceType
from app.models.user import User, UserRole
from app.api.deps import hash_password

logger = logging.getLogger(__name__)

# ─── Test Providers ─────────────────────────────────────────

TEST_PROVIDERS = [
    # Crypto
    {
        "name": "[TEST] CryptoWhale Signals",
        "source": ProviderSource.TELEGRAM,
        "description": "Top crypto signals from whale tracker. 70%+ win rate.",
        "telegram_channel_id": "-1001234567001",
    },
    {
        "name": "[TEST] BTC Scalper Pro",
        "source": ProviderSource.TRADINGVIEW,
        "description": "Bitcoin scalping alerts. 15m-1h timeframes.",
        "tradingview_webhook_id": "tv_btc_scalper",
    },
    {
        "name": "[TEST] Altcoin Hunter",
        "source": ProviderSource.TELEGRAM,
        "description": "Early altcoin entries before pumps. Mid-term holds.",
        "telegram_channel_id": "-1001234567002",
    },
    # Forex
    {
        "name": "[TEST] Forex Flow",
        "source": ProviderSource.TRADINGVIEW,
        "description": "Major forex pairs. Technical analysis based.",
        "tradingview_webhook_id": "tv_forex_flow",
    },
    {
        "name": "[TEST] Forex Breakout Lab",
        "source": ProviderSource.TRADINGVIEW,
        "description": "Breakout strategies on EUR/GBP/JPY pairs. Session-based entries.",
        "tradingview_webhook_id": "tv_forex_breakout",
    },
    # DeFi / On-chain
    {
        "name": "[TEST] DeFi Alpha",
        "source": ProviderSource.MANUAL,
        "description": "DeFi token signals. On-chain analytics based.",
    },
    # Stocks / Indices
    {
        "name": "[TEST] US Tech Momentum",
        "source": ProviderSource.TRADINGVIEW,
        "description": "AAPL, MSFT, NVDA, TSLA momentum signals. Daily timeframe.",
        "tradingview_webhook_id": "tv_us_tech",
    },
    {
        "name": "[TEST] RU Market Navigator",
        "source": ProviderSource.TELEGRAM,
        "description": "SBER, GAZP, LKOH, YNDX signals for MOEX. Mid-term holds.",
        "telegram_channel_id": "-1001234567003",
    },
    # Multi-asset / Commodities
    {
        "name": "[TEST] Commodities AI",
        "source": ProviderSource.MANUAL,
        "description": "Gold, Silver, Oil signals powered by AI analysis.",
    },
    {
        "name": "[TEST] Index Trend Surfer",
        "source": ProviderSource.TRADINGVIEW,
        "description": "SP500, NASDAQ, DAX trend-following signals. 4h-1d.",
        "tradingview_webhook_id": "tv_indices",
    },
    # ─── Additional providers (batch 2) ──────
    {
        "name": "[TEST] ETH Maximalist",
        "source": ProviderSource.TELEGRAM,
        "description": "Ethereum ecosystem: ETH, L2 tokens, DeFi blue chips. Swing trades 1-7 days.",
        "telegram_channel_id": "-1001234567010",
    },
    {
        "name": "[TEST] Scalp King",
        "source": ProviderSource.TRADINGVIEW,
        "description": "High-frequency scalping on BTC/ETH. 1m-5m timeframes. 50+ trades/day.",
        "tradingview_webhook_id": "tv_scalp_king",
    },
    {
        "name": "[TEST] Macro Trader",
        "source": ProviderSource.MANUAL,
        "description": "Global macro signals: indices, bonds, FX crosses. Based on economic data.",
    },
    {
        "name": "[TEST] Asian Markets",
        "source": ProviderSource.TRADINGVIEW,
        "description": "JPY pairs, Nikkei, HSI signals. Asian session focus.",
        "tradingview_webhook_id": "tv_asian",
    },
    {
        "name": "[TEST] Swing Master",
        "source": ProviderSource.TELEGRAM,
        "description": "Multi-asset swing trades. 1D-1W timeframes. Patience-based strategy.",
        "telegram_channel_id": "-1001234567011",
    },
    {
        "name": "[TEST] Crypto Gems",
        "source": ProviderSource.TELEGRAM,
        "description": "Low-cap altcoins before pumps. High risk, high reward. DYOR.",
        "telegram_channel_id": "-1001234567012",
    },
    {
        "name": "[TEST] Oil & Energy",
        "source": ProviderSource.TRADINGVIEW,
        "description": "USOIL, Natural Gas, energy stocks. Fundamental + technical.",
        "tradingview_webhook_id": "tv_oil_energy",
    },
    {
        "name": "[TEST] Quant Algo V2",
        "source": ProviderSource.MANUAL,
        "description": "Algorithmic signals from quantitative models. Mean reversion + momentum.",
    },
    {
        "name": "[TEST] EUR/USD Specialist",
        "source": ProviderSource.TRADINGVIEW,
        "description": "Dedicated EURUSD analysis. All timeframes. 5+ years track record.",
        "tradingview_webhook_id": "tv_eurusd_spec",
    },
    {
        "name": "[TEST] Precious Metals",
        "source": ProviderSource.MANUAL,
        "description": "Gold, Silver, Platinum signals. Safe-haven analysis. Weekly outlook.",
    },
]

# ─── Test Signal Templates ──────────────────────────────────

SIGNAL_TEMPLATES = [
    # ─── Crypto majors ───
    {"ticker": "BTCUSDT", "base_price": 67500, "volatility": 3000},
    {"ticker": "BTCUSDT", "base_price": 65000, "volatility": 2500},
    {"ticker": "BTCUSDT", "base_price": 69000, "volatility": 4000},
    {"ticker": "ETHUSDT", "base_price": 3450, "volatility": 200},
    {"ticker": "ETHUSDT", "base_price": 3600, "volatility": 150},
    # ─── Crypto altcoins ───
    {"ticker": "SOLUSDT", "base_price": 145, "volatility": 15},
    {"ticker": "BNBUSDT", "base_price": 580, "volatility": 30},
    {"ticker": "XRPUSDT", "base_price": 0.55, "volatility": 0.05},
    {"ticker": "DOGEUSDT", "base_price": 0.12, "volatility": 0.015},
    {"ticker": "AVAXUSDT", "base_price": 35, "volatility": 4},
    {"ticker": "ADAUSDT", "base_price": 0.45, "volatility": 0.04},
    {"ticker": "DOTUSDT", "base_price": 7.20, "volatility": 0.8},
    {"ticker": "MATICUSDT", "base_price": 0.70, "volatility": 0.08},
    {"ticker": "LINKUSDT", "base_price": 14.50, "volatility": 1.5},
    {"ticker": "NEARUSDT", "base_price": 6.80, "volatility": 0.7},
    {"ticker": "AAVEUSDT", "base_price": 95, "volatility": 10},
    {"ticker": "UNIUSDT", "base_price": 7.50, "volatility": 0.8},
    {"ticker": "ARBUSDT", "base_price": 1.10, "volatility": 0.12},
    # ─── Forex majors ───
    {"ticker": "EURUSD", "base_price": 1.0850, "volatility": 0.005},
    {"ticker": "GBPUSD", "base_price": 1.2720, "volatility": 0.006},
    {"ticker": "USDJPY", "base_price": 155.50, "volatility": 1.5},
    {"ticker": "USDCHF", "base_price": 0.8830, "volatility": 0.004},
    {"ticker": "AUDUSD", "base_price": 0.6620, "volatility": 0.005},
    {"ticker": "USDCAD", "base_price": 1.3650, "volatility": 0.005},
    {"ticker": "EURGBP", "base_price": 0.8530, "volatility": 0.003},
    {"ticker": "EURJPY", "base_price": 168.70, "volatility": 1.2},
    {"ticker": "GBPJPY", "base_price": 197.80, "volatility": 1.8},
    # ─── US Stocks ───
    {"ticker": "AAPL", "base_price": 192.50, "volatility": 8},
    {"ticker": "MSFT", "base_price": 415.00, "volatility": 15},
    {"ticker": "NVDA", "base_price": 880.00, "volatility": 50},
    {"ticker": "TSLA", "base_price": 245.00, "volatility": 20},
    {"ticker": "GOOGL", "base_price": 175.30, "volatility": 7},
    {"ticker": "AMZN", "base_price": 185.60, "volatility": 8},
    {"ticker": "META", "base_price": 505.00, "volatility": 20},
    # ─── RU Stocks (MOEX) ───
    {"ticker": "SBER", "base_price": 305.0, "volatility": 12},
    {"ticker": "GAZP", "base_price": 163.0, "volatility": 8},
    {"ticker": "LKOH", "base_price": 7200.0, "volatility": 300},
    {"ticker": "YNDX", "base_price": 3800.0, "volatility": 150},
    {"ticker": "GMKN", "base_price": 155.0, "volatility": 7},
    # ─── Commodities & Indices ───
    {"ticker": "XAUUSD", "base_price": 2350.0, "volatility": 40},
    {"ticker": "XAGUSD", "base_price": 29.50, "volatility": 1.5},
    {"ticker": "USOIL", "base_price": 78.50, "volatility": 3},
    {"ticker": "SPX500", "base_price": 5320.0, "volatility": 60},
    {"ticker": "NAS100", "base_price": 18750.0, "volatility": 250},
    {"ticker": "DAX40", "base_price": 18200.0, "volatility": 200},
]


async def seed_test_data(db: AsyncSession):
    """Seed realistic test data into the database."""

    # Check if already seeded
    existing = (await db.execute(
        select(Provider).where(Provider.name.like("[TEST]%"))
    )).scalar_one_or_none()
    if existing:
        logger.info("Test data already seeded, skipping")
        return

    random.seed(42)
    now = datetime.now(timezone.utc)
    logger.info("Seeding test data...")

    # ─── Create test users ────────────────────────────────
    test_users = []
    for i, (username, email) in enumerate([
        ("[TEST] trader_mike", "test_mike@winextraflow.com"),
        ("[TEST] crypto_anna", "test_anna@winextraflow.com"),
        ("[TEST] signal_master", "test_master@winextraflow.com"),
        ("[TEST] forex_pro", "test_forex@winextraflow.com"),
        ("[TEST] stock_guru", "test_stocks@winextraflow.com"),
        ("[TEST] algo_bot", "test_algo@winextraflow.com"),
        ("[TEST] whale_watcher", "test_whale@winextraflow.com"),
        ("[TEST] moex_trader", "test_moex@winextraflow.com"),
    ]):
        user = User(
            email=email,
            username=username,
            hashed_password=hash_password("TestPass123"),
            referral_code=secrets.token_urlsafe(8),
            role=UserRole.USER,
        )
        db.add(user)
        test_users.append(user)
    await db.flush()

    # ─── Create providers ─────────────────────────────────
    providers = []
    for p_data in TEST_PROVIDERS:
        provider = Provider(
            name=p_data["name"],
            source=p_data["source"],
            description=p_data["description"],
            is_active=True,
            telegram_channel_id=p_data.get("telegram_channel_id"),
            tradingview_webhook_id=p_data.get("tradingview_webhook_id"),
        )
        db.add(provider)
        providers.append(provider)
    await db.flush()

    # ─── Create signals (500-800 total, mixed statuses) ────
    total_signals = 0
    for provider in providers:
        num_signals = random.randint(50, 80)
        for j in range(num_signals):
            template = random.choice(SIGNAL_TEMPLATES)
            is_buy = random.random() > 0.4  # 60% buys
            entry = template["base_price"] + random.uniform(-template["volatility"], template["volatility"])
            tp_dist = template["volatility"] * random.uniform(0.5, 2.0)
            sl_dist = template["volatility"] * random.uniform(0.3, 1.0)

            if is_buy:
                tp = entry + tp_dist
                sl = entry - sl_dist
            else:
                tp = entry - tp_dist
                sl = entry + sl_dist

            # Time: spread over last 90 days
            created = now - timedelta(days=random.uniform(0, 90), hours=random.uniform(0, 24))

            # Status: 40% active, 35% TP, 15% SL, 10% expired
            roll = random.random()
            if roll < 0.40:
                status = SignalStatus.ACTIVE
                close_price = None
                profit_pct = None
            elif roll < 0.75:
                # Won — closed at TP
                status = SignalStatus.CLOSED_TP
                profit_pct = random.uniform(1.0, 12.0)
                close_price = entry * (1 + profit_pct / 100) if is_buy else entry * (1 - profit_pct / 100)
            elif roll < 0.90:
                # Lost — closed at SL
                status = SignalStatus.CLOSED_SL
                profit_pct = random.uniform(-8.0, -0.5)
                close_price = entry * (1 + profit_pct / 100) if is_buy else entry * (1 - profit_pct / 100)
            else:
                status = SignalStatus.EXPIRED
                close_price = None
                profit_pct = None

            # AI confidence based on signal quality
            confidence = random.uniform(0.35, 0.95)
            if tp and sl:
                confidence += 0.1
            confidence = min(1.0, confidence)

            reasoning_parts = []
            if confidence > 0.7:
                reasoning_parts.append("Strong: good risk management, reliable provider")
            elif confidence > 0.5:
                reasoning_parts.append("Average quality across factors")
            else:
                reasoning_parts.append("Weak: missing TP/SL or low provider history")

            timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]

            signal = Signal(
                provider_id=provider.id,
                ticker=template["ticker"],
                action=SignalAction.BUY if is_buy else SignalAction.SELL,
                entry_price=round(entry, 6),
                take_profit=round(tp, 6) if random.random() > 0.1 else None,
                stop_loss=round(sl, 6) if random.random() > 0.15 else None,
                timeframe=random.choice(timeframes),
                status=status,
                close_price=round(close_price, 6) if close_price else None,
                profit_pct=round(profit_pct, 2) if profit_pct else None,
                ai_confidence=round(confidence, 3),
                ai_reasoning=reasoning_parts[0],
                raw_message=f"[TEST] Auto-generated signal #{total_signals}",
            )
            signal.created_at = created
            db.add(signal)
            total_signals += 1

    await db.flush()

    # ─── Update provider stats ────────────────────────────
    from app.services.ai_rating import ai_rating_service
    for provider in providers:
        await ai_rating_service.recalculate_provider_stats(db, provider.id)

    # ─── Create strategies ────────────────────────────────
    strategy_configs = [
        # Crypto
        {"provider_idx": 0, "name": "[TEST] Whale Watch Alpha", "desc": "Follow the whales. BTC/ETH focus. 70%+ win rate historical.",
         "tags": "crypto,btc,eth,whales", "price_type": PriceType.FREE},
        {"provider_idx": 1, "name": "[TEST] BTC Scalp Machine", "desc": "High-frequency BTC scalping. 15m-1h entries with tight stops.",
         "tags": "crypto,btc,scalping,short-term", "price_type": PriceType.PREMIUM},
        {"provider_idx": 2, "name": "[TEST] Altseason Picks", "desc": "Altcoin gems before they pump. Mid-term 1-4 week holds.",
         "tags": "crypto,altcoins,mid-term", "price_type": PriceType.PAID, "monthly": 19.99},
        # Forex
        {"provider_idx": 3, "name": "[TEST] Forex Momentum", "desc": "Major pairs momentum trades. 4h-1d timeframes.",
         "tags": "forex,eur,gbp,jpy", "price_type": PriceType.FREE},
        {"provider_idx": 4, "name": "[TEST] Forex Breakout Master", "desc": "Session-based breakout entries on EUR/GBP/JPY. High R:R.",
         "tags": "forex,breakout,session", "price_type": PriceType.PAID, "monthly": 14.99},
        # DeFi
        {"provider_idx": 5, "name": "[TEST] DeFi Deep Dive", "desc": "On-chain alpha for DeFi tokens. Research-backed signals.",
         "tags": "crypto,defi,research", "price_type": PriceType.PAID, "monthly": 29.99},
        # Stocks
        {"provider_idx": 6, "name": "[TEST] US Tech Rocket", "desc": "AAPL, NVDA, TSLA momentum signals. Daily timeframe, trend-following.",
         "tags": "stocks,us,tech,momentum", "price_type": PriceType.PAID, "monthly": 24.99},
        {"provider_idx": 7, "name": "[TEST] MOEX Value Picks", "desc": "SBER, GAZP, LKOH value + momentum. Mid-term 1-3 months.",
         "tags": "stocks,ru,moex,value", "price_type": PriceType.FREE},
        # Commodities / Indices
        {"provider_idx": 8, "name": "[TEST] Gold & Silver AI", "desc": "XAUUSD, XAGUSD signals powered by AI analysis. All timeframes.",
         "tags": "commodities,gold,silver,ai", "price_type": PriceType.PREMIUM},
        {"provider_idx": 9, "name": "[TEST] Index Trend Surfer", "desc": "SP500, NASDAQ, DAX trend-following. 4h-1d confirmed breakouts.",
         "tags": "indices,sp500,nasdaq,dax,trend", "price_type": PriceType.PAID, "monthly": 19.99},
    ]

    for sc in strategy_configs:
        strategy = Strategy(
            author_id=test_users[sc["provider_idx"] % len(test_users)].id,
            provider_id=providers[sc["provider_idx"]].id,
            name=sc["name"],
            description=sc["desc"],
            tags=sc["tags"],
            is_published=True,
            price_type=sc["price_type"],
            price_monthly=sc.get("monthly", 0),
            subscriber_count=random.randint(5, 150),
        )
        db.add(strategy)

    await db.flush()

    # ─── Seed copy trading data for admin ─────────────────
    # Find admin user
    admin = (await db.execute(
        select(User).where(User.role == UserRole.ADMIN)
    )).scalar_one_or_none()

    if admin:
        from app.models.exchange_account import ExchangeAccount, ExchangeName
        from app.models.subscription import Subscription, SubscriptionStatus
        from app.models.order import Order, OrderSide, OrderType, OrderStatus
        from app.models.copy_trade import CopyTrade, CopyTradeStatus
        from app.services.execution import encrypt_value

        # Create demo exchange account for admin
        demo_account = ExchangeAccount(
            user_id=admin.id,
            exchange=ExchangeName.DEMO,
            label="[TEST] Demo Trading Account",
            api_key_encrypted=encrypt_value("demo"),
            api_secret_encrypted=encrypt_value("demo"),
            is_active=True,
            auto_execute=True,
            min_confidence=0.5,
            max_position_pct=5.0,
        )
        db.add(demo_account)
        await db.flush()

        # Subscribe admin to first 4 strategies with auto_execute
        strategies = (await db.execute(
            select(Strategy).where(Strategy.is_published == True).limit(4)
        )).scalars().all()

        for strat in strategies:
            sub = Subscription(
                user_id=admin.id,
                strategy_id=strat.id,
                status=SubscriptionStatus.ACTIVE,
                auto_execute=True,
            )
            db.add(sub)
        await db.flush()

        # Create test orders (simulating past executions)
        closed_signals = (await db.execute(
            select(Signal).where(Signal.status.in_([
                SignalStatus.CLOSED_TP, SignalStatus.CLOSED_SL
            ])).limit(40)
        )).scalars().all()

        copy_trades_created = 0
        for sig in closed_signals:
            # Create order
            is_filled = random.random() > 0.15  # 85% fill rate
            order = Order(
                user_id=admin.id,
                signal_id=sig.id,
                exchange_account_id=demo_account.id,
                exchange_order_id=f"DEMO-TEST-{uuid.uuid4().hex[:8].upper()}",
                exchange="demo",
                symbol=sig.ticker,
                side=OrderSide.BUY if sig.action == SignalAction.BUY else OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=round(random.uniform(0.001, 0.1), 6),
                price=sig.entry_price,
                filled_price=sig.entry_price if is_filled else None,
                filled_quantity=round(random.uniform(0.001, 0.1), 6) if is_filled else None,
                status=OrderStatus.FILLED if is_filled else OrderStatus.FAILED,
                error_message=None if is_filled else "Insufficient balance",
            )
            db.add(order)
            await db.flush()

            # Create copy trade record
            strat_for_copy = strategies[copy_trades_created % len(strategies)] if strategies else None
            if strat_for_copy:
                ct = CopyTrade(
                    subscriber_id=admin.id,
                    strategy_id=strat_for_copy.id,
                    signal_id=sig.id,
                    order_id=order.id,
                    status=CopyTradeStatus.EXECUTED if is_filled else CopyTradeStatus.FAILED,
                    error_message=None if is_filled else "Insufficient balance",
                )
                db.add(ct)
                copy_trades_created += 1

        logger.info(f"Copy trading seed: {len(closed_signals)} orders, {copy_trades_created} copy trades")

    await db.commit()
    logger.info(f"Test data seeded: {len(providers)} providers, {total_signals} signals, {len(strategy_configs)} strategies, {len(test_users)} users")
