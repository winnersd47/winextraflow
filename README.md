# WinExtraFlow

AI-платформа торговых сигналов с WEF Score рейтингом.

## Что это

Агрегируем сигналы из TradingView и Telegram, оцениваем AI по 9 факторам (WEF Score 0-100), подключаем к биржам для авто-торговли.

## Ключевые цифры

- **200** AI эволюционных компонентов из 99 источников
- **115** тикеров в скринере (MOEX, Crypto, Forex, US/EU Stocks)
- **9** бирж (Binance, Bybit, OKX, Kraken, MT5, IBKR, Tinkoff, Exante, Demo)
- **3** платёжных шлюза (ЮKassa, CryptoCloud, Prodamus)
- **10** внешних API (MOEX ISS, Binance, Yahoo Finance, CoinGecko, CBR, DeFi Llama...)

## Стек

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2
- **Frontend**: Next.js 14, TypeScript, Tailwind CSS
- **Database**: SQLite (dev) / PostgreSQL (prod)
- **Payments**: ЮKassa (RUB) + CryptoCloud (USDT/BTC) + Prodamus (USD/EUR)
- **Charts**: TradingView Lightweight Charts
- **PWA**: manifest.json + service worker

## Быстрый старт

```bash
# Backend
cd backend
pip install -r requirements.txt
cp ../.env.example .env  # заполнить
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

Открыть: http://localhost:3000

## Тарифы

| Тариф | RUB | USD | Что входит |
|-------|:---:|:---:|-----------|
| Free | 0 | $0 | 10 сигналов, 1 бэктест/день |
| Pro | 1 490 | $16 | Все сигналы, AI чат, скринер, журнал |
| Premium | 2 990 | $33 | Всё + копитрейдинг, исполнение, маркетплейс |

## Структура

```
WinExtraFlow/
├── backend/           # FastAPI (30 API модулей, 21 модель, 24 сервиса)
│   ├── app/api/       # 122 endpoints
│   ├── app/models/    # SQLAlchemy models
│   ├── app/services/  # Business logic + AI
│   └── tests/         # 130 tests
├── frontend/          # Next.js 14 (36 pages, 13 sidebar tabs)
│   ├── src/app/       # Pages (App Router)
│   ├── src/components # Reusable components
│   └── src/lib/       # API, auth, i18n, ws, cache
├── tg-bot/            # Telegram bot (content publishing)
├── nginx/             # Reverse proxy config
└── docker-compose.yml # Full stack deploy
```

## Тесты

```bash
cd backend
pytest tests/ -v
# 130 tests, 20 modules
```

## Документы

- [PROJECT_ARCHITECTURE_PROMPT.md](PROJECT_ARCHITECTURE_PROMPT.md) — полная архитектура + changelog
- [winextraflow_telegram_wave1_context.md](winextraflow_telegram_wave1_context.md) — маркетинг контент

## Лицензия

Proprietary. All rights reserved.
