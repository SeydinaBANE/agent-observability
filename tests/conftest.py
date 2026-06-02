import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.auth import hash_api_key
from api.main import app
from core.database import Base, get_db
from core.models import Tenant

TEST_DATABASE_URL = os.getenv("AGENT_OBS_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/agent_obs")

test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSession() as session:
        try:
            yield session
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session")
def event_loop():
    import asyncio

    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True, scope="session")
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture
async def db_session():
    async with TestSession() as session:
        try:
            yield session
        finally:
            await session.close()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def test_tenant(db_session):
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant(name=f"Test-{uid}", slug=f"test-{uid}", api_key_hash=hash_api_key("test-key-12345678"))
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest.fixture
def api_key():
    return "test-key-12345678"
