"""TradingView Community Strategies Catalog — curated from TradingView scripts.

Each strategy classified by Strategy ID and evaluated by Evolutionary Architecture.
Provides ready-to-use webhook templates for MOEX and global markets.
"""

import logging

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.services.quant.strategy_classifier import StrategyID, STRATEGY_META

logger = logging.getLogger(__name__)
router = APIRouter()

TV_STRATEGIES = [
    # ─── Regime / Trend ──────────────────────────
    {"id": "tv_regime_exec", "name": "Regime Execution Strategy [JOAT]", "author": "officialjackofalltrades",
     "likes": 7, "strategy_id": 1, "risk": "medium",
     "description_ru": "Мультиголосовая система: прогнозный bias + канальное состояние + ATR риск-менеджмент. Фильтр режима рынка.",
     "description_en": "Multi-vote entry: forecast bias + channel state + ATR risk management. Market regime filter.",
     "tickers": ["MOEX", "FOREX", "CRYPTO"], "timeframe": "1H-4H",
     "tv_url": "https://ru.tradingview.com/script/regime-execution-strategy/",
     "webhook_template": '{"ticker":"{{ticker}}","action":"{{strategy.order.action}}","price":{{close}}}',
     "tags": ["regime", "trend", "atr", "multi-vote"], "moex_compatible": True},

    {"id": "tv_quant_synthesis", "name": "Quant Synthesis Strategy [JOAT]", "author": "officialjackofalltrades",
     "likes": 9, "strategy_id": 7, "risk": "medium",
     "description_ru": "Определение режима + HTF bias + исполнение по сессиям. Квант-подход.",
     "description_en": "Regime detection, HTF bias, session-based execution. Quant approach.",
     "tickers": ["MOEX", "FOREX", "CRYPTO"], "timeframe": "1H",
     "tv_url": "https://ru.tradingview.com/script/quant-synthesis-strategy/",
     "webhook_template": '{"ticker":"{{ticker}}","action":"{{strategy.order.action}}","price":{{close}}}',
     "tags": ["quant", "regime", "htf", "session"], "moex_compatible": True},

    {"id": "tv_kalman_trend", "name": "Kalman Trend Levels Strategy", "author": "shitholed",
     "likes": 5, "strategy_id": 1, "risk": "low",
     "description_ru": "Двойные фильтры Калмана с динамическим позиционированием. Метрики доходности в реальном времени.",
     "description_en": "Dual Kalman filters with dynamic position sizing and annualized performance metrics.",
     "tickers": ["MOEX", "FOREX"], "timeframe": "1D",
     "tv_url": "https://ru.tradingview.com/script/kalman-trend-levels/",
     "webhook_template": '{"ticker":"{{ticker}}","action":"{{strategy.order.action}}","price":{{close}}}',
     "tags": ["kalman", "trend", "dynamic-sizing", "math"], "moex_compatible": True},

    # ─── Breakout ────────────────────────────────
    {"id": "tv_ict_session", "name": "ICT Session Breakout v3", "author": "Burdiga84",
     "likes": 27, "strategy_id": 4, "risk": "medium",
     "description_ru": "Пробой-возврат-ретест последовательность с риск-менеджментом по заполнению. Внутридневная торговля.",
     "description_en": "Break-reentry-retest sequence with fill-based risk management for intraday trading.",
     "tickers": ["FOREX", "CRYPTO", "MOEX"], "timeframe": "M15-1H",
     "tv_url": "https://ru.tradingview.com/script/ict-session-breakout/",
     "webhook_template": '{"ticker":"{{ticker}}","action":"{{strategy.order.action}}","price":{{close}},"take_profit":{{strategy.order.price}},"stop_loss":null}',
     "tags": ["ict", "breakout", "session", "intraday"], "moex_compatible": True},

    {"id": "tv_liquidity_zones", "name": "Liquidity Entry Zones 2.0", "author": "evrinb7716",
     "likes": 11, "strategy_id": 4, "risk": "high",
     "description_ru": "Зоны ликвидности для входа с высоким R:R. Свинг-торговля.",
     "description_en": "Liquidity zones for high R:R entries. Swing trading.",
     "tickers": ["FOREX", "CRYPTO"], "timeframe": "1H-4H",
     "tv_url": "https://ru.tradingview.com/script/liquidity-entry-zones/",
     "webhook_template": '{"ticker":"{{ticker}}","action":"{{strategy.order.action}}","price":{{close}}}',
     "tags": ["liquidity", "breakout", "swing", "high-rr"], "moex_compatible": False},

    {"id": "tv_sr_scalper", "name": "SR Chart Pattern Scalper V1", "author": "anthony_eglmada",
     "likes": 5, "strategy_id": 4, "risk": "medium",
     "description_ru": "Пивот-подтверждение поддержки/сопротивления + распознавание графических паттернов.",
     "description_en": "Confirmed pivot S/R with chart pattern detection.",
     "tickers": ["FOREX", "CRYPTO", "MOEX"], "timeframe": "M15-1H",
     "tv_url": "https://ru.tradingview.com/script/sr-chart-pattern-scalper/",
     "webhook_template": '{"ticker":"{{ticker}}","action":"{{strategy.order.action}}","price":{{close}}}',
     "tags": ["support-resistance", "patterns", "scalping"], "moex_compatible": True},

    # ─── Mean Reversion ──────────────────────────
    {"id": "tv_mean_rev_200ma", "name": "Mean Reversion at 200MA", "author": "josephgregory8976",
     "likes": 6, "strategy_id": 2, "risk": "low",
     "description_ru": "Возврат к среднему от 200-EMA. Оптимизирован для S&P фьючерсов на 30-мин графике.",
     "description_en": "EMA-based mean reversion targeting S&P futures on 30-minute charts.",
     "tickers": ["SPX500", "MOEX"], "timeframe": "M30",
     "tv_url": "https://ru.tradingview.com/script/mean-reversion-200ma/",
     "webhook_template": '{"ticker":"{{ticker}}","action":"{{strategy.order.action}}","price":{{close}}}',
     "tags": ["mean-reversion", "ema", "200ma", "futures"], "moex_compatible": True},

    # ─── Multi-Indicator ─────────────────────────
    {"id": "tv_zeta9", "name": "ZETA9 v6", "author": "demeth5D",
     "likes": 24, "strategy_id": 5, "risk": "medium",
     "description_ru": "SMC + Price Action. Оптимизирован для EURUSD и XAUUSD.",
     "description_en": "SMC and price action strategy for EURUSD and XAUUSD.",
     "tickers": ["EURUSD", "XAUUSD"], "timeframe": "1H",
     "tv_url": "https://ru.tradingview.com/script/zeta9/",
     "webhook_template": '{"ticker":"{{ticker}}","action":"{{strategy.order.action}}","price":{{close}}}',
     "tags": ["smc", "price-action", "forex", "gold"], "moex_compatible": False},

    {"id": "tv_velox_mtf", "name": "Velox MTF + Marubozu Filter", "author": "rakshithradhakrishna",
     "likes": 3, "strategy_id": 5, "risk": "medium",
     "description_ru": "Мульти-таймфрейм моментум с фильтром Марубозу. 70-80% точность в трендовых рынках.",
     "description_en": "Multi-timeframe momentum with Marubozu filter. 70-80% accuracy in trending markets.",
     "tickers": ["MOEX", "FOREX", "CRYPTO"], "timeframe": "1H-4H",
     "tv_url": "https://ru.tradingview.com/script/velox-mtf/",
     "webhook_template": '{"ticker":"{{ticker}}","action":"{{strategy.order.action}}","price":{{close}}}',
     "tags": ["multi-timeframe", "momentum", "marubozu"], "moex_compatible": True},

    {"id": "tv_universal_3sl3tp", "name": "Universal 3 SL + 3 TP + RSI + ATR", "author": "debonairTruffl17165",
     "likes": 2, "strategy_id": 5, "risk": "low",
     "description_ru": "Универсальная стратегия: 1 стоп-лосс + 3 частичных тейк-профита. RSI + ATR фильтры.",
     "description_en": "Universal strategy with single stop loss and three partial take profits. RSI + ATR.",
     "tickers": ["MOEX", "FOREX", "CRYPTO"], "timeframe": "Any",
     "tv_url": "https://ru.tradingview.com/script/universal-3sl-3tp/",
     "webhook_template": '{"ticker":"{{ticker}}","action":"{{strategy.order.action}}","price":{{close}},"stop_loss":{{strategy.order.price}}}',
     "tags": ["universal", "partial-tp", "rsi", "atr"], "moex_compatible": True},

    {"id": "tv_smc_emas", "name": "Ultimate SMC + EMAs Day Trading", "author": "Remarkablefreddy",
     "likes": 2, "strategy_id": 5, "risk": "medium",
     "description_ru": "SMC: ордер-блоки + уровни Фибоначчи + пулы ликвидности HTF. Дейтрейдинг.",
     "description_en": "SMC order blocks + Fibonacci + HTF liquidity pools. Day trading.",
     "tickers": ["FOREX", "CRYPTO"], "timeframe": "M15-1H",
     "tv_url": "https://ru.tradingview.com/script/smc-emas-day-trading/",
     "webhook_template": '{"ticker":"{{ticker}}","action":"{{strategy.order.action}}","price":{{close}}}',
     "tags": ["smc", "ema", "fibonacci", "liquidity"], "moex_compatible": False},

    # ─── Gold / AI ───────────────────────────────
    {"id": "tv_gold_ai", "name": "GOLD AI Strategy v2.0", "author": "francescodimichele",
     "likes": 5, "strategy_id": 7, "risk": "medium",
     "description_ru": "AI-стратегия для золота оптимизированная под H1 таймфрейм.",
     "description_en": "AI strategy optimized for H1 timeframe gold trading.",
     "tickers": ["XAUUSD"], "timeframe": "1H",
     "tv_url": "https://ru.tradingview.com/script/gold-ai-strategy/",
     "webhook_template": '{"ticker":"XAUUSD","action":"{{strategy.order.action}}","price":{{close}}}',
     "tags": ["ai", "gold", "h1"], "moex_compatible": False},

    # ─── Range / Grid ────────────────────────────
    {"id": "tv_donchian", "name": "Donchian Channels Breakout", "author": "Khanhtq26",
     "likes": 6, "strategy_id": 4, "risk": "medium",
     "description_ru": "Пробой каналов Дончиана. Адаптирован для индексных фьючерсов.",
     "description_en": "Donchian channel breakout. Designed for index futures.",
     "tickers": ["SPX500", "NAS100", "MOEX"], "timeframe": "1D",
     "tv_url": "https://ru.tradingview.com/script/donchian-channels/",
     "webhook_template": '{"ticker":"{{ticker}}","action":"{{strategy.order.action}}","price":{{close}}}',
     "tags": ["donchian", "breakout", "indices", "futures"], "moex_compatible": True},

    {"id": "tv_opening_range", "name": "Opening Range UltraPro Max+", "author": "frank_quebec",
     "likes": 16, "strategy_id": 4, "risk": "medium",
     "description_ru": "Классическая стратегия открытия диапазона. Двойная конфигурация.",
     "description_en": "Traditional opening range strategy with dual configurations.",
     "tickers": ["MOEX", "FOREX"], "timeframe": "M15-1H",
     "tv_url": "https://ru.tradingview.com/script/opening-range-ultrapro/",
     "webhook_template": '{"ticker":"{{ticker}}","action":"{{strategy.order.action}}","price":{{close}}}',
     "tags": ["opening-range", "breakout", "dual-config"], "moex_compatible": True},

    # ─── Crypto specific ─────────────────────────
    {"id": "tv_supertrend_bb", "name": "Crypto Algo: SuperTrend + Bollinger", "author": "smvdtravelsolutions",
     "likes": 2, "strategy_id": 1, "risk": "high",
     "description_ru": "Мульти-таймфрейм SuperTrend с фильтром волатильности Боллинджера для крипто.",
     "description_en": "Multi-timeframe SuperTrend with Bollinger Bands volatility filter for crypto.",
     "tickers": ["BTCUSDT", "ETHUSDT"], "timeframe": "1H",
     "tv_url": "https://ru.tradingview.com/script/crypto-algo-supertrend/",
     "webhook_template": '{"ticker":"{{ticker}}","action":"{{strategy.order.action}}","price":{{close}}}',
     "tags": ["supertrend", "bollinger", "crypto", "multi-tf"], "moex_compatible": False},

    {"id": "tv_ether_grid", "name": "Ether Vault Grid — ETH/USDT", "author": "3Commas",
     "likes": 3, "strategy_id": 3, "risk": "medium",
     "description_ru": "Статическая геометрическая сетка для бокового ETH. Grid-стратегия.",
     "description_en": "Static geometric grid for range-bound ETH consolidation.",
     "tickers": ["ETHUSDT"], "timeframe": "1H",
     "tv_url": "https://ru.tradingview.com/script/ether-vault-grid/",
     "webhook_template": '{"ticker":"ETHUSDT","action":"{{strategy.order.action}}","price":{{close}}}',
     "tags": ["grid", "eth", "range", "3commas"], "moex_compatible": False},
]

STRATEGY_NAMES_RU = {1: "Тренд", 2: "Возврат к среднему", 3: "Диапазон", 4: "Пробой", 5: "Мульти-индикатор", 6: "Статистический", 7: "ML/AI"}
STRATEGY_NAMES_EN = {1: "Trend", 2: "Mean Reversion", 3: "Range", 4: "Breakout", 5: "Multi-Indicator", 6: "Statistical", 7: "ML/AI"}
RISK_RU = {"low": "Низкий", "medium": "Средний", "high": "Высокий"}


@router.get("")
async def list_tv_strategies(user: User = Depends(get_current_user)):
    """List curated TradingView strategies with evolutionary classification."""
    return {
        "strategies": [
            {
                **s,
                "strategy_name_ru": STRATEGY_NAMES_RU.get(s["strategy_id"], "?"),
                "strategy_name_en": STRATEGY_NAMES_EN.get(s["strategy_id"], "?"),
                "risk_ru": RISK_RU.get(s["risk"], s["risk"]),
            }
            for s in TV_STRATEGIES
        ],
        "total": len(TV_STRATEGIES),
        "moex_count": sum(1 for s in TV_STRATEGIES if s.get("moex_compatible")),
    }
