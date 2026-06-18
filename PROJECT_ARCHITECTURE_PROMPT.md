# Промт: Информационная архитектура проекта WinExtraFlow

Используй этот промт как шаблон для создания аналогичного проекта.
Замени доменную логику (трейдинг/сигналы) на свою, но сохрани структуру, паттерны и связи.

---

## СИСТЕМНЫЙ ПРОМТ

Ты — senior full-stack разработчик. Ты строишь SaaS-платформу со следующей архитектурой.

## 1. СТЕК ТЕХНОЛОГИЙ

```
Backend:  Python 3.12 + FastAPI + SQLAlchemy 2.0 (async) + Pydantic v2
Database: SQLite (dev) / PostgreSQL (prod) + Alembic миграции
Frontend: Next.js 14 (App Router) + TypeScript + Tailwind CSS
Auth:     JWT (access token в localStorage)
Realtime: WebSocket (FastAPI → фронтенд)
Payments: 3 шлюза (РФ рубли + международные карты + крипто)
PWA:      manifest.json + service worker (установка на телефон)
i18n:     2 языка (RU/EN), переключатель в header
Theme:    Dark/Light, CSS variables + Tailwind
```

## 2. СТРУКТУРА BACKEND (30 API модулей)

### 2.1 Модели данных (20 моделей SQLAlchemy)
```
Ядро:
- User (email, username, password_hash, role enum, referral_code, premium_expires_at)
- [MainEntity] — основная сущность продукта (сигнал, задача, заказ...)
- [MainEntityProvider] — источник/автор основных сущностей
- [Category/Strategy] — классификация основных сущностей

Монетизация:
- Payment (user_id, payment_gateway_id, plan enum, amount, currency, status enum)
- Subscription (user_id, strategy_id, status, auto_execute, expires_at)
- Referral (referrer_id, referred_id, level 1/2, reward_type, status)

Социальные:
- Comment (entity_id, user_id, username, text)
- Like (entity_id, user_id) + UniqueConstraint
- Notification (user_id, type enum, title, message, is_read)
- Achievement (name, description, xp, category) + UserAchievement (user_id, unlocked_at)

Операции:
- Order (user_id, entity_id, account_id, status, price, quantity)
- ExchangeAccount (user_id, exchange enum, api_key_encrypted, auto_execute)
- JournalEntry (user_id, entity_id, entry_price, exit_price, note, emotion, tags JSON)
- Alert (user_id, ticker, condition, target_value, is_active, is_triggered)

Юридическое:
- ComplianceDocument (doc_type enum, title, description, status enum, file_path)
- KYCVerification (user_id, status, document_path)
- CourseAccess (user_id, course_id, purchased_at)

Отчёты:
- BacktestReport (user_id, title, metrics JSON, equity_curve JSON)
```

### 2.2 API роутеры (30 модулей)
```
Аутентификация:
- auth.py — register, login, me, profile update, password reset, account delete
- deps.py — get_current_user, require_admin, require_premium, hash_password

Основная логика:
- [entities].py — CRUD основных сущностей + фильтры + пагинация
- [providers].py — CRUD провайдеров/авторов + leaderboard
- [strategies].py — маркетплейс + подписки + unified view

AI/Аналитика:
- ai_chat.py — чат-бот (POST /ask → rule-based analysis на данных платформы)
- screener.py — сканирование по условиям (фильтры, сортировка, 115+ тикеров)
- [intelligence].py — режимы, оценки, readiness monitor

Операции:
- execution.py — подключение аккаунтов бирж + ордера
- copy_trading.py — автокопирование сделок
- journal.py — CRUD дневника + stats (win rate, by emotion, by ticker)
- portfolio.py — агрегация позиций + P&L + allocation + equity curve
- alerts.py — CRUD ценовых алертов (до 20 на пользователя)
- backtesting.py — бэктест на реальных исторических данных (3 API: MOEX/Binance/Yahoo)

Монетизация:
- payments.py — 3 шлюза (checkout, webhook, history, plans)
- premium.py — is_premium, grant_days, activate promo, check_limits
- products.py — API keys, reports, education courses, channels
- referrals.py — stats, tree, my-code

Социальные:
- social.py — comments CRUD, likes toggle, trader profile
- notifications.py — list, mark read, unread count
- achievements.py — seed, list, progress, unlock
- digest.py — weekly digest generation + send to messenger

Админ:
- admin.py — users list, role management, stats
- compliance.py — checklist, upload docs, status, warnings
- [capacity].py — system monitoring

Публичное:
- public.py — stats + sample entity (без авторизации, для лендинга)
- ws.py — WebSocket real-time push

Внешние интеграции:
- [external_data].py — live данные из внешнего API (котировки, индексы)
- [marketplace_items].py — каталог внешних продуктов (50+ items)
```

### 2.3 Сервисы (бизнес-логика)
```
Ядро:
- ai_rating.py — 9-факторная оценка каждой сущности (weighted score 0-1)
- signal_aggregator.py — единая точка входа + listener pattern (on_new_entity)
- [external_parser].py — парсинг из внешних источников (Telegram, webhooks)

Платежи (3 шлюза):
- yookassa_service.py — РФ рубли (карты, СБП 0.7%, SberPay)
- cryptocloud_service.py — крипто (USDT, BTC, ETH — 0.4% комиссия)
- prodamus_service.py — международные карты (USD/EUR — Visa/MC)

Операции:
- execution.py — BaseAdapter → DemoAdapter → [RealAdapters]
- copy_trading.py — on_new_entity → find subscribers → execute
- backtesting_real.py — fetch candles + simulate bar-by-bar + Monte Carlo

Вспомогательные:
- premium.py — is_premium(), grant_premium_days(), check_limits()
- notifications.py — create notification at events (hook pattern)
- achievements.py — seed + increment + unlock (gamification)
- revenue.py — трекинг дохода + алерты при приближении к лимитам
- email_digest.py — weekly summary generation
- seed_data.py — тестовые данные для dev-среды

Эволюционная система (уникальная):
- evolution.py — Registry с 150+ компонентами, ветвями, версиями
- regime.py — определение текущего режима/состояния рынка
- recommendations.py — TP/SL/Volume рекомендации на основе компонентов
- auto_evolution.py — автоматическое обогащение при каждом визите
- article_log.py — трекинг обработанных источников знаний
```

## 3. СТРУКТУРА FRONTEND (36 страниц)

### 3.1 Публичные страницы
```
/ — Landing (hero + live stats + sample + features + pricing 3-tier + comparison table + testimonials + FAQ + urgency + sticky CTA)
/login — Login form
/register — Register + referral code + 2 consent checkboxes
/forgot-password — Email reset
/reset-password — New password form
/terms — Terms of Service (RU/EN)
/privacy — Privacy Policy (RU/EN)
/refund — Refund Policy (RU/EN)
/cookies — Cookie Policy (RU/EN)
/api-docs — API documentation
```

### 3.2 Dashboard (авторизованные)
```
Sidebar навигация (13 пунктов, объединены по смыслу):

1. /dashboard — главная лента (real-time WebSocket + звук + badge)
2. /dashboard/create-signal — форма создания (role: analyst+)
3. /dashboard/marketplace — табы: Стратегии + Лидерборд (объединены)
4. /dashboard/backtest — бэктест на реальных свечах
5. /dashboard/intelligence — табы: Обзор + AI Чат + Скринер (объединены)
6. /dashboard/alerts — CRUD ценовых оповещений
7. /dashboard/portfolio — табы: Обзор + Журнал + Биржи + Ордера + Копитрейдинг (5 табов)
8. /dashboard/telegram — подключение мессенджеров
9. /dashboard/referrals — реферальная программа (2 уровня)
10. /dashboard/store — табы: Premium (3 тарифа × 3 шлюза) + API + Reports + Channels + Education
11. /dashboard/profile — табы: Настройки + KYC (объединены)
12. /dashboard/capacity — admin: мониторинг нагрузки
13. /dashboard/compliance — admin: юр. документы (checklist 17 пунктов)
```

### 3.3 Компоненты
```
Переиспользуемые:
- signal-card.tsx — карточка основной сущности (sparkline + badge + hover glow)
- rating-badge.tsx — бейдж оценки (цветовой: green/yellow/red)
- sparkline.tsx — SVG мини-график (trend line + bar chart)
- candlestick-chart.tsx — TradingView Lightweight Charts (lazy loaded)
- equity-chart.tsx — Recharts AreaChart
- compliance-gate.tsx — блокировка функций по % юр. соответствия
- disclaimer.tsx — юридический дисклеймер
- sea-icons.tsx — иконки (или любая тематическая иконка-библиотека)

Библиотеки:
- lib/api.ts — fetch wrapper с JWT
- lib/auth.ts — AuthProvider context (login, logout, user state)
- lib/ws.ts — WebSocket hook + sound + browser notification + tab badge
- lib/i18n.ts — translations (RU/EN) context + useI18n hook
- lib/theme.ts — dark/light toggle context
- lib/cache.ts — SWR-like stale-while-revalidate cache
- lib/utils.ts — cn(), formatPrice(), timeAgo(), confidenceColor()
```

## 4. ПАТТЕРНЫ АРХИТЕКТУРЫ

### 4.1 Compliance Gate (прогрессивная разблокировка)
```
0%   → информационные разделы (бесплатно)
30%  → базовая монетизация (магазин, рефералы)
60%  → финансовые операции (портфель, маркетплейс)
100% → полная коммерческая эксплуатация

Каждый документ (12 обязательных) = +8.3% к разблокировке.
Admin загружает документы → compliance_pct растёт → функции открываются для ВСЕХ пользователей.
```

### 4.2 Feature Gating (Free vs Pro vs Premium)
```
Free:    лимитированный доступ (N последних сущностей, 1 действие/день)
Pro:     полный доступ к данным + AI + аналитика
Premium: всё + автоматизация + маркетплейс + VIP каналы

Проверка: require_premium dependency в FastAPI + check_limits() в сервисах.
Фронтенд: compliance-gate.tsx блокирует страницу если pct < required.
```

### 4.3 Multi-Payment Gateway
```
Автовыбор по локали пользователя:
- locale === "ru" → РФ шлюз (рубли, СБП)
- locale === "en" → международный шлюз (USD/EUR карты)
- Криптовалюта — доступна всем

3 endpoint'а: /checkout, /checkout/crypto, /checkout/international
Каждый шлюз: demo mode (если нет ключей) → real mode (с ключами из .env)
Webhook'и: отдельный endpoint на каждый шлюз
```

### 4.4 Real-time Pipeline
```
Новая сущность создана
  → signal_aggregator.notify_listeners()
    → AI Rating (автоматическая оценка)
    → WebSocket broadcast → фронтенд (звук + badge + browser notification)
    → Telegram/Messenger bot broadcast (VIP мгновенно, Free с задержкой)
    → Copy trading (авто-исполнение для подписчиков)
    → Notification service (in-app уведомление)
    → Achievement hooks (прогресс гамификации)
```

### 4.5 Evolutionary Architecture (уникальный паттерн)
```
Registry хранит N компонентов (алгоритмы, правила, модели).
Каждый компонент: name, description, strategy_ids[], strength 0-1, status (active/emerging/planned).

Источники знаний: статьи, чаты, документация → парсинг → классификация → новые компоненты.
При каждом визите: auto_evolution.py проверяет новые источники → обогащает Registry.
Ветви эволюции: Stable → Growing → Evolving → Accelerating → Breakthrough.

Article log трекает: какой источник → какие компоненты → какие ветви затронуты.
```

### 4.6 Backtesting на реальных данных
```
3 бесплатных API без ключей:
- Источник 1 (локальный рынок) — например MOEX ISS API
- Источник 2 (крипто) — например Binance API
- Источник 3 (глобальный) — например Yahoo Finance

Автодетект тикера → выбор источника → загрузка OHLCV свечей.
Симуляция бар-за-баром: entry → проверка TP/SL на каждой свече → exit.

Расширенная аналитика:
- Buy & Hold бенчмарк (сравнение с "просто держать")
- Monte Carlo (1000 перестановок → диапазон результатов → risk of ruin)
- Месячная разбивка P&L
- Комиссии + position sizing
- WEF Score фильтр (бэктест только лучших сигналов)
```

## 5. LANDING PAGE СТРУКТУРА (максимальная конверсия)

```
1. Nav: логотип + RUS/ENG + Dark/Light + Login/Register
2. Hero: gradient заголовок + animated live stats (из API) + 2 CTA кнопки + photo bg
3. Exchange/Partner logos: trust bar с названиями интеграций
4. Sample/Demo: пример основного продукта с AI-оценкой (данные из API)
5. Trust badges: шифрование, юрисдикция, дисклеймер (5 бейджей)
6. Features: 6 карточек (glassmorphism + gradient border + hover glow)
7. How it works: 3 шага (photo bg + particles)
8. Promo banner: промокод с кнопкой "скопировать" (mesh gradient)
9. Pricing: 3 тарифа (Free / Pro / Premium) с feature-листами
10. Live Stats: animated counters (из API) + photo bg
11. Comparison table: vs 3 конкурента (9 фич + цены)
12. Testimonials: 3 отзыва (glassmorphism cards)
13. FAQ: 6 вопросов (collapsible details)
14. Urgency banner: промокод + дедлайн + жёлтая CTA
15. Sticky CTA: фиксированная кнопка на мобильных (sm:hidden)
16. Footer: ссылки (Terms, Privacy, Refund, Cookies, API) + disclaimer + copyright
```

## 6. CSS/ВИЗУАЛЬНЫЙ СЛОЙ

```
:root / .dark — CSS variables для всех цветов (surface, card, border, text-primary/secondary/muted)
.glass — backdrop-filter blur + полупрозрачный фон
.gradient-border::before — animated shimmer gradient (3s infinite)
.mesh-gradient — 3 radial-gradient'а разных цветов
.pulse-dot — зелёная пульсирующая точка (live индикатор)
.stat-glow:hover — translateY(-2px) + box-shadow
.particles::after — тонкие точки через radial-gradient
.bg-* — секционные фоны с Unsplash фото + overlay gradient
.card-wave:hover — border-color change + glow shadow

Фото-фоны (Unsplash, бесплатные):
- hero-ocean: ocean/water photo
- bg-trading-floor: рабочее пространство
- bg-analytics: графики/данные
- bg-city-skyline: город ночью
- bg-crypto-dark: крипто/технологии
```

## 7. КОНФИГУРАЦИЯ (.env)

```
# Database
DATABASE_URL=sqlite+aiosqlite:///./app.db

# Security
SECRET_KEY=          (auto-generated in dev, required in prod)
ENCRYPTION_KEY=      (separate key for encrypting sensitive data)

# Admin seed
ADMIN_EMAIL=
ADMIN_USERNAME=
ADMIN_PASSWORD=

# Payments (3 gateways)
YOOKASSA_SHOP_ID=
YOOKASSA_SECRET_KEY=
CRYPTOCLOUD_API_KEY=
CRYPTOCLOUD_SHOP_ID=
PRODAMUS_SECRET_KEY=
PRODAMUS_PAYFORM_URL=

# Messenger integration
TELEGRAM_BOT_TOKEN=
TELEGRAM_API_ID=
TELEGRAM_API_HASH=

# Promo codes
PROMO_CODES=CODE1:DAYS,CODE2:DAYS

# App
APP_ENV=development
ALLOWED_ORIGINS=http://localhost:3000
```

## 8. ТЕСТИРОВАНИЕ

```
13 модулей тестов, 85 тестов:
- test_auth.py (8) — register, login, me, duplicate, bad creds
- test_signals.py (6) — CRUD, webhook, close
- test_providers.py (4) — list, create, leaderboard
- test_ai_rating.py (3) — factors, scoring, provider stats
- test_backtesting.py (2) — engine, metrics
- test_referrals.py (3) — register with ref, stats, tree
- test_execution.py (4) — demo account, execute, orders
- test_strategies.py (3) — publish, browse, subscribe
- test_achievements.py (4) — seed, increment, unlock
- test_security.py (19) — XSS, injection, auth, rate limits
- test_load.py (10) — concurrent requests, stress
- test_stress_functions.py (10) — edge cases
- test_achievement_hooks.py (9) — event-driven hooks

Fixtures: SQLite in-memory + AsyncClient + user/admin factories
```

## 9. DEPLOY

```
docker-compose.yml: PostgreSQL + Redis + Backend + Frontend + Nginx
Frontend Dockerfile: multi-stage (npm install → npm build → serve)
next.config.js: rewrites /api/* → backend:8000, security headers
PWA: manifest.json + sw.js (cache-first static, network-first API)
```

---

## КАК ИСПОЛЬЗОВАТЬ

1. Замени доменную логику (Signal → твоя сущность, Provider → твой автор)
2. Сохрани все паттерны: compliance gate, feature gating, multi-payment, real-time pipeline
3. Адаптируй landing: замени контент, сохрани 16-секционную структуру
4. Скопируй CSS-систему: variables + glass + gradient-border + photo backgrounds
5. Используй те же 3 платёжных шлюза (ЮKassa + CryptoCloud + Prodamus) для РФ рынка
6. Эволюционная архитектура — опциональна, но даёт уникальное конкурентное преимущество

---

## 10. CHANGELOG — Контроль изменений

Каждая запись = конкретное изменение с путями файлов. Можно скопировать и воспроизвести.

---

### v1.0.0 — Фундамент (Phase 1-9)
```
Создано:
- backend/app/main.py — FastAPI entry + lifespan (seed, listeners, bots)
- backend/app/config.py — Pydantic Settings (50+ переменных)
- backend/app/database.py — SQLAlchemy async engine + session
- backend/app/models/ — 17 моделей (User, Signal, Provider, Strategy...)
- backend/app/api/ — 20 роутеров (auth, signals, providers, strategies...)
- backend/app/services/ — 15 сервисов (ai_rating, execution, copy_trading...)
- frontend/src/app/ — 25 страниц (login, register, dashboard/*)
- frontend/src/components/ — signal-card, rating-badge, sidebar, header
- frontend/src/lib/ — api.ts, auth.ts, ws.ts, i18n.ts, theme.ts, utils.ts
- docker-compose.yml, frontend/Dockerfile, nginx/nginx.conf
- backend/tests/ — 85 тестов, 13 модулей
```

### v1.1.0 — Маркетплейс + эволюция
```
Создано:
- backend/app/api/advisors.py — 50 MT5 советников (24 free + 26 paid)
- backend/app/api/tv_strategies.py — 16 TradingView стратегий
- backend/app/services/quant/evolution.py — Registry 116 компонентов
- backend/app/services/quant/article_log.py — 52 MQL5 статей
- backend/app/services/quant/recommendations.py — TP/SL/Volume engine
- backend/app/services/quant/auto_evolution.py — авто-эволюция при визите

Изменено:
- frontend/src/app/dashboard/marketplace/page.tsx — 3 таба → 1 unified view
```

### v1.2.0 — MOEX + мессенджеры + приватность
```
Создано:
- backend/app/services/moex.py — MOEX ISS API (27 тикеров, 7 индексов)
- backend/app/services/telegram_bot.py — Telegram бот (VIP + Free каналы)
- backend/app/services/max_bot.py — MAX Messenger бот
- backend/app/services/revenue.py — трекинг дохода самозанятого
- frontend/src/app/privacy/page.tsx — 9 разделов ФЗ-152
- frontend/src/app/terms/page.tsx, refund/page.tsx, cookies/page.tsx

Изменено:
- backend/app/models/user.py — +ANALYST role, +max_chat_id
- frontend/src/app/register/page.tsx — 2 consent checkboxes
```

### v2.0.0 — Landing + Public API + WEF Score
```
Создано:
- backend/app/api/public.py — /stats + /sample-signal (без авторизации)
- frontend/src/app/page.tsx — полный лендинг (hero, features, pricing, stats)

Изменено:
- frontend/src/components/rating-badge.tsx — "AI" → "WEF" (ребрендинг)
- frontend/src/app/page.tsx — live stats counter, sample signal, promo AIGROWTH14
- backend/app/services/seed_data.py — удалён [TEST] префикс
```

### v2.1.0 — AI Ассистент + Скринер + PWA
```
Создано:
- backend/app/api/ai_chat.py — POST /ask (5 типов запросов)
- backend/app/api/screener.py — GET /scan (68→115 тикеров, 4→5 рынков)
- frontend/src/app/dashboard/ai-chat/page.tsx — чат-интерфейс + suggestions
- frontend/src/app/dashboard/screener/page.tsx — таблица + фильтры
- frontend/public/manifest.json — PWA manifest
- frontend/public/sw.js — Service Worker (cache-first)

Изменено:
- frontend/src/app/layout.tsx — +manifest link, +theme-color meta, +SW register
- frontend/src/components/sidebar.tsx — +AI Ассистент, +Скринер
```

### v2.2.0 — Торговый журнал + Портфель + Оповещения
```
Создано:
- backend/app/models/journal.py — JournalEntry (ticker, action, emotion, tags)
- backend/app/models/alert.py — PriceAlert (ticker, condition, target)
- backend/app/api/journal.py — CRUD + /stats (win rate, by emotion, by ticker)
- backend/app/api/portfolio.py — summary (positions, P&L, allocation, equity)
- backend/app/api/alerts.py — CRUD + toggle (limit 20)
- frontend/src/app/dashboard/journal/page.tsx — форма + список + статистика
- frontend/src/app/dashboard/portfolio/page.tsx — 3 таба (обзор, биржи, ордера)
- frontend/src/app/dashboard/alerts/page.tsx — создание + управление алертами

Изменено:
- frontend/src/lib/ws.ts — +playNotificationSound(), +updateTabBadge(), +showBrowserNotification()
- frontend/src/app/dashboard/page.tsx — +requestNotificationPermission(), +resetBadge(), +pulse-dot
```

### v2.3.0 — Социальные функции + Дайджест + Кеширование
```
Создано:
- backend/app/models/social.py — SignalComment + StrategyLike
- backend/app/api/social.py — comments CRUD, likes toggle, trader profile
- backend/app/api/digest.py — preview + send-telegram
- backend/app/services/email_digest.py — weekly summary generation
- frontend/src/lib/cache.ts — SWR-like cachedFetch()

Изменено:
- frontend/src/app/dashboard/signals/[id]/page.tsx — +CommentsSection component
```

### v2.4.0 — Графики + Визуальные улучшения
```
Создано:
- frontend/src/components/candlestick-chart.tsx — TradingView Lightweight Charts (lazy)
- frontend/src/components/sparkline.tsx — SVG Sparkline + SparkBar

Изменено:
- frontend/src/app/globals.css — +glass, +gradient-border, +mesh-gradient, +pulse-dot, +stat-glow, +particles, +bg-trading-floor, +bg-crypto-dark, +bg-analytics, +bg-city-skyline
- frontend/src/app/dashboard/signals/[id]/page.tsx — +CandlestickChart (Entry/TP/SL lines)
- frontend/src/components/signal-card.tsx — +Sparkline, +stat-glow hover
- frontend/src/app/page.tsx — фото-фоны на секциях, glassmorphism карточки
```

### v2.5.0 — Sidebar consolidation (19 → 13 вкладок)
```
Объединено:
- Аналитика + AI Чат + Скринер → /dashboard/intelligence (3 таба)
- Портфель + Журнал + Копитрейдинг → /dashboard/portfolio (5 табов)
- Лидерборд + Маркетплейс → /dashboard/marketplace (2 таба)
- KYC + Профиль → /dashboard/profile (2 таба)

Удалено из sidebar:
- /dashboard/leaderboard (→ внутри marketplace)
- /dashboard/ai-chat (→ внутри intelligence)
- /dashboard/screener (→ внутри intelligence)
- /dashboard/journal (→ внутри portfolio)
- /dashboard/copy-trading (→ внутри portfolio)
- /dashboard/execution (→ внутри portfolio)
- /dashboard/kyc (→ внутри profile)

Изменено:
- frontend/src/components/sidebar.tsx — 19 items → 13 items
- frontend/src/components/compliance-gate.tsx — обновлён FEATURE_TIERS
- frontend/src/app/dashboard/intelligence/page.tsx — +MarketOverview wrapper + tab switcher
- frontend/src/app/dashboard/portfolio/page.tsx — +5 табов (Journal, CopyTrading dynamic import)
- frontend/src/app/dashboard/marketplace/page.tsx — +StrategiesContent + LeaderboardPage tab
- frontend/src/app/dashboard/profile/page.tsx — +KYCPage tab
```

### v2.6.0 — ЮKassa + CryptoCloud + Prodamus (3 шлюза)
```
Создано:
- backend/app/services/yookassa_service.py — РФ рубли (карты, СБП, SberPay)
- backend/app/services/cryptocloud_service.py — крипто (USDT, BTC, ETH)
- backend/app/services/prodamus_service.py — международные карты (USD/EUR)

Изменено:
- backend/app/api/payments.py — +/checkout/crypto, +/checkout/international, +/webhook/crypto, +/webhook/prodamus, обновлён /plans (3 метода)
- backend/app/config.py — +yookassa_*, +cryptocloud_*, +prodamus_*
- backend/app/models/payment.py — +yookassa_payment_id, currency default "rub"
- frontend/src/app/dashboard/store/page.tsx — +PaymentSection (3 метода × 3 тарифа)
```

### v2.7.0 — 3-tier pricing (Free/Pro/Premium)
```
Изменено:
- backend/app/services/yookassa_service.py — PLAN_CONFIG: monthly 2990, yearly 23900 + PRO_CONFIG: 1490/11900
- backend/app/services/cryptocloud_service.py — $33/$264 + PRO $16/$128
- backend/app/services/prodamus_service.py — $33/€30 + PRO $16/€15
- frontend/src/app/dashboard/store/page.tsx — 3 карточки (Pro/Premium/Yearly) с feature-листами
- frontend/src/app/page.tsx — 3-tier pricing на лендинге (Free $0 / Pro 1490₽ / Premium 2990₽)
- frontend/src/app/page.tsx — comparison table: WinExtraFlow $0-33 vs TradingView $13-200 vs Token Metrics $29-99 vs 3Commas $29-99
```

### v2.8.0 — Landing максимальная конверсия
```
Добавлено на лендинг (frontend/src/app/page.tsx):
- Exchange logos trust bar (9 бирж)
- Trust badges (5 бейджей: HTTPS, ФЗ-152, оферта, шифрование, дисклеймер)
- Comparison table vs 3 конкурента (9 фич)
- Testimonials (3 отзыва бета-тестеров)
- FAQ (6 вопросов с collapsible)
- Urgency banner (промокод + жёлтая CTA)
- Sticky CTA (мобильная фиксированная кнопка)
```

### v2.9.0 — Факт-чек лендинга
```
Исправлено:
- "AES-256" → "Fernet (AES-128-CBC)" — правда (2 места)
- MOEX убран из логотипов бирж → заменён на Exante
- "автоматически торгуем" → "подключаем к биржам для авто-торговли"
- "153 компонента" → "150+ компонентов" (динамически растёт)
- Дублирование "(Fernet)" в FAQ убрано
```

### v2.10.0 — Эволюция РБК Крипто
```
Создано:
- memory/ai_analyst_profiles.md — 10 профилей аналитиков с AI

Изменено:
- backend/app/services/quant/evolution.py — +37 компонентов (116 → 153)
- backend/app/services/quant/article_log.py — +РБК Крипто (5000 сообщений)
```

### v3.0.0 — Real Backtesting Engine
```
Создано:
- backend/app/services/backtesting_real.py:
  - fetch_moex_candles() — MOEX ISS API (бесплатно)
  - fetch_binance_candles() — Binance API (бесплатно)
  - fetch_forex_candles() — Yahoo Finance (бесплатно, 300+ пар)
  - detect_source() — авто-детект по тикеру (MOEX/Binance/Forex/Stocks)
  - simulate_trade() — бар-за-баром (TP/SL проверка)
  - run_real_backtest() — полный отчёт
  - compute_monthly_breakdown() — P&L по месяцам
  - compute_buy_and_hold() — бенчмарк
  - run_monte_carlo() — 1000 симуляций (equity, drawdown, risk of ruin)
  - apply_commission() — вычет комиссии
  - apply_position_sizing() — масштабирование по размеру позиции

Изменено:
- backend/app/api/backtesting.py:
  - POST /backtest/real — расширенный ответ:
    - raw (до комиссии) + adjusted (после)
    - buy_and_hold бенчмарк + strategy_vs_hold
    - monthly breakdown
    - monte_carlo (1000 sim: median, p5, p95, risk_of_ruin, profitable_pct)
    - exits breakdown (tp/sl/expired)
    - min_wef_score фильтр
    - commission_pct + position_size_pct параметры

- backend/app/api/screener.py — 68 → 115 тикеров (5 рынков):
  - MOEX: 24 | Crypto: 15 | Forex: 18 | US Stocks: 47 | EU/Asia: 11

Покрытие бэктеста:
- 115 тикеров + 300+ форекс-пар
- 3 API, все бесплатные, без ключей
- Monte Carlo: 1000 перестановок → risk of ruin + profitable %
```

### v3.1.0 — Marketing Context File
```
Создано:
- winextraflow_telegram_wave1_context.md — 8 постов + описание UI + метрики
- PROJECT_ARCHITECTURE_PROMPT.md — этот файл (воспроизводимая архитектура)
```

---

### v3.2.0 — Evolution: 50 new sources
```
Изменено:
- backend/app/services/quant/evolution.py — +46 компонентов (154 → 200):
  - 10 MQL5 Neural Network articles: spatial aggregation, perturbed SSM, UncAD, STCA,
    unified feature-context, robust patterns, structural decomposition, ADS, diff microstructure, GDformer
  - 8 MQL5 Practical articles: RSI grid + risk manager, Hurst exponent, categorical HMM,
    inconsistency risk, custom symbols, cellular grid EA, synthetic options, L1-VaR portfolio
  - 5 Transformer research papers: TFT, PatchTST, Informer, Autoformer, FEDformer
  - 10 Trading community strategies: Ichimoku, Harmonic patterns, Order Blocks (SMC),
    Wyckoff phases, Elliott Wave, Supply/Demand zones, Session filter, Correlation matrix,
    Mean reversion bands, Multi-TF momentum divergence
  - 8 Quantitative finance: GARCH regime switching, Kalman filter, Hawkes process,
    PCA factors, VaR/CVaR, Sharpe/Sortino/Calmar/Omega, Walk-forward optimizer,
    Regime-aware position sizing
  - 5 Misc: volatility forecast Python, 3D bars, 3D trend strength, MT5 debug, GARCH

- backend/app/services/quant/article_log.py — +35 ProcessedArticle records (64 → 99 sources)

Результат:
  Компонентов: 200 (9 active, 187 emerging, 4 planned)
  Источников: 99
```

### v3.3.0 — Heatmap Integration (BestStocks-style)
```
Создано:
- frontend/src/components/heatmap-widget.tsx:
  - TradingViewHeatmap — embed TradingView виджет (MOEX/Crypto/US, бесплатно)
  - CustomHeatmap — собственная тепловая карта из MOEX API данных (по секторам, цвет = change%)
- frontend/src/components/heatmap-tab.tsx — 4 вида карт:
  - MOEX Live (наши данные, MOEX ISS API, real-time)
  - MOEX TradingView (интерактивный виджет)
  - Crypto (TradingView крипто heatmap)
  - US Stocks S&P 500 (TradingView)

Изменено:
- backend/app/api/moex.py — +GET /moex/heatmap (тикеры + change% + секторы)
- frontend/src/app/dashboard/intelligence/page.tsx — +таб "Тепловая карта" (4-й таб в Аналитике)

Секторы MOEX: Finance, Energy, Metals, Tech, Retail, Telecom, Transport, Chemicals
```

### v3.4.0 — Cleanup: dead code + bug fix
```
Баг исправлен:
- frontend/src/lib/api.ts — session_id → payment_id (demo-оплата работает)
- frontend/src/app/dashboard/store/page.tsx — session_id → payment_id

Удалено (мёртвый код):
- backend/app/services/stripe_service.py — Stripe полностью заменён на ЮKassa
- frontend/src/components/strategy-card.tsx — нигде не импортировался
- frontend/src/app/dashboard/execution/ — дубликат Portfolio → Биржи + Ордера
- frontend/src/app/dashboard/premium/ — заменена на Store с 3 шлюзами
- frontend/src/app/dashboard/moex/ — MOEX встроен в Intelligence

Конфиг очищен:
- .env.example — Stripe убран, добавлены ЮKassa/CryptoCloud/Prodamus
- config.py — stripe_api_key/stripe_webhook_secret удалены
- models/__init__.py — __all__ обновлён (14 → 21 модель)
- compliance-gate.tsx — удалены /execution, /moex из legacy routes
- intelligence/page.tsx — ссылка /premium → /store
```

### v3.5.0 — Feedback System
```
Создано:
- backend/app/models/feedback.py — модель (type, rating 1-5, nps 0-10, upvotes, admin_reply, status)
- backend/app/api/feedback.py — 7 endpoints (submit, list, my, upvote, delete, reply, stats)
- frontend/src/components/feedback-widget.tsx — плавающая кнопка 💬 + модальное окно
- frontend/src/app/dashboard/feedback/page.tsx — страница всех отзывов + admin ответы

Типы: review (⭐), feature_request (💡), bug_report (🐛), suggestion (💬), nps (📊)
Метрики: NPS score, avg rating, top feature requests by upvotes, by category
```

## 11. ТЕКУЩЕЕ СОСТОЯНИЕ ПРОЕКТА

```
Backend:   30 API модулей, 20 моделей, 24 сервиса, 122 endpoints
Frontend:  36 страниц, 13 sidebar пунктов, 10+ компонентов
Tests:     85 тестов, 13 модулей
Тикеров:   115 (screener) + 300+ forex пар (backtest)
AI:        200 эволюционных компонентов из 99 источников
Платежи:   3 шлюза (ЮKassa + CryptoCloud + Prodamus), 10 способов оплаты
Тарифы:    Free ($0) / Pro ($16) / Premium ($33)
Языки:     RU/EN
Тема:      Dark/Light
PWA:       Да
Юр. docs:  5 страниц (Terms, Privacy, Refund, Cookies, Risk)
Compliance: 17-point checklist, progressive unlock (0/30/60/100%)
```
