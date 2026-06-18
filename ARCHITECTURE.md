# ARCHITECTURE.md — WinExtraFlow

> Единственный источник правды по архитектуре. Обновляй при значимых изменениях.

---

## Обзор

**Проект:** WinExtraFlow — агрегатор торговых сигналов с AI-рейтингом
**Назначение:** Агрегация сигналов (Telegram/TradingView), AI-оценка, авто-трейдинг, маркетплейс стратегий, копи-трейдинг
**Версия:** 1.0 MVP
**Статус:** Production-ready backend, MVP frontend

---

## Технологический стек

| Слой | Технология | Версия |
|------|-----------|--------|
| Backend | FastAPI | 0.115.6 |
| Runtime | Python | 3.12 |
| ORM | SQLAlchemy (async) | 2.0.36 |
| DB driver | asyncpg | 0.30.0 |
| Migrations | Alembic | 1.14.0 |
| Database | PostgreSQL | 16 |
| Cache/Queue | Redis | 7 |
| Auth | PyJWT | 2.10.1 |
| Password | passlib[bcrypt] | 1.7.4 |
| Encryption | cryptography (Fernet) | — |
| HTTP client | httpx | 0.28.1 |
| Telegram | Telethon | 1.38.1 |
| Frontend | Next.js (App Router) | 14.x |
| Language | TypeScript | 5 |
| Styling | Tailwind CSS | 3.x |
| Charts | Recharts + lightweight-charts | — |
| Reverse proxy | Nginx | alpine |
| Containers | Docker Compose | — |

---

## Структура репозитория

```
WinExtraFlow/
├── backend/
│   ├── app/
│   │   ├── api/               # 32 API-модуля
│   │   │   ├── deps.py        # FastAPI dependencies
│   │   │   ├── auth.py        # Аутентификация
│   │   │   ├── signals.py     # Торговые сигналы
│   │   │   ├── payments.py    # YooKassa/CryptoCloud/Prodamus
│   │   │   ├── referrals.py   # Реферальная система
│   │   │   ├── ws.py          # WebSocket live updates
│   │   │   └── ...            # (29 других модулей)
│   │   ├── models/            # 20 SQLAlchemy-моделей
│   │   ├── schemas/           # 11 Pydantic-схем
│   │   ├── services/
│   │   │   ├── exchanges/     # 9 адаптеров бирж
│   │   │   ├── quant/         # AI-анализ, эволюция стратегий
│   │   │   ├── telegram.py    # Bot broadcast
│   │   │   ├── yookassa_service.py
│   │   │   ├── cryptocloud_service.py
│   │   │   ├── prodamus_service.py
│   │   │   └── ...
│   │   ├── workers/
│   │   │   └── signal_fetcher.py   # Async парсинг Telegram-каналов
│   │   ├── config.py          # pydantic-settings
│   │   ├── database.py        # SQLAlchemy engine
│   │   └── main.py            # FastAPI app, lifespan
│   ├── alembic/
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── app/               # Next.js App Router
│   │   │   ├── dashboard/     # 25+ страниц
│   │   │   ├── login/
│   │   │   ├── register/
│   │   │   └── ...
│   │   ├── components/        # Charts, cards, sidebar
│   │   ├── lib/
│   │   │   ├── api.ts         # ApiClient (342 строки)
│   │   │   └── auth.ts        # React Context auth
│   │   └── types/
│   ├── public/
│   ├── package.json
│   └── Dockerfile
│
├── nginx/nginx.conf
├── docker-compose.yml
├── .env.example
└── ARCHITECTURE.md
```

---

## Архитектурные паттерны

### Поток сигналов
```
[Telegram каналы] ──► [signal_fetcher worker]
[TradingView webhook] ──► [/api/v1/tv_strategies]
                                  │
                         [AI Rating Service]
                         confidence scoring
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
             [PostgreSQL]              [Redis Pub/Sub]
             signal record             live broadcast
                    │                           │
             [Copy Trading]              [WebSocket]
             Auto execution             frontend updates
                    │
             [Exchange Adapters]
             Binance/Bybit/OKX/...
```

### Биржевые адаптеры
```python
class ExchangeAdapter(ABC):
    async def place_order(ticker, side, qty, price) -> Order
    async def get_balance() -> Balance
    async def get_positions() -> list[Position]
    async def cancel_order(order_id) -> bool
```
Реализации: `binance`, `bybit`, `kraken`, `okx`, `tinkoff`, `exante`, `ib`, `mt5`, `demo`

---

## База данных

### Ключевые таблицы

| Таблица | Назначение |
|---------|-----------|
| `users` | Аккаунты, роли, referral_code, premium |
| `signals` | Торговые сигналы (ticker, action, price, confidence, TP/SL) |
| `providers` | Авторы/советники сигналов с рейтингом |
| `exchange_accounts` | Зашифрованные API-ключи бирж |
| `orders` | Исполненные ордера |
| `strategies` | Маркетплейс стратегий |
| `subscriptions` | Premium-подписки |
| `copy_trades` | Конфиги копи-трейдинга |
| `achievements` | Геймификация |
| `payments` | История транзакций (3 шлюза) |
| `referrals` | Реферальная система (level 1/2) |
| `notifications` | Уведомления |
| `kyc_verifications` | KYC документы |
| `journal_entries` | Торговый журнал |
| `price_alerts` | Ценовые уведомления |
| `backtest_reports` | Результаты бэктестинга |

---

## API Endpoints (ключевые)

**Base URL:** `/api/v1`

| Метод | Endpoint | Auth | Описание |
|-------|----------|------|---------|
| POST | `/auth/register` | — | Регистрация |
| POST | `/auth/login` | — | JWT token |
| POST | `/auth/refresh` | — | Refresh token |
| GET | `/auth/me` | ✓ | Профиль |
| GET | `/signals` | ✓ | Список сигналов |
| POST | `/signals` | ✓ | Создать сигнал |
| GET | `/signals/{id}/chart` | ✓ | Ценовые данные |
| POST | `/execution/order` | ✓ | Исполнить ордер |
| GET | `/strategies` | — | Маркетплейс |
| POST | `/copy_trading/subscribe` | ✓ | Копировать трейдера |
| POST | `/payments/yookassa` | ✓ | Создать платёж |
| POST | `/payments/webhook/yookassa` | — | YooKassa webhook |
| POST | `/payments/webhook/cryptocloud` | — | CryptoCloud webhook |
| GET | `/referrals/stats` | ✓ | Статистика рефералов |
| WS | `/api/v1/ws` | ✓ | Live сигналы |
| GET | `/health` | — | Health check |

---

## Окружение (.env)

| Переменная | Обязательна | Описание |
|-----------|------------|---------|
| `DATABASE_URL` | ✓ | PostgreSQL async DSN |
| `REDIS_URL` | ✓ | Redis DSN |
| `SECRET_KEY` | ✓ | JWT (мин. 32 символа) |
| `ENCRYPTION_KEY` | ✓ | Fernet (для биржевых ключей) |
| `TELEGRAM_BOT_TOKEN` | ✓ | Bot для рассылки |
| `TELEGRAM_CHANNEL_ID` | ✓ | Free-канал |
| `TELEGRAM_VIP_CHANNEL_ID` | ✓ | VIP-канал |
| `YOOKASSA_SHOP_ID` | — | Платежи RU |
| `YOOKASSA_SECRET_KEY` | — | — |
| `CRYPTOCLOUD_API_KEY` | — | Крипто-платежи |
| `PRODAMUS_SECRET_KEY` | — | Платежи USD/EUR |
| `TRADINGVIEW_SECRET` | — | Webhook HMAC |

---

## Инфраструктура

### Docker Compose (5 сервисов)
| Сервис | Image | Port |
|--------|-------|------|
| postgres | postgres:16-alpine | 5432 |
| redis | redis:7-alpine | 6379 |
| backend | custom | 8200 |
| frontend | custom | 3200 |
| nginx | nginx:alpine | 80 |

---

## Запуск

```bash
# Полный стек
docker compose up -d

# Backend (dev)
cd backend
alembic upgrade head
uvicorn app.main:app --reload --port 8200

# Frontend (dev)
cd frontend
npm install && npm run dev   # :3200

# Тесты
cd backend && pytest tests/ -v
```

---

## Changelog

### v1.0 — 2026-06-11
- Полный backend (32 API-модуля, 20 моделей)
- JWT auth + bcrypt
- 9 биржевых адаптеров
- 3 платёжных шлюза
- Реферальная система (2 уровня)
- Telegram bot + парсинг каналов
- TradingView webhook
- Docker Compose deployment
