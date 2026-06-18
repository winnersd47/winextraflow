# CLAUDE.md — WinExtraFlow

> Агрегатор торговых сигналов с AI-рейтингом, авто-трейдингом и маркетплейсом стратегий. Часть экосистемы AIGrowth.
> Общие принципы: `../AIGROWTH.md` | Shared-модули: `../shared/`

---

## Проект

**Назначение:** Платформа торговых сигналов — агрегация из Telegram/TradingView, AI-рейтинг, копи-трейдинг, маркетплейс стратегий, 3 платёжных шлюза.
**Корень:** `C:\Users\v.serdyuk\Documents\AIGrowth\WinExtraFlow\`
**Frontend:** http://localhost:3200 | **Backend:** http://localhost:8200

---

## Стек

| Слой | Технология |
|------|-----------|
| Backend | Python 3.12 + FastAPI 0.115.6 |
| ORM | SQLAlchemy 2.0 async + asyncpg |
| БД | PostgreSQL 16 + Redis 7 |
| Биржи | Binance, Bybit, Kraken, OKX, Tinkoff, Exante, IB, MetaTrader5 |
| Мессенджеры | Telethon (парсинг каналов) + Telegram Bot + MAX Bot |
| AI | Signal rating, quant evolution, strategy classifier |
| Платежи | YooKassa + CryptoCloud + Prodamus |
| Frontend | Next.js 14 + TypeScript + Tailwind + Recharts |
| Инфра | Docker Compose + Nginx |

---

## Ключевые файлы

| Файл | Назначение |
|------|-----------|
| `backend/app/main.py` | FastAPI app, 33+ роутера |
| `backend/app/config.py` | 40+ настроек (pydantic-settings) |
| `backend/app/api/auth.py` | JWT auth (register/login/refresh/logout) |
| `backend/app/api/signals.py` | Торговые сигналы (CRUD + chart) |
| `backend/app/api/payments.py` | YooKassa + CryptoCloud + Prodamus webhooks |
| `backend/app/api/referrals.py` | Реферальная система |
| `backend/app/api/ws.py` | WebSocket (live signal streaming) |
| `backend/app/services/exchanges/` | 9 адаптеров бирж |
| `backend/app/services/quant/` | AI-анализ, эволюция стратегий |
| `backend/app/services/telegram.py` | Telegram bot broadcast |
| `backend/app/services/yookassa_service.py` | YooKassa логика |
| `backend/app/models/` | 20 моделей (signal, user, payment, referral, ...) |
| `frontend/src/lib/api.ts` | ApiClient (342 строки) |
| `frontend/src/lib/auth.ts` | React Context auth provider |
| `docker-compose.yml` | 5 сервисов: postgres, redis, backend, frontend, nginx |
| `.env.example` | 40+ переменных окружения |

---

## Команды

```bash
# Полный стек
docker compose up -d

# Backend (dev)
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8200

# Frontend (dev)
cd frontend
npm install
npm run dev  # :3200

# Тесты
cd backend && pytest tests/ -v
```

---

## API (33 роутера)

| Группа | Роутеры |
|--------|--------|
| Auth | auth.py |
| Торговля | signals, providers, execution, copy_trading, backtesting, screener, journal, portfolio, alerts |
| AI/Quant | quant, ai_chat, tv_strategies, moex, advisors |
| Монетизация | payments, premium, strategies (маркетплейс), referrals |
| Социальные | social, achievements, notifications, digest |
| Прочее | admin, kyc, compliance, products, public, ws |

---

## Биржи (services/exchanges/)

Каждая биржа — отдельный адаптер с общим интерфейсом:
```python
class ExchangeAdapter:
    async def place_order(ticker, side, qty, price) -> Order
    async def get_balance() -> Balance
    async def get_positions() -> list[Position]
    async def cancel_order(order_id) -> bool
```
Адаптеры: `binance.py`, `bybit.py`, `kraken.py`, `okx.py`, `tinkoff.py`, `exante.py`, `ib.py`, `mt5.py`, `demo.py`

---

## Критические пробелы

| Файл | Важность | Описание |
|------|---------|---------|
| `frontend/next.config.mjs` | 🔴 КРИТИЧНО | Отсутствует (Next.js не будет работать корректно) |
| `frontend/src/middleware.ts` | 🟡 ВАЖНО | Нет Edge-защиты роутов |
| `ARCHITECTURE.md` | 🟡 ВАЖНО | Архитектурная документация отсутствует |
| `Makefile` | 🟢 ПОЛЕЗНО | Автоматизация dev-команд |

---

## Реферальная система (уже реализована)

```python
# backend/app/api/referrals.py
# Формат: /register?ref=XXXXXX
# Level 1: +7 дней Pro
# Level 2: +3 дня Pro
```

---

## Платёжные шлюзы (уже реализованы)

```python
# YooKassa (RU: карты, СБП, SberPay)
YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY

# CryptoCloud (USDT, BTC, ETH)
CRYPTOCLOUD_API_KEY, CRYPTOCLOUD_SHOP_ID

# Prodamus (USD/EUR)
PRODAMUS_SECRET_KEY, PRODAMUS_PAYFORM_URL
```
Вебхуки в `backend/app/api/payments.py`.

---

## Правила при разработке

1. **Биржи** — только через адаптеры в `services/exchanges/`, не напрямую к API
2. **Сигналы** — broadcast через `services/telegram.py` (VIP + Free каналы раздельно)
3. **Платежи** — верифицировать HMAC-подписи вебхуков перед обработкой
4. **Exchange credentials** — шифровать через Fernet перед сохранением в БД
5. **WebSocket** — использовать `api/ws.py` для live-обновлений, не polling

---

## Типичные задачи

### Добавить новую биржу
1. `backend/app/services/exchanges/{name}.py` (реализовать ExchangeAdapter)
2. Добавить в routing в `backend/app/api/execution.py`
3. Добавить ENV-переменные в `.env.example`

### Добавить новый тип сигнала
1. Обновить `backend/app/models/signal.py`
2. Alembic-миграция
3. Обновить AI-рейтинг в `services/ai_rating.py`
