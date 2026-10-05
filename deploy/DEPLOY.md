# Деплой WinExtraFlow

Фронтенд — статика на том же VPS (Cloudflare Pages недоступен из РФ, см. п.7).
Бэкенд — FastAPI на российском VPS (152-ФЗ: персональные данные граждан РФ
хранятся в РФ).

```
Пользователь → winextraflow.ru (nginx, статика Next.js export)
                        ↓ /api/* на том же origin
             127.0.0.1:8000 — uvicorn (systemd) + SQLite + cron
```

---

## Что этот деплой даёт и чего не даёт

Честная рамка, чтобы не было расхождения между документом и реальностью.

**Проверено:**

- 166 автотестов проходят; сюда входят регрессии на шесть багов, которые
  реально доехали до канала (см. `backend/tests/test_signal_integrity.py`)
- конвейер парсинга, рейтинга и публикации работает на живых каналах
- watchdog доставляет отчёт (бот → при отсутствии chat_id в Saved Messages)

**Не проверено / ограничения:**

- **Эта инструкция ни разу не выполнялась на реальном сервере.** Первый прогон
  будет отладкой инструкции, а не деплоем по накатанному. Планируйте вечер, а не
  двадцать минут.
- **«Автономная работа» на Windows — не автономная.** Задачи в Task Scheduler
  требуют, чтобы ПК был включён, пользователь залогинен, а VPN/SOCKS5 подняты.
  Автономность появляется только после переезда на cron+systemd на VPS. До этого
  честная формулировка — «работает, пока включён рабочий ПК».
- **Единые точки отказа:** одна Telegram-сессия (её файл — SQLite с одним
  писателем), один SQLite-файл, один бот-токен. Любая из них останавливает поток
  сигналов целиком. Реплик нет.
- **Концентрация источников.** ~90% потока даёт одна группа каналов
  (beststocks / ricesignal — фактически один поставщик аналитики). Их формат —
  «направление + целевая цена»: вход и стоп считает уже наша сторона
  (`app/services/signal_levels.py`). Если этот источник закроется или сменит
  формат, поток обнулится. Диверсификация источников — открытая задача.
- **Трек-рекорд мал.** На 07.08.2026 измеренных закрытых сделок — 7 (после
  исключения фиктивных стопов и дубликатов, `scripts/fix_track_record_honesty.py`).
  Агрегированные проценты не публикуются до 30 сделок и это правильно.
- **WEF Score не валидирован.** `scripts/wef_validation.py` показывает, что
  выборки не хватает ни в одной полосе балла. До набора данных это оценка
  качества входных данных, а не проверенный предиктор.
- **Юр. соответствие 9/17 (53%).** Уведомление в РКН не подано, ПВК по 115-ФЗ не
  написаны, регламент KYC не оформлен (`scripts/fix_compliance_honesty.py`).

---

## 0. Перед началом

| Что | Где взять |
|-----|-----------|
| VPS в РФ, из реестра РКН | Timeweb Cloud (~530₽/мес) или RuVDS (349₽/мес). **Не Aeza** — под санкциями OFAC |
| Домен для API | Любой регистратор. Можно поддомен основного |
| `.env.production` | Уже создан в `backend/` — перенести на сервер как `.env` |
| Сессия Telegram | `backend/winextraflow_bot.session` — скопировать, иначе парсинг не поднимется |

Проверьте, что провайдер **в реестре хостинг-провайдеров РКН** (406-ФЗ): без этого
он не вправе оказывать услуги в РФ.

---

## 1. Подготовка сервера

```bash
# Ubuntu 24.04
sudo timedatectl set-timezone Europe/Moscow          # чтобы cron совпадал с рынком
sudo apt update && sudo apt install -y python3-venv python3-pip nginx sqlite3 \
     ffmpeg git certbot python3-certbot-nginx

sudo useradd -r -m -d /opt/winextraflow -s /bin/bash wef
sudo mkdir -p /opt/winextraflow /var/log/winextraflow /var/backups/winextraflow
sudo chown -R wef:wef /opt/winextraflow /var/log/winextraflow
sudo chmod 700 /var/backups/winextraflow            # в бэкапах лежит .env с секретами
```

`ffmpeg` обязателен — без него не рендерятся видео-клипы сигналов.

---

## 2. Код и зависимости

```bash
sudo -u wef -i
cd /opt/winextraflow
git clone <ваш-репозиторий> .            # или rsync с локальной машины
python3 -m venv venv
./venv/bin/pip install -U pip
./venv/bin/pip install -r backend/requirements.txt
```

---

## 3. Конфигурация

```bash
# Перенести .env.production с локальной машины (НЕ через git — он в .gitignore)
scp backend/.env.production wef@SERVER:/opt/winextraflow/backend/.env
scp backend/winextraflow_bot.session wef@SERVER:/opt/winextraflow/backend/

# На сервере:
chmod 600 /opt/winextraflow/backend/.env
```

Обязательно поправить в `.env`:

| Ключ | Значение |
|------|----------|
| `ADMIN_PASSWORD` | Заменить `CHANGE_ME_STRONG_PASSWORD` |
| `TELEGRAM_BOT_TOKEN` | **Перевыпустить у @BotFather** — прежний лежал в коде |
| `ALLOWED_ORIGINS` | Реальный origin фронта, без слеша на конце |
| `FRONTEND_URL`, `REFERRAL_BASE_URL` | Тот же домен |
| `SMTP_*` | Иначе письма верификации только в лог |
| `CRYPTO_PRIMARY` | `bybit` — Binance ушёл с рынка РФ и с этого IP может отвечать иначе, чем с вашей сети |
| `LLM_PARSE_PER_RUN` | `10` при пополненном OpenRouter, `0` или `1` без пополнения (без кредитов лимит 50 запросов/сутки на всю платформу) |
| `MT5_BRIDGE_TOKEN` | Нужен, только если мост MT5 слушает не 127.0.0.1. Сгенерировать: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `FRED_API_KEY` | Необязательно. Без него в экономическом календаре нет раздела США — и он честно об этом пишет |
| `ADMIN_TELEGRAM_CHAT_ID` | Куда watchdog присылает отчёт. Пусто — уйдёт в Saved Messages через Telethon |

`SECRET_KEY` и `ENCRYPTION_KEY` уже сгенерированы. **`ENCRYPTION_KEY` менять после
первого запуска нельзя** — им шифруются API-ключи биржевых аккаунтов.

`PAID_SUBSCRIPTIONS_ENABLED` не трогать — подписки отключены намеренно, до
подтверждённой статистики доходности. Все четыре точки оплаты отдают 503.

### Схема БД

```bash
cd /opt/winextraflow/backend && ../venv/bin/python scripts/migrate_schema.py --apply
```

Обязательно, и на первом запуске, и после каждого `git pull`. База создаётся через
`create_all`, который создаёт отсутствующие таблицы, но никогда не меняет
существующие: новая колонка в модели останется невидимой для уже созданной таблицы,
и запрос упадёт с «no such column» в рантайме, а не при импорте. Скрипт
идемпотентен — на актуальной схеме просто ничего не делает.

---

## 4. Проверка перед запуском

```bash
cd /opt/winextraflow/backend
../venv/bin/python -m pytest tests/ -q          # ожидаем 128 passed

# Доступны ли внешние API с этого IP
../venv/bin/python - <<'PY'
import asyncio, sys; sys.path.insert(0,'.')
from app.services.live_price import get_live_price
async def m():
    for t in ["SBER","BTCUSDT","EURUSD","NVDA"]:
        p = await get_live_price(t)
        print(f"{t:8} {'OK ' + str(p['price']) if p and p.get('price') else 'FAIL'}")
asyncio.run(m())
PY
```

⚠️ **Если BTCUSDT падает** — Binance блокирует российские IP. Это ожидаемо.
Решение: прописать в `.env` SOCKS5-прокси (`SOCKS5_HOST`/`PORT`/`USER`/`PASS`) —
тот же механизм, что используется для Telegram.

---

## 5. Сервис и nginx

```bash
sudo cp /opt/winextraflow/deploy/winextraflow.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now winextraflow
sudo systemctl status winextraflow

# nginx: подставьте свой домен вместо api.winextraflow.ru
sudo cp /opt/winextraflow/deploy/nginx.conf /etc/nginx/sites-available/winextraflow
sudo ln -sf /etc/nginx/sites-available/winextraflow /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# TLS
sudo certbot --nginx -d api.winextraflow.ru
sudo systemctl enable certbot.timer          # автопродление

curl -s https://api.winextraflow.ru/health   # {"status":"ok"}
```

---

## 6. Автоматика (cron)

```bash
sudo chmod +x /opt/winextraflow/deploy/backup.sh
sudo crontab -u wef /opt/winextraflow/deploy/crontab
sudo crontab -u wef -l
```

Что запускается:

| Задача | Расписание |
|--------|-----------|
| Парсинг каналов → публикация сигналов | каждые 30 мин |
| Контроль TP/SL открытых сигналов | :17 каждый час |
| **Виртуальные счета: открыть новое, закрыть закрывшееся** | :25 каждый час |
| Утренний обзор (разный текст в VIP и общий) | 09:00 |
| Обучающий тизер → ссылка на статью | Вт/Чт 15:00 |
| Посты про инструменты | Пн/Ср/Пт 14:00 |
| Статистика отклонённых + топ по WEF | Сб 12:00 |
| Недельный дайджест | Вс 19:00 |
| Бэкап БД и сессии | 03:30 |
| **watchdog — проверка, что всё вышеперечисленное реально сработало** | 10:00 |
| Валидация WEF Score и калибровки самооценки модели | 1-го числа 11:00 |

`paper_sync` стоит на `:25`, сразу после монитора на `:17` — закрытый сигнал в тот
же час становится сделкой с деньгами. Без этой задачи виртуальные счета не наберут
выборку, и трек-рекорд не двинется с места.

Обучающий тизер **не включать до переезда фронта на этот сервер**: пока сайт живёт
на `*.pages.dev`, каждый тизер ведёт на страницу, которую читатель из РФ не откроет.

Watchdog обязателен: без него любой из джобов может молча умереть. Он проверяет
свежесть логов, статистику конвейера за 24 ч и доступность внешних источников,
отдаёт отчёт в Telegram и возвращает код 1 при проблемах. В `--quiet` он всё
равно присылает один отчёт в сутки — иначе «тишина» неотличима от «watchdog
умер». Куда он пишет: `ADMIN_TELEGRAM_CHAT_ID`, а если он не задан — в Saved
Messages вашего аккаунта через Telethon-сессию.

```bash
# добавить в crontab, если ещё нет
0 10 * * * cd /opt/winextraflow/backend && python scripts/watchdog.py --quiet >> /var/log/winextraflow/watchdog.log 2>&1
```

---

## 7. Фронтенд

### ⚠️ Сначала прочитайте: `*.pages.dev` недоступен из России

Замер с рабочего подключения оператора (07.08.2026):

| Адрес | Напрямую | Через SOCKS5 |
|-------|----------|--------------|
| `winextraflow.pages.dev` | соединение разорвано (curl 000, 15 с) | **200** за 0.5 с |
| `fb91d1d3.winextraflow.pages.dev` | соединение разорвано | **200** за 0.4 с |
| `www.cloudflare.com` (контроль) | 200 | — |

DNS отвечает нормально (188.114.97.1). Сам Cloudflare открывается. Блокируется
именно хостнейм `*.pages.dev`. Деплой при этом успешный, страница отдаётся верная
(`<title>WinExtraFlow — AI Trading Signals</title>`).

Вывод: Pages нельзя использовать как основной хостинг фронта — целевая аудитория
его не откроет. Основной фронт отдаётся с того же VPS (см. `deploy/nginx.conf`,
блок «Frontend on the same host»), Pages остаётся зеркалом.

Дополнительный плюс: фронт и API на одном origin — нет CORS, `NEXT_PUBLIC_API_URL`
можно оставить пустым, и WebSocket-лента работает без отдельной настройки.

### Сборка и заливка на VPS (основной вариант)

```bash
# локально — пустой API URL, потому что фронт и API на одном домене
cd frontend
build-pages.bat
rsync -a --delete out/ root@SERVER:/var/www/winextraflow/
```

Перед сборкой **остановите dev-сервер**, если он запущен: `next build` пишет в ту же
`.next`, и работающий dev-сервер после этого падает с `Cannot find module './NNN.js'`.

Первым шагом `build-pages.bat` выгружает статьи в `public/lessons.json`
(`backend/scripts/export_lessons.py`). Это обязательно: за статикой нет бэкенда, и
без этого файла `/learn` откроется и напишет «материал не найден» — что читается
как сломанный контент, а не как отсутствующий.

### Cloudflare Pages (зеркало для не-РФ)

```bash
cd frontend
build-pages.bat https://api.winextraflow.ru
```

Затем **Workers & Pages → Create → Pages → Upload assets**, имя проекта
`winextraflow`, загрузить папку `frontend/out`.

> Динамические маршруты (`/dashboard/signals/[id]`) в статике недоступны —
> перед сборкой их временно убирают. Полный SSR-функционал требует хостинга
> Next.js на сервере.

---

## 8. Вебхуки

| Провайдер | URL | Где указать |
|-----------|-----|-------------|
| TradingView | `https://api.winextraflow.ru/api/v1/signals/webhook/tradingview` | В alert: JSON + `secret` из `.env` |
| ЮKassa | `https://api.winextraflow.ru/api/v1/payments/webhook` | ЛК → Интеграция → HTTP-уведомления (`payment.succeeded`, `payment.canceled`) |

---

## 9. После запуска — проверить

- [ ] `curl https://api.winextraflow.ru/health` → ok
- [ ] Регистрация и вход с фронта работают
- [ ] `ALLOWED_ORIGINS` совпадает с origin фронта (иначе CORS-ошибки в консоли)
- [ ] Внешние цены: MOEX / Binance / Yahoo (см. п.4)
- [ ] Через 30 мин: `tail /var/log/winextraflow/poller.log` — сигналы парсятся
- [ ] Утром: пришёл обзор в каналы
- [ ] Наутро: `ls /var/backups/winextraflow` — бэкап создан
- [ ] Страница `/contacts` доступна и содержит ИНН — обязательно для ЮKassa

---

## Обновление версии

```bash
sudo -u wef -i
cd /opt/winextraflow && git pull
./venv/bin/pip install -r backend/requirements.txt
cd backend
../venv/bin/python scripts/migrate_schema.py --apply   # НЕ пропускать
../venv/bin/python -m pytest tests/ -q
exit
sudo systemctl restart winextraflow
```

Порядок важен: миграция до перезапуска. Если сервис поднимется на старой схеме с
новым кодом, запросы к изменённым таблицам будут падать.

## Диагностика

```bash
sudo journalctl -u winextraflow -n 100 --no-pager
tail -f /var/log/winextraflow/api.err.log
tail -f /var/log/winextraflow/poller.log
sudo systemctl restart winextraflow
```
