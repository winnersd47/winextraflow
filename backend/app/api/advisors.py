"""MT5 Advisors Catalog + MetaApi Connection API.

Provides:
- GET /advisors — catalog of free MQL5 Market expert advisors
- GET /advisors/{id} — advisor details with strategy classification
- POST /advisors/connect-mt5 — connect user's MT5 account via MetaApi
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_premium
from app.database import get_db
from app.models.user import User
from app.services.quant.strategy_classifier import StrategyID, STRATEGY_META

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Advisor Catalog (curated from MQL5 Market) ─────────

ADVISORS_CATALOG = [
    {
        "id": "ea_dark_venus",
        "name": "Dark Venus MT5",
        "author": "Marco Solito",
        "rating": 4.6,
        "reviews": 1414,
        "strategy_id": 3,
        "description_ru": "Скальпинг на основе полос Боллинджера. Высокая частота сделок. Один из самых популярных бесплатных советников — более 100 000 скачиваний.",
        "description_en": "Bollinger Bands scalping with high frequency trading. One of the most popular free EAs — over 100,000 downloads.",
        "tickers": ["EURUSD", "GBPUSD", "USDJPY"],
        "timeframe": "M5",
        "mql5_url": "https://www.mql5.com/ru/market/product/56365",
        "risk": "medium",
        "tags": ["scalping", "bollinger", "forex"],
    },
    {
        "id": "ea_trend_catcher",
        "name": "Trend Catcher EA Pro MT5",
        "author": "Issam Kassas",
        "rating": 4.47,
        "reviews": 32,
        "strategy_id": 1,
        "description_ru": "Комбинация автоматической алгоритмической торговли с ручным контролем трейдера. Оптимизирован для EURUSD на реальных тиках.",
        "description_en": "Combines automatic algorithmic trading with manual trader control. Optimized for EURUSD on real tick data.",
        "tickers": ["EURUSD"],
        "timeframe": "H1",
        "mql5_url": "https://www.mql5.com/ru/market/product/153494",
        "risk": "low",
        "tags": ["trend", "eurusd", "hybrid"],
    },
    {
        "id": "ea_xauusd_5min",
        "name": "XAUUSD 5 Minute",
        "author": "Branislav Bridzik",
        "rating": 4.41,
        "reviews": 111,
        "strategy_id": 4,
        "description_ru": "Скальпинг на золоте (XAUUSD) с реальным рыночным преимуществом. Надёжная и стабильная работа.",
        "description_en": "Gold scalping with genuine market edge. Robust, reliable performance.",
        "tickers": ["XAUUSD"],
        "timeframe": "M5",
        "mql5_url": "https://www.mql5.com/ru/market/product/147332",
        "risk": "medium",
        "tags": ["gold", "scalping", "xauusd"],
    },
    {
        "id": "ea_safe_scalper",
        "name": "SafeScalperPro",
        "author": "Muharrem Rogova",
        "rating": 4.67,
        "reviews": 6,
        "strategy_id": 4,
        "description_ru": "Консервативный пробойный скальпинг. Работает на XAUUSD, XAGUSD и основных форекс-парах (M5/M15).",
        "description_en": "Conservative breakout scalping. Works on XAUUSD, XAGUSD, major forex pairs (M5/M15).",
        "tickers": ["XAUUSD", "XAGUSD", "EURUSD", "GBPUSD"],
        "timeframe": "M5-M15",
        "mql5_url": "https://www.mql5.com/ru/market/product/165581",
        "risk": "low",
        "tags": ["breakout", "scalping", "conservative"],
    },
    {
        "id": "ea_impossible_gold",
        "name": "The Impossible Gold",
        "author": "Paul Raymond Heckles",
        "rating": 4.73,
        "reviews": 11,
        "strategy_id": 4,
        "description_ru": "Пробойный скальпер сессий с многокомпонентной системой оценки. Таймфрейм M5 на XAUUSD.",
        "description_en": "Session breakout scalper with multi-component scoring. XAUUSD M5 timeframe.",
        "tickers": ["XAUUSD"],
        "timeframe": "M5",
        "mql5_url": "https://www.mql5.com/ru/market/product/169680",
        "risk": "medium",
        "tags": ["breakout", "session", "gold", "scoring"],
    },
    {
        "id": "ea_gold_zone",
        "name": "Gold Zone EA",
        "author": "Simon Reger",
        "rating": 4.09,
        "reviews": 35,
        "strategy_id": 3,
        "description_ru": "Торговля от зон спроса и предложения с Price Action. Мультиинструментальная поддержка: золото, форекс, крипто.",
        "description_en": "Supply & demand zones with price action. Multi-instrument: gold, forex, crypto.",
        "tickers": ["XAUUSD", "EURUSD", "BTCUSD"],
        "timeframe": "M15-H1",
        "mql5_url": "https://www.mql5.com/ru/market/product/157473",
        "risk": "medium",
        "tags": ["zones", "price-action", "multi-asset"],
    },
    {
        "id": "ea_range_breakout",
        "name": "RangeBreakout EA MT5",
        "author": "Claye Weight",
        "rating": 4.47,
        "reviews": 58,
        "strategy_id": 4,
        "description_ru": "Пробой утреннего диапазона. Без мартингейла и сетки. Трендовая торговля на пробоях.",
        "description_en": "Morning range breakout trading. No martingale or grid. Trend trading on breakouts.",
        "tickers": ["EURUSD", "GBPUSD", "USDJPY"],
        "timeframe": "M15",
        "mql5_url": "https://www.mql5.com/ru/market/product/113587",
        "risk": "low",
        "tags": ["breakout", "morning", "no-martingale"],
    },
    {
        "id": "ea_supertrend_g5",
        "name": "Supertrend G5",
        "author": "Van Minh Nguyen",
        "rating": 4.83,
        "reviews": 23,
        "strategy_id": 1,
        "description_ru": "Трендовая система оптимизированная для XAUUSD M5. Работает на золоте, крипто и основных парах.",
        "description_en": "Trend-following system optimized for XAUUSD M5. Works on gold, crypto, and major pairs.",
        "tickers": ["XAUUSD", "BTCUSD", "EURUSD"],
        "timeframe": "M5",
        "mql5_url": "https://www.mql5.com/ru/market/product/144058",
        "risk": "medium",
        "tags": ["trend", "supertrend", "gold", "crypto"],
    },
    {
        "id": "ea_grid_scalper_ma",
        "name": "Grid Scalper MA MT5",
        "author": "Allan Munene Mutiiria",
        "rating": 4.46,
        "reviews": 74,
        "strategy_id": 5,
        "description_ru": "Динамическая сетка с сигналами от скользящих средних или пробоя структуры. Закрытие по взвешенному безубытку.",
        "description_en": "Dynamic grid engine with MA or break-of-structure signals. Volume-weighted breakeven closing.",
        "tickers": ["XAUUSD", "EURUSD", "GBPUSD"],
        "timeframe": "M5-M15",
        "mql5_url": "https://www.mql5.com/ru/market/product/133466",
        "risk": "high",
        "tags": ["grid", "ma", "structure"],
    },
    {
        "id": "ea_matrader_ai",
        "name": "MATrader AI MT5",
        "author": "Marc Albrecht Schmid",
        "rating": 4.36,
        "reviews": 14,
        "strategy_id": 7,
        "description_ru": "AI-система для торговли золотом. 4 года тестирования. Машинное обучение для определения точек входа.",
        "description_en": "AI-based gold trading system. Four-year testing history. Machine learning for entry points.",
        "tickers": ["XAUUSD"],
        "timeframe": "H1",
        "mql5_url": "https://www.mql5.com/ru/market/product/165635",
        "risk": "medium",
        "tags": ["ai", "ml", "gold"],
    },
    {
        "id": "ea_gold_ict",
        "name": "Gold ICT OrderBlock Expert",
        "author": "Charles Fournel",
        "rating": 4.33,
        "reviews": 36,
        "strategy_id": 4,
        "description_ru": "Методология ICT: торговля от ордер-блоков и структурных сдвигов. XAUUSD M6.",
        "description_en": "ICT methodology using order blocks and structure shifts. XAUUSD M6.",
        "tickers": ["XAUUSD"],
        "timeframe": "M6",
        "mql5_url": "https://www.mql5.com/ru/market/product/143851",
        "risk": "medium",
        "tags": ["ict", "orderblock", "structure", "gold"],
    },
    {
        "id": "ea_fibo_scalping",
        "name": "Fibo Scalping Strategy",
        "author": "Komila Safarova",
        "rating": 4.2,
        "reviews": 5,
        "strategy_id": 2,
        "description_ru": "Скальпинг по уровням Фибоначчи. Открывает несколько одновременных позиций на покупку и продажу.",
        "description_en": "Fibonacci retracement scalping. Multiple simultaneous buy/sell positions.",
        "tickers": ["EURUSD", "GBPUSD"],
        "timeframe": "M15",
        "mql5_url": "https://www.mql5.com/ru/market/product/139014",
        "risk": "medium",
        "tags": ["fibonacci", "scalping", "multi-position"],
    },
]

STRATEGY_NAMES_RU = {1: "Тренд", 2: "Возврат к среднему", 3: "Диапазон", 4: "Пробой", 5: "Мульти-индикатор", 6: "Статистический", 7: "ML/AI"}
STRATEGY_NAMES_EN = {1: "Trend Following", 2: "Mean Reversion", 3: "Range", 4: "Breakout", 5: "Multi-Indicator", 6: "Statistical", 7: "ML/AI"}
RISK_RU = {"low": "Низкий", "medium": "Средний", "high": "Высокий"}


@router.get("")
async def list_advisors(user: User = Depends(get_current_user)):
    """List all MT5 advisors in catalog with strategy classification."""
    return {
        "advisors": [
            {
                **ea,
                "strategy_name_ru": STRATEGY_NAMES_RU.get(ea["strategy_id"], "?"),
                "strategy_name_en": STRATEGY_NAMES_EN.get(ea["strategy_id"], "?"),
                "risk_ru": RISK_RU.get(ea["risk"], ea["risk"]),
            }
            for ea in ADVISORS_CATALOG
        ],
        "total": len(ADVISORS_CATALOG),
    }


@router.get("/{advisor_id}")
async def get_advisor(advisor_id: str, user: User = Depends(get_current_user)):
    """Get advisor details."""
    ea = next((a for a in ADVISORS_CATALOG if a["id"] == advisor_id), None)
    if not ea:
        raise HTTPException(404, "Advisor not found")
    return {
        **ea,
        "strategy_name_ru": STRATEGY_NAMES_RU.get(ea["strategy_id"], "?"),
        "strategy_name_en": STRATEGY_NAMES_EN.get(ea["strategy_id"], "?"),
        "risk_ru": RISK_RU.get(ea["risk"], ea["risk"]),
        "connect_instructions_ru": (
            "1. Скачайте советник на MQL5 Market (бесплатно)\n"
            "2. Установите в MetaTrader 5\n"
            "3. Подключите MT5 счёт к WinExtraFlow через MetaApi\n"
            "4. Сигналы от советника будут автоматически появляться на платформе"
        ),
        "connect_instructions_en": (
            "1. Download advisor from MQL5 Market (free)\n"
            "2. Install in MetaTrader 5\n"
            "3. Connect MT5 account to WinExtraFlow via MetaApi\n"
            "4. Advisor signals will automatically appear on the platform"
        ),
    }


class MT5ConnectRequest(BaseModel):
    metaapi_token: str
    account_label: str = "My MT5"


@router.post("/connect-mt5")
async def connect_mt5_account(
    data: MT5ConnectRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_premium),
):
    """Connect user's MT5 account via MetaApi token (Premium required).

    The MetaApi token allows the platform to:
    - Read account balance and positions
    - Execute trades from platform signals
    - Sync advisor signals to the platform
    """
    from app.models.exchange_account import ExchangeAccount, ExchangeName
    from app.services.execution import encrypt_value

    account = ExchangeAccount(
        user_id=user.id,
        exchange=ExchangeName.METATRADER5,
        label=data.account_label,
        api_key_encrypted=encrypt_value(data.metaapi_token),
        api_secret_encrypted=encrypt_value("metaapi"),
        is_active=True,
        auto_execute=False,
        min_confidence=0.6,
        max_position_pct=3.0,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)

    logger.info(f"MT5 account connected via MetaApi: {data.account_label} for user {user.username}")

    return {
        "status": "connected",
        "account_id": str(account.id),
        "label": data.account_label,
        "exchange": "metatrader5",
        "message_ru": "MT5 счёт подключён. Перейдите в Исполнение для настройки авто-торговли.",
        "message_en": "MT5 account connected. Go to Execution to set up auto-trading.",
    }
