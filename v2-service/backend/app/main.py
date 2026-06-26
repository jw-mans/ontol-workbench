"""Точка входа FastAPI (Фаза 0 — скелет).

Поднимает приложение с CORS и healthcheck. Роутеры auth/projects/files/build
подключаются в следующих фазах (см. ../../docs/V2_PLAN.md).

Запуск:
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.db import engine

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.get('/')
async def root() -> dict:
    return {'service': settings.app_name, 'docs': '/docs'}


@app.get('/health')
async def health() -> dict:
    """Лёгкий healthcheck — не трогает БД."""
    return {'status': 'ok'}


@app.get('/health/db')
async def health_db() -> dict:
    """Проверка соединения с БД (нужен живой Postgres)."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text('SELECT 1'))
        return {'database': 'ok'}
    except Exception as error:  # noqa: BLE001 — вернуть статус, а не падать
        return {'database': 'error', 'detail': str(error)}
