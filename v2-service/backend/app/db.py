"""Асинхронный слой БД (SQLAlchemy 2.0).

``create_async_engine`` не открывает соединение на импорте — реальное
подключение происходит лениво при первом запросе, поэтому приложение
поднимается и без живого Postgres (healthcheck доступен).
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, future=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Базовый класс для всех ORM-моделей (модели появятся в Фазе 2)."""


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Зависимость FastAPI: выдаёт сессию БД на время запроса."""
    async with async_session_maker() as session:
        yield session
