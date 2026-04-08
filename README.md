# WinExtraFlow

Trading signal aggregator platform with AI rating, auto-trading, and strategy marketplace.

## Quick Start

```bash
# Copy environment config
cp .env.example .env

# Start infrastructure
docker-compose up -d

# Run backend
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# Run frontend
cd frontend
npm install
npm run dev
```

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic
- **Database**: PostgreSQL 16, Redis
- **Frontend**: Next.js 14, TypeScript, Tailwind CSS
- **Infrastructure**: Docker Compose
