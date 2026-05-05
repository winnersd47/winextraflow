# WinExtraFlow — Deploy Guide

## Шаг 1: Аренда VPS

### Рекомендуемые хостинги (для РФ)
| Хостинг | Тариф | Цена | Рекомендация |
|---------|-------|------|--------------|
| **Serverspace** (vStack) | 1 vCPU, 1 GB RAM, 25 GB SSD | ~700 руб/мес | Рекомендуемый |
| **Timeweb Cloud** | 1 vCPU, 1 GB RAM, 20 GB NVMe | ~550 руб/мес | Бюджетный |
| **Selectel** | 1 vCPU, 1 GB RAM, 10 GB | ~600 руб/мес | Надёжный |
| **Hetzner** (EU) | CX22, 2 vCPU, 4 GB RAM | €4.50/мес | Лучшее соотношение |

### Требования к серверу
- **ОС**: Ubuntu 22.04 / 24.04 LTS
- **RAM**: минимум 1 GB (рекомендуется 2 GB)
- **Disk**: 20 GB SSD
- **Порты**: 80, 443, 22 (SSH)

### При создании сервера:
1. Выбери Ubuntu 22.04 LTS
2. Запиши IP-адрес сервера
3. Запиши root пароль или добавь SSH ключ

---

## Шаг 2: Покупка домена

### Где купить
| Регистратор | Цена .com | Рекомендация |
|------------|-----------|-------------|
| **reg.ru** | ~1000 руб/год | Для РФ |
| **Namecheap** | ~$9/год | Международный |
| **Cloudflare Registrar** | ~$9/год | Без наценки |

### Рекомендуемые домены
- `winextraflow.com`
- `winextraflow.io`
- `wexflow.com`

### После покупки:
Настрой DNS A-запись:
```
Type: A
Name: @
Value: <IP_ВАШЕГО_СЕРВЕРА>
TTL: 300
```

И для www:
```
Type: A
Name: www
Value: <IP_ВАШЕГО_СЕРВЕРА>
TTL: 300
```

---

## Шаг 3: Подключение к серверу

```bash
ssh root@<IP_СЕРВЕРА>
```

---

## Шаг 4: Установка на сервере

Выполни на сервере:

```bash
# 1. Обновление системы
apt update && apt upgrade -y

# 2. Установка Docker
curl -fsSL https://get.docker.com | sh
apt install -y docker-compose-plugin

# 3. Установка Git
apt install -y git

# 4. Клонирование проекта
cd /opt
git clone <URL_ВАШЕГО_РЕПОЗИТОРИЯ> winextraflow
cd winextraflow

# 5. Создание production .env
cp .env.production.example .env

# 6. Отредактировать .env — заполнить свои ключи
nano .env
```

---

## Шаг 5: Настройка .env

```bash
# Заполни эти поля в .env:
POSTGRES_PASSWORD=<СИЛЬНЫЙ_ПАРОЛЬ>
SECRET_KEY=<СЛУЧАЙНАЯ_СТРОКА_32_СИМВОЛА>
APP_ENV=production
APP_DEBUG=false

# Домен
DOMAIN=winextraflow.com
FRONTEND_URL=https://winextraflow.com

# Telegram (если есть)
TELEGRAM_API_ID=<ваш_id>
TELEGRAM_API_HASH=<ваш_hash>

# Stripe (когда будет готов)
STRIPE_API_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

---

## Шаг 6: Запуск

```bash
# Первый запуск
docker compose -f docker-compose.yml up -d --build

# Проверка
docker compose ps
docker compose logs backend --tail 20

# Должно быть:
# postgres   ... Up (healthy)
# redis      ... Up (healthy)
# backend    ... Up
# frontend   ... Up
# nginx      ... Up
```

---

## Шаг 7: SSL сертификат (Let's Encrypt)

```bash
# Установка Certbot
apt install -y certbot

# Получение сертификата (остановить nginx)
docker compose stop nginx
certbot certonly --standalone -d winextraflow.com -d www.winextraflow.com

# Сертификаты будут в:
# /etc/letsencrypt/live/winextraflow.com/fullchain.pem
# /etc/letsencrypt/live/winextraflow.com/privkey.pem

# Перезапуск
docker compose up -d
```

---

## Шаг 8: Проверка

```bash
# Health check
curl https://winextraflow.com/health

# Должно вернуть:
# {"status":"ok","version":"0.1.0"}
```

Откройте в браузере: `https://winextraflow.com`

---

## Обновление проекта

```bash
cd /opt/winextraflow
git pull
docker compose up -d --build
```

---

## Мониторинг

```bash
# Логи
docker compose logs -f backend
docker compose logs -f frontend

# Ресурсы
docker stats

# Диск
df -h
```

---

## Бэкап базы данных

```bash
# Создать бэкап
docker compose exec postgres pg_dump -U winextraflow winextraflow > backup_$(date +%Y%m%d).sql

# Восстановить
docker compose exec -T postgres psql -U winextraflow winextraflow < backup_20260505.sql
```
