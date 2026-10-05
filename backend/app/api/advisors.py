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
#
# `rating` and `reviews` below are a hand-copied snapshot from mql5.com, not live
# data. They were taken once, on the date in STATS_AS_OF, and never refreshed —
# meanwhile the marketplace page sorts by them by default, so a stale number decides
# what a user sees first. Every response now carries STATS_AS_OF and a notice so the
# UI can date them; an undated rating presented as current is the same defect as the
# fabricated subscriber counts removed from api/strategies.py.
#
# To refresh: update the numbers and move STATS_AS_OF. Do not leave one without the
# other.
STATS_AS_OF = "2026-05-19"

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
    # ─── Batch 2: Top popular advisors ──────
    {
        "id": "ea_athena_scalping",
        "name": "Quantitative Athena Scalping",
        "author": "Titouan Cadoux",
        "rating": 4.72, "reviews": 25, "strategy_id": 4,
        "description_ru": "Гиперскальпинг с множественными отложенными ордерами и быстрой фиксацией прибыли. Без стоп-лосса — строгий мани-менеджмент обязателен.",
        "description_en": "Hyper-scalping with multiple pending positions and quick profit-taking. No stop loss — strict money management required.",
        "tickers": ["XAUUSD"], "timeframe": "M5",
        "mql5_url": "https://www.mql5.com/ru/market/product/130334",
        "risk": "high", "tags": ["scalping", "gold", "pending-orders"],
    },
    {
        "id": "ea_stratos_goldwind",
        "name": "Stratos Goldwind MT5",
        "author": "Michela Russo",
        "rating": 4.68, "reviews": 276, "strategy_id": 5,
        "description_ru": "Инновационный торговый робот для золота с 10 разными стратегиями в одном советнике. Диверсификация подходов.",
        "description_en": "Innovative gold trading robot with 10 diverse strategies in one EA. Approach diversification.",
        "tickers": ["XAUUSD"], "timeframe": "M5",
        "mql5_url": "https://www.mql5.com/ru/market/product/117951",
        "risk": "medium", "tags": ["gold", "multi-strategy", "diversified"],
    },
    {
        "id": "ea_aurum_ra",
        "name": "Aurum Ra Gold EA",
        "author": "Akapop Srisang",
        "rating": 4.64, "reviews": 25, "strategy_id": 4,
        "description_ru": "Чистая пробойная система без сетки и мартингейла. Стоп-лосс на каждой сделке. Консервативный подход к золоту.",
        "description_en": "Pure breakout system without grid or martingale. Stop loss on every trade. Conservative gold approach.",
        "tickers": ["XAUUSD"], "timeframe": "M1-M5",
        "mql5_url": "https://www.mql5.com/ru/market/product/149983",
        "risk": "low", "tags": ["breakout", "gold", "no-martingale", "conservative"],
    },
    {
        "id": "ea_cannon_trend",
        "name": "Cannon Trend",
        "author": "Tan Au Phuong",
        "rating": 4.37, "reviews": 63, "strategy_id": 1,
        "description_ru": "5 режимов торговли, исключающих эмоциональные решения. Правила-основанное исполнение для золота.",
        "description_en": "Five trading strategy modes removing emotional decisions through rule-based execution.",
        "tickers": ["XAUUSD"], "timeframe": "Multi",
        "mql5_url": "https://www.mql5.com/ru/market/product/129308",
        "risk": "medium", "tags": ["trend", "gold", "multi-mode", "rule-based"],
    },
    {
        "id": "ea_apex_origin",
        "name": "Apex Origin",
        "author": "Yi Hsiu Tsai",
        "rating": 4.8, "reviews": 15, "strategy_id": 6,
        "description_ru": "Алгоритмическая система на основе математики и статистики со строгим контролем рисков. Золото и BTC.",
        "description_en": "Algorithmic system emphasizing mathematics and statistics with strict risk control. Gold and BTC.",
        "tickers": ["XAUUSD", "BTCUSD"], "timeframe": "Multi",
        "mql5_url": "https://www.mql5.com/ru/market/product/166552",
        "risk": "low", "tags": ["statistical", "math", "gold", "btc", "risk-control"],
    },
    {
        "id": "ea_cyber_pulse",
        "name": "Cyber Pulse",
        "author": "Marco Brugali",
        "rating": 4.35, "reviews": 17, "strategy_id": 7,
        "description_ru": "3-5 сделок в неделю. Комбинация машинного обучения с Price Action стратегиями. GBPUSD, XAUUSD, USDJPY.",
        "description_en": "3-5 trades weekly combining machine learning with price action strategies.",
        "tickers": ["GBPUSD", "XAUUSD", "USDJPY"], "timeframe": "D1",
        "mql5_url": "https://www.mql5.com/ru/market/product/112509",
        "risk": "low", "tags": ["ai", "ml", "price-action", "weekly"],
    },
    {
        "id": "ea_surfer",
        "name": "Surfer EA",
        "author": "Eugen-Alexandru Zibileanu",
        "rating": 5.0, "reviews": 8, "strategy_id": 2,
        "description_ru": "Сетка на основе RSI с подтверждением тренда. Рейтинг 5.0/5. Форекс-пары.",
        "description_en": "RSI-based grid with trend confirmation mechanics. Perfect 5.0/5 rating. Forex pairs.",
        "tickers": ["EURUSD", "GBPUSD"], "timeframe": "M5",
        "mql5_url": "https://www.mql5.com/ru/market/product/175579",
        "risk": "high", "tags": ["grid", "rsi", "forex"],
    },
    {
        "id": "ea_tomgoodcar",
        "name": "Tomgoodcar Anglosaxon",
        "author": "Tanakon Khotmitr",
        "rating": 4.79, "reviews": 14, "strategy_id": 1,
        "description_ru": "Многоуровневый подход: двойные EMA для определения тренда + возврат к среднему. Мультиинструментальный.",
        "description_en": "Multi-layered approach using dual EMAs for trend identification and mean-reversion.",
        "tickers": ["EURUSD", "GBPUSD", "XAUUSD"], "timeframe": "H1",
        "mql5_url": "https://www.mql5.com/ru/market/product/173937",
        "risk": "medium", "tags": ["trend", "ema", "mean-reversion", "multi-asset"],
    },
    {
        "id": "ea_universal_breakout",
        "name": "Universal Breakout MT5",
        "author": "Sergey Ermolov",
        "rating": 4.23, "reviews": 48, "strategy_id": 4,
        "description_ru": "Пробой диапазона с настраиваемыми временными интервалами. Автоопределение уровней. Универсальный.",
        "description_en": "Range breakout with customizable timeframe intervals. Auto level detection. Universal.",
        "tickers": ["EURUSD", "GBPUSD", "XAUUSD"], "timeframe": "Custom",
        "mql5_url": "https://www.mql5.com/ru/market/product/93732",
        "risk": "medium", "tags": ["breakout", "range", "universal", "customizable"],
    },
    {
        "id": "ea_sr_breakout",
        "name": "Support and Resistance Breakout MT5",
        "author": "Peter Mueller",
        "rating": 5.0, "reviews": 6, "strategy_id": 4,
        "description_ru": "Объективное определение поддержки/сопротивления через свечной анализ. Рейтинг 5.0/5.",
        "description_en": "Objective S/R identification via candle analysis. Perfect 5.0/5 rating.",
        "tickers": ["EURUSD", "GBPUSD", "XAUUSD"], "timeframe": "M5-H1",
        "mql5_url": "https://www.mql5.com/ru/market/product/164550",
        "risk": "low", "tags": ["support-resistance", "breakout", "candle-analysis"],
    },
    {
        "id": "ea_gold_candle_bot",
        "name": "Gold Candle Bot",
        "author": "Maksim Kononenko",
        "rating": 4.61, "reviews": 36, "strategy_id": 5,
        "description_ru": "Торговля по паттернам крупных и малых свечей на XAUUSD. Мульти-таймфрейм анализ.",
        "description_en": "Trades large-to-small candle patterns on XAUUSD across multiple timeframes.",
        "tickers": ["XAUUSD"], "timeframe": "M1-M30",
        "mql5_url": "https://www.mql5.com/ru/market/product/129105",
        "risk": "medium", "tags": ["candle-patterns", "gold", "multi-timeframe"],
    },
    {
        "id": "ea_stratos_zephyr",
        "name": "Stratos Zephyr MT5",
        "author": "Michela Russo",
        "rating": 4.76, "reviews": 190, "strategy_id": 2,
        "description_ru": "RSI-робот для форекса с 10 стратегиями. 190 отзывов. Разнообразные стили торговли в одном советнике.",
        "description_en": "RSI-based forex robot with 10 strategies. 190 reviews. Diverse trading styles in one EA.",
        "tickers": ["EURUSD", "GBPUSD", "USDJPY"], "timeframe": "Multi",
        "mql5_url": "https://www.mql5.com/ru/market/product/112907",
        "risk": "medium", "tags": ["rsi", "forex", "multi-strategy", "diversified"],
    },
    # ─── Paid advisors (top rated from MQL5 Market) ────
    {"id": "ea_quantum_athena", "name": "Quantum Athena", "author": "Bogdan Ion Puscasu", "rating": 5.0, "reviews": 26, "strategy_id": 7,
     "description_ru": "Торговля золотом с точностью, выкованной опытом. Один из топовых платных советников.", "description_en": "Gold trading with precision forged from experience. Top-rated paid EA.",
     "tickers": ["XAUUSD"], "timeframe": "M15", "mql5_url": "https://www.mql5.com/ru/market/product/173058", "risk": "medium", "tags": ["gold", "ai", "premium"], "price_usd": 999.99},
    {"id": "ea_price_action_robot", "name": "Price Action Robot MT5", "author": "MQL TOOLS SL", "rating": 5.0, "reviews": 3, "strategy_id": 3,
     "description_ru": "Чистый Price Action без индикаторов и сеток. Анализирует структуру свечей.", "description_en": "Pure price action analysis without indicators or grids.",
     "tickers": ["XAUUSD"], "timeframe": "M5", "mql5_url": "https://www.mql5.com/ru/market/product/172319", "risk": "low", "tags": ["price-action", "gold", "no-indicators"], "price_usd": 599},
    {"id": "ea_sentinel", "name": "Sentinel MT5", "author": "Luca Barone", "rating": 5.0, "reviews": 37, "strategy_id": 5,
     "description_ru": "EA с фокусом на сохранение капитала. Приоритет — контроль рисков, а не максимальная прибыль.", "description_en": "Risk-focused EA prioritizing capital preservation over maximum profit.",
     "tickers": ["XAUUSD"], "timeframe": "Multi", "mql5_url": "https://www.mql5.com/ru/market/product/160633", "risk": "low", "tags": ["risk-control", "gold", "capital-preservation"], "price_usd": 299},
    {"id": "ea_legendary_multi", "name": "EA Legendary Multi Strategy", "author": "Vitali Vasilenka", "rating": 5.0, "reviews": 5, "strategy_id": 5,
     "description_ru": "12 независимых стратегий с коллективным интеллектом в одном советнике.", "description_en": "Twelve independent strategies with collective intelligence.",
     "tickers": ["XAUUSD", "EURUSD"], "timeframe": "Multi", "mql5_url": "https://www.mql5.com/ru/market/product/170372", "risk": "medium", "tags": ["multi-strategy", "collective", "diversified"], "price_usd": 249},
    {"id": "ea_gold_opr_killer", "name": "Gold OPR Killer", "author": "Ilies Zalegh", "rating": 5.0, "reviews": 5, "strategy_id": 4,
     "description_ru": "Профессиональный скальпинг золота на рыночных ускорениях.", "description_en": "Professional gold scalping targeting market accelerations.",
     "tickers": ["XAUUSD"], "timeframe": "M5", "mql5_url": "https://www.mql5.com/ru/market/product/177265", "risk": "medium", "tags": ["scalping", "gold", "acceleration"], "price_usd": 249},
    {"id": "ea_ultimate_breakout", "name": "Ultimate Breakout System", "author": "Profalgo Limited", "rating": 5.0, "reviews": 35, "strategy_id": 4,
     "description_ru": "Пакет из 100+ пробойных стратегий. Один из самых полных наборов для трейдера.", "description_en": "Package includes 100+ breakout strategies. One of the most complete sets.",
     "tickers": ["EURUSD", "GBPUSD", "XAUUSD"], "timeframe": "Multi", "mql5_url": "https://www.mql5.com/ru/market/product/133653", "risk": "medium", "tags": ["breakout", "package", "100-strategies"], "price_usd": 1499},
    {"id": "ea_quantum_king", "name": "Quantum King EA", "author": "Bogdan Ion Puscasu", "rating": 5.0, "reviews": 180, "strategy_id": 7,
     "description_ru": "Интеллектуальная мультивалютная система. 180 отзывов, рейтинг 5.0.", "description_en": "Intelligent multi-pair trading system. 180 reviews, 5.0 rating.",
     "tickers": ["EURUSD", "GBPUSD", "XAUUSD"], "timeframe": "Multi", "mql5_url": "https://www.mql5.com/ru/market/product/152162", "risk": "medium", "tags": ["ai", "multi-pair", "quantum"], "price_usd": 649.99},
    {"id": "ea_full_throttle", "name": "Full Throttle DMX", "author": "Stanislav Tomilov", "rating": 5.0, "reviews": 9, "strategy_id": 5,
     "description_ru": "Мультивалютная система с 10 независимыми стратегиями. EUR/USD, AUD/USD, NZD/USD.", "description_en": "Multi-currency system with 10 independent strategies.",
     "tickers": ["EURUSD", "AUDUSD", "NZDUSD"], "timeframe": "Multi", "mql5_url": "https://www.mql5.com/ru/market/product/167600", "risk": "medium", "tags": ["multi-currency", "10-strategies", "forex"], "price_usd": 699},
    {"id": "ea_nano_machine", "name": "Nano Machine", "author": "William Brandon Autry", "rating": 5.0, "reviews": 11, "strategy_id": 7,
     "description_ru": "AI-система запоминающая паттерны откатов. Машинное обучение для точных входов.", "description_en": "AI system remembering pullback patterns. Machine learning for precise entries.",
     "tickers": ["XAUUSD", "EURUSD"], "timeframe": "Multi", "mql5_url": "https://www.mql5.com/ru/market/product/156448", "risk": "medium", "tags": ["ai", "ml", "pullback", "memory"], "price_usd": 497.37},
    {"id": "ea_quantum_queen", "name": "Quantum Queen MT5", "author": "Bogdan Ion Puscasu", "rating": 4.97, "reviews": 589, "strategy_id": 7,
     "description_ru": "Специализированный советник для золота. 589 отзывов, 20+ месяцев реальных результатов.", "description_en": "Specialized gold advisor with 589 reviews and 20+ months live results.",
     "tickers": ["XAUUSD"], "timeframe": "Multi", "mql5_url": "https://www.mql5.com/ru/market/product/118805", "risk": "medium", "tags": ["gold", "quantum", "proven"], "price_usd": 1999.99},
    {"id": "ea_bb_return", "name": "BB Return MT5", "author": "Leonid Arkhipov", "rating": 4.99, "reviews": 101, "strategy_id": 2,
     "description_ru": "Разворотная стратегия на полосах Боллинджера для золота. 101 отзыв.", "description_en": "Bollinger Bands reversal strategy for gold. 101 reviews.",
     "tickers": ["XAUUSD"], "timeframe": "Multi", "mql5_url": "https://www.mql5.com/ru/market/product/162150", "risk": "medium", "tags": ["bollinger", "reversal", "gold"], "price_usd": 649},
    {"id": "ea_game_changer", "name": "Game Changer MT5", "author": "Vasiliy Strukov", "rating": 4.94, "reviews": 32, "strategy_id": 1,
     "description_ru": "Трендовая система на основе индикаторных сигналов. Доступная цена — $50.", "description_en": "Trend-following system based on indicator signals. Affordable at $50.",
     "tickers": ["EURUSD", "GBPUSD", "XAUUSD"], "timeframe": "Any", "mql5_url": "https://www.mql5.com/ru/market/product/158111", "risk": "low", "tags": ["trend", "affordable", "indicators"], "price_usd": 50},
    {"id": "ea_aiq", "name": "AiQ", "author": "William Brandon Autry", "rating": 4.87, "reviews": 38, "strategy_id": 7,
     "description_ru": "Продвинутый AI с отложенными ордерами для импульсного расширения. Самый дорогой советник.", "description_en": "Advanced AI with pending orders for impulse expansion. Most expensive EA.",
     "tickers": ["XAUUSD", "EURUSD", "GBPUSD"], "timeframe": "Multi", "mql5_url": "https://www.mql5.com/ru/market/product/134329", "risk": "medium", "tags": ["ai", "impulse", "advanced"], "price_usd": 2237.97},
    {"id": "ea_aurum_ai", "name": "Aurum AI MT5", "author": "Leonid Arkhipov", "rating": 4.87, "reviews": 45, "strategy_id": 7,
     "description_ru": "Золотая AI-система с годом тестирования. Обновление декабрь 2025.", "description_en": "Year-tested gold AI system with December 2025 update.",
     "tickers": ["XAUUSD"], "timeframe": "Multi", "mql5_url": "https://www.mql5.com/ru/market/product/126802", "risk": "medium", "tags": ["ai", "gold", "tested"], "price_usd": 499},
    {"id": "ea_quantum_emperor", "name": "Quantum Emperor MT5", "author": "Bogdan Ion Puscasu", "rating": 4.86, "reviews": 503, "strategy_id": 7,
     "description_ru": "Специалист по GBPUSD. 503 отзыва — один из самых проверенных советников.", "description_en": "GBPUSD specialist. 503 reviews — one of the most proven EAs.",
     "tickers": ["GBPUSD"], "timeframe": "Multi", "mql5_url": "https://www.mql5.com/ru/market/product/103452", "risk": "medium", "tags": ["gbpusd", "quantum", "proven"], "price_usd": 799.99},
    {"id": "ea_xiro_robot", "name": "XIRO Robot MT5", "author": "MQL TOOLS SL", "rating": 4.85, "reviews": 26, "strategy_id": 5,
     "description_ru": "Двойная система из проверенных стратегий для GBP/USD, XAUUSD, BTC/USD.", "description_en": "Dual-system combining proven strategies for three assets.",
     "tickers": ["GBPUSD", "XAUUSD", "BTCUSD"], "timeframe": "Multi", "mql5_url": "https://www.mql5.com/ru/market/product/161191", "risk": "medium", "tags": ["dual-system", "multi-asset", "proven"], "price_usd": 699},
    {"id": "ea_wave_rider", "name": "Wave Rider EA MT5", "author": "Adam Hrncir", "rating": 4.83, "reviews": 23, "strategy_id": 4,
     "description_ru": "Гибридный скальпер: скорость + управление позицией. XAUUSD M15/M30.", "description_en": "Hybrid scalper combining speed with position management.",
     "tickers": ["XAUUSD"], "timeframe": "M15-M30", "mql5_url": "https://www.mql5.com/ru/market/product/165897", "risk": "medium", "tags": ["scalping", "hybrid", "gold"], "price_usd": 449},
    {"id": "ea_pulse_engine", "name": "Pulse Engine", "author": "Jimmy Peter Eriksson", "rating": 4.83, "reviews": 18, "strategy_id": 1,
     "description_ru": "Долгосрочная система без мартингейла и сеток. Стабильность важнее скорости.", "description_en": "Long-term system avoiding martingale and grids. Stability over speed.",
     "tickers": ["XAUUSD"], "timeframe": "Multi", "mql5_url": "https://www.mql5.com/ru/market/product/165801", "risk": "low", "tags": ["long-term", "no-martingale", "stable"], "price_usd": 599},
    {"id": "ea_quantum_btc", "name": "Quantum Bitcoin EA", "author": "Bogdan Ion Puscasu", "rating": 4.83, "reviews": 120, "strategy_id": 7,
     "description_ru": "Специалист по Bitcoin. 120 отзывов. Приоритет — производительность и стабильность.", "description_en": "Bitcoin specialist. 120 reviews. Performance and stability priority.",
     "tickers": ["BTCUSD"], "timeframe": "Multi", "mql5_url": "https://www.mql5.com/ru/market/product/127013", "risk": "medium", "tags": ["bitcoin", "quantum", "btc"], "price_usd": 699.99},
    {"id": "ea_gold_atlas", "name": "Gold Atlas", "author": "Jimmy Peter Eriksson", "rating": 4.81, "reviews": 21, "strategy_id": 1,
     "description_ru": "Фокус на долгосрочную стабильность с ежедневной защитой от убытков.", "description_en": "Long-term stability focus with daily loss protection.",
     "tickers": ["XAUUSD"], "timeframe": "Multi", "mql5_url": "https://www.mql5.com/ru/market/product/159658", "risk": "low", "tags": ["gold", "stable", "daily-protection"], "price_usd": 399},
    {"id": "ea_gold_zilla", "name": "Gold Zilla AI MT5", "author": "Christophe Trouillas", "rating": 4.77, "reviews": 13, "strategy_id": 7,
     "description_ru": "5 AI-стратегий адаптирующихся к режимам рынка. Золото.", "description_en": "Five AI strategies adapting to market regimes.",
     "tickers": ["XAUUSD"], "timeframe": "Multi", "mql5_url": "https://www.mql5.com/ru/market/product/155855", "risk": "medium", "tags": ["ai", "regime-adaptive", "gold", "5-strategies"], "price_usd": 229},
    {"id": "ea_chiroptera", "name": "Chiroptera", "author": "Rob Janssen", "rating": 4.76, "reviews": 25, "strategy_id": 3,
     "description_ru": "Ночной мультивалютный советник с постоянной адаптацией. Торговля в тихие часы.", "description_en": "Night-trading multi-currency EA with continuous adjustments.",
     "tickers": ["EURUSD", "GBPUSD", "AUDUSD"], "timeframe": "Night", "mql5_url": "https://www.mql5.com/ru/market/product/152565", "risk": "low", "tags": ["night-trading", "multi-currency", "adaptive"], "price_usd": 899},
    {"id": "ea_quantum_valkyrie", "name": "Quantum Valkyrie", "author": "Bogdan Ion Puscasu", "rating": 4.75, "reviews": 138, "strategy_id": 7,
     "description_ru": "Точность и дисциплина в торговле золотом. 138 отзывов серии Quantum.", "description_en": "Precision-focused gold trading with disciplined execution. 138 reviews.",
     "tickers": ["XAUUSD"], "timeframe": "Multi", "mql5_url": "https://www.mql5.com/ru/market/product/153481", "risk": "medium", "tags": ["quantum", "gold", "precision"], "price_usd": 1099.99},
    {"id": "ea_big_forex_players", "name": "Big Forex Players MT5", "author": "MQL TOOLS SL", "rating": 4.75, "reviews": 136, "strategy_id": 6,
     "description_ru": "3 стратегии отслеживающие позиции крупных банков. 136 отзывов, $2999.", "description_en": "Three strategies tracking major bank positions. 136 reviews.",
     "tickers": ["EURUSD", "GBPUSD", "USDJPY"], "timeframe": "Multi", "mql5_url": "https://www.mql5.com/ru/market/product/92199", "risk": "medium", "tags": ["institutional", "bank-tracking", "forex"], "price_usd": 2999},
    {"id": "ea_talon_gold", "name": "TALON Gold Scalper", "author": "Eusebiu Dascalu", "rating": 5.0, "reviews": 4, "strategy_id": 4,
     "description_ru": "Краткосрочный скальпинг золота с внутренним мульти-таймфрейм анализом.", "description_en": "Short-term gold scalping with internal multi-timeframe analysis.",
     "tickers": ["XAUUSD"], "timeframe": "M15", "mql5_url": "https://www.mql5.com/ru/market/product/174586", "risk": "medium", "tags": ["scalping", "gold", "multi-tf"], "price_usd": 101},
    {"id": "ea_somagold", "name": "SomaGold", "author": "Andrii Soma", "rating": 5.0, "reviews": 1, "strategy_id": 4,
     "description_ru": "32 независимые пробойные стратегии для золота в одном советнике.", "description_en": "32 independent breakout strategies for gold in one EA.",
     "tickers": ["XAUUSD"], "timeframe": "M15", "mql5_url": "https://www.mql5.com/ru/market/product/176349", "risk": "medium", "tags": ["breakout", "gold", "32-strategies"], "price_usd": 200},
    {"id": "ea_twisterpro", "name": "TwisterPro Scalper", "author": "Jorge Guimaraes", "rating": 4.38, "reviews": 73, "strategy_id": 4,
     "description_ru": "M15 скальпер для золота с пятиуровневой верификацией входа. 73 отзыва.", "description_en": "M15 gold scalper with five-level entry verification. 73 reviews.",
     "tickers": ["XAUUSD"], "timeframe": "M15", "mql5_url": "https://www.mql5.com/ru/market/product/166740", "risk": "medium", "tags": ["scalping", "gold", "5-level-verification"], "price_usd": 399},
]

STRATEGY_NAMES_RU = {1: "Тренд", 2: "Возврат к среднему", 3: "Диапазон", 4: "Пробой", 5: "Мульти-индикатор", 6: "Статистический", 7: "ML/AI"}
STRATEGY_NAMES_EN = {1: "Trend Following", 2: "Mean Reversion", 3: "Range", 4: "Breakout", 5: "Multi-Indicator", 6: "Statistical", 7: "ML/AI"}
RISK_RU = {"low": "Низкий", "medium": "Средний", "high": "Высокий"}


def _stats_notice() -> dict:
    """Provenance of the rating/reviews numbers, attached to every response."""
    from datetime import date
    try:
        age = (date.today() - date.fromisoformat(STATS_AS_OF)).days
    except ValueError:
        age = None
    return {
        "stats_as_of": STATS_AS_OF,
        "stats_age_days": age,
        "stats_are_live": False,
        "stats_notice_ru": (
            f"Рейтинг и число отзывов — снимок с MQL5 Market на {STATS_AS_OF}"
            + (f" ({age} дн. назад)" if age else "")
            + ". Это не живые данные: актуальные смотрите по ссылке на MQL5."
        ),
        "stats_notice_en": (
            f"Rating and review count are a snapshot from MQL5 Market taken on "
            f"{STATS_AS_OF}. Not live data — follow the MQL5 link for current values."
        ),
    }


def _enrich(ea: dict) -> dict:
    return {
        **ea,
        "strategy_name_ru": STRATEGY_NAMES_RU.get(ea["strategy_id"], "?"),
        "strategy_name_en": STRATEGY_NAMES_EN.get(ea["strategy_id"], "?"),
        "risk_ru": RISK_RU.get(ea["risk"], ea["risk"]),
        # Per-item too: a card rendered on its own must still carry the date.
        "stats_as_of": STATS_AS_OF,
        "stats_are_live": False,
    }


@router.get("")
async def list_advisors(user: User = Depends(get_current_user)):
    """List all MT5 advisors in catalog with strategy classification."""
    return {
        "advisors": [_enrich(ea) for ea in ADVISORS_CATALOG],
        "total": len(ADVISORS_CATALOG),
        **_stats_notice(),
    }


@router.get("/{advisor_id}")
async def get_advisor(advisor_id: str, user: User = Depends(get_current_user)):
    """Get advisor details."""
    ea = next((a for a in ADVISORS_CATALOG if a["id"] == advisor_id), None)
    if not ea:
        raise HTTPException(404, "Advisor not found")
    return {
        **_enrich(ea),
        **_stats_notice(),
        # The bridge in mt5/WEF_Bridge.mq5 is what actually delivers signals to the
        # platform; the previous text pointed at MetaApi, which is a different path
        # and is not what the project runs.
        "connect_instructions_ru": (
            "1. Скачайте советник на MQL5 Market и установите в MetaTrader 5\n"
            "2. Отдельно поставьте на график WEF_Bridge.mq5 из этого проекта\n"
            "3. В настройках моста: ServerHost/ServerPort и BridgeToken "
            "(= MT5_BRIDGE_TOKEN в .env), PublishToPlatform = true\n"
            "4. Запустите мост: python scripts/mt5_server.py\n"
            "5. Сигналы пройдут гейт качества и появятся на платформе\n\n"
            "Важно: рейтинг и отзывы ниже — снимок с MQL5, а не проверенная "
            "статистика доходности. Результаты советника на вашем счёте "
            "измеряются только после подключения к мосту."
        ),
        "connect_instructions_en": (
            "1. Download the advisor from MQL5 Market and install it in MetaTrader 5\n"
            "2. Separately attach WEF_Bridge.mq5 from this project to a chart\n"
            "3. In the bridge inputs: ServerHost/ServerPort and BridgeToken "
            "(= MT5_BRIDGE_TOKEN in .env), PublishToPlatform = true\n"
            "4. Start the bridge: python scripts/mt5_server.py\n"
            "5. Signals pass the quality gate and appear on the platform\n\n"
            "Note: the rating and review count are an MQL5 snapshot, not verified "
            "performance. This advisor's results on your account are only measured "
            "once it is connected through the bridge."
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
