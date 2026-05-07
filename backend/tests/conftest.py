"""Shared test fixtures — in-memory SQLite, test client, user helpers."""

import asyncio
import os
import uuid
from typing import AsyncGenerator

# Set test env BEFORE any app imports
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["APP_DEBUG"] = "false"
os.environ["APP_ENV"] = "test"
os.environ["SECRET_KEY"] = "test-secret"

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Now import app modules (they'll use the env vars above)
import app.database as db_module
from app.database import Base, get_db

# Create a single test engine and patch the module-level references
test_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

# Monkeypatch the database module so lifespan/services use test engine
db_module.engine = test_engine
db_module.async_session = TestSession


async def override_get_db():
    async with TestSession() as session:
        try:
            yield session
        finally:
            await session.close()


from app.main import app  # noqa: E402

app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_db():
    """Create all tables before each test, drop after."""
    import app.models  # noqa: F401 — register all models
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSession() as session:
        yield session


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def seed_referrer(db: AsyncSession) -> str:
    """Create a seed user to provide referral codes for test registrations."""
    import secrets
    from app.models.user import User
    code = secrets.token_urlsafe(8)
    db.add(User(
        email=f"seed_{uuid.uuid4().hex[:6]}@test.com",
        username=f"seed_{uuid.uuid4().hex[:6]}",
        hashed_password="$2b$12$dummy",
        referral_code=code,
    ))
    await db.commit()
    return code


@pytest.fixture
async def registered_user(client: AsyncClient, seed_referrer: str) -> dict:
    resp = await client.post("/api/v1/auth/register", json={
        "email": f"test_{uuid.uuid4().hex[:8]}@test.com",
        "username": f"user_{uuid.uuid4().hex[:8]}",
        "password": "testpass123",
        "referral_code": seed_referrer,
    })
    assert resp.status_code == 201, f"Register failed: {resp.text}"
    return resp.json()


@pytest.fixture
async def auth_headers(client: AsyncClient, registered_user: dict) -> dict:
    resp = await client.post("/api/v1/auth/login", json={
        "email": registered_user["email"],
        "password": "testpass123",
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
async def premium_auth_headers(client: AsyncClient, auth_headers: dict, registered_user: dict, db: AsyncSession) -> dict:
    """Grant premium to the test user and return auth headers."""
    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == registered_user["email"]))).scalar_one()
    from app.services.premium import grant_premium_days
    await grant_premium_days(db, user, 30)
    return auth_headers
