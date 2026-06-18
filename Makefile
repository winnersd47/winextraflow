# ============================================================
# WinExtraFlow — Makefile
# ============================================================

.PHONY: help up down dev-api dev-web migrate rollback test lint seed logs clean

COMPOSE = docker compose
BACKEND = cd backend &&
FRONTEND = cd frontend &&

help:
	@echo "WinExtraFlow — команды разработки"
	@echo ""
	@echo "  make up          Запустить весь стек (Docker)"
	@echo "  make down        Остановить стек"
	@echo "  make infra       Только postgres + redis"
	@echo "  make dev-api     Backend hot-reload :8200"
	@echo "  make dev-web     Frontend dev :3200"
	@echo "  make migrate     alembic upgrade head"
	@echo "  make rollback    alembic downgrade -1"
	@echo "  make test        pytest"
	@echo "  make lint        ruff + mypy"
	@echo "  make seed        Заполнить начальными данными"
	@echo "  make logs        Логи всех сервисов"
	@echo "  make clean       Удалить volumes + containers"

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

infra:
	$(COMPOSE) up -d postgres redis

dev-api:
	$(BACKEND) uvicorn app.main:app --reload --host 0.0.0.0 --port 8200

dev-web:
	$(FRONTEND) npm run dev

migrate:
	$(BACKEND) alembic upgrade head

rollback:
	$(BACKEND) alembic downgrade -1

migration:
	$(BACKEND) alembic revision --autogenerate -m "$(msg)"

test:
	$(BACKEND) pytest tests/ -v --cov=app --cov-report=term-missing

lint:
	$(BACKEND) ruff check app/ && mypy app/

lint-fix:
	$(BACKEND) ruff check --fix app/ && ruff format app/

seed:
	$(BACKEND) python -c "from app.services.seed_data import seed; import asyncio; asyncio.run(seed())"

logs:
	$(COMPOSE) logs -f --tail=100

logs-api:
	$(COMPOSE) logs -f backend

clean:
	$(COMPOSE) down -v --remove-orphans

install:
	$(BACKEND) pip install -r requirements.txt
	$(FRONTEND) npm install

build:
	$(COMPOSE) build

reset: clean up migrate seed
	@echo "Стек пересоздан и заполнен данными"

health:
	@curl -s http://localhost:8200/health | python -m json.tool
