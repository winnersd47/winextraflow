# Деплой WinExtraFlow

Фронтенд — статика на Cloudflare Pages. Бэкенд — FastAPI на российском VPS
(требование 152-ФЗ: персональные данные граждан РФ хранятся в РФ).

```
Пользователь → winextraflow.pages.dev (Cloudflare Pages, статика)
                        ↓ HTTPS
             api.winextraflow.ru (nginx + Let's Encrypt)
                        ↓ 127.0.0.1:8000
             uvicorn (systemd) + SQLite + cron-автоматика
```

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
| `ALLOWED_ORIGINS` | Реальный origin фронта, без слеша на конце |
| `FRONTEND_URL`, `REFERRAL_BASE_URL` | Тот же домен |
| `SMTP_*` | Иначе письма верификации только в лог |

`SECRET_KEY` и `ENCRYPTION_KEY` уже сгенерированы. **`ENCRYPTION_KEY` менять после
первого запуска нельзя** — им шифруются API-ключи биржевых аккаунтов.

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
| Контроль TP/SL открытых сигналов | каждый час |
| Утренний обзор + режим рынка | 09:00 |
| Недельный дайджест | Вс 19:00 |
| Статистика отклонённых + топ по WEF | Сб 12:00 |
| Посты про инструменты | Пн/Ср/Пт 14:00 |
| Бэкап БД и сессии | 03:30 |

---

## 7. Фронтенд (Cloudflare Pages)

Статичный экспорт должен знать адрес API:

```bash
# локально
cd frontend
echo "NEXT_PUBLIC_API_URL=https://api.winextraflow.ru" > .env.production.local
cp next.config.pages.js next.config.js        # output: "export"
NODE_OPTIONS=--max-old-space-size=4096 npx next build
cp next.config.js.standalone.bak next.config.js   # вернуть обычный конфиг
```

Затем в Cloudflare: **Workers & Pages → Create → Pages → Upload assets**,
имя проекта `winextraflow`, загрузить папку `frontend/out`.

> Динамические маршруты (`/dashboard/signals/[id]`) в статике недоступны —
> перед сборкой их временно убирают. Полный SSR-функционал требует хостинга
> Next.js на сервере (тогда фронт тоже на VPS, а не на Pages).

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
cd backend && ../venv/bin/python -m pytest tests/ -q
exit
sudo systemctl restart winextraflow
```

## Диагностика

```bash
sudo journalctl -u winextraflow -n 100 --no-pager
tail -f /var/log/winextraflow/api.err.log
tail -f /var/log/winextraflow/poller.log
sudo systemctl restart winextraflow
```
