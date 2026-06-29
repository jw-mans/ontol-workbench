"""Общие фикстуры тестов backend.

БД — in-memory SQLite (StaticPool, одно соединение → данные живут в рамках теста);
внешний Postgres не нужен. Модели ontol используют кроссбазовый GUID, поэтому
схема создаётся и на SQLite. Запросы к API идут in-process через ASGITransport.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — регистрирует модели на Base.metadata
from app.db import Base, get_async_session
from app.main import app

PASSWORD = 'password123'


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(
        'sqlite+aiosqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
def session_maker(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def client(session_maker):
    """HTTP-клиент к приложению с БД, подменённой на тестовую."""

    async def override_get_session():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_async_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as c:
        yield c
    app.dependency_overrides.clear()


async def _register_and_login(c: AsyncClient) -> str:
    email = f'user_{uuid.uuid4().hex[:8]}@test.com'
    r = await c.post('/auth/register', json={'email': email, 'password': PASSWORD})
    assert r.status_code == 201, r.text
    r = await c.post(
        '/auth/cookie/login', data={'username': email, 'password': PASSWORD}
    )
    assert r.status_code in (200, 204), r.text
    return email


@pytest_asyncio.fixture
async def auth_client(client):
    """Клиент с зарегистрированным и залогиненным пользователем."""
    client.email = await _register_and_login(client)
    return client


@pytest_asyncio.fixture
async def other_client(session_maker):
    """Второй залогиненный пользователь (для проверок изоляции доступа)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as c:
        await _register_and_login(c)
        yield c
