"""Асинхронный слой БД (SQLAlchemy 2.0)."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    future=True,
    # Валидируем соединение перед выдачей из пула: отсеивает «мёртвые» коннекты
    # после простоя/перезапуска Postgres (иначе — периодические "connection closed").
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,  # пересоздавать коннект раз в 30 мин (не копим долгоживущие)
)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Базовый класс для всех ORM-моделей."""


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Зависимость FastAPI: выдаёт сессию БД на время запроса."""
    async with async_session_maker() as session:
        yield session
