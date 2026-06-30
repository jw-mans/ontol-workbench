"""Точка входа FastAPI.

Поднимает приложение с CORS и healthcheck.

Запуск:
    uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import ai, build, files, projects
from app.auth.backend import auth_backend, fastapi_users
from app.config import settings
from app.db import engine
from app.queue import create_redis_pool
from app.schemas.user import UserCreate, UserRead, UserUpdate


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Пул Redis для постановки задач в очередь (arq). Один на процесс.
    app.state.redis = await create_redis_pool()
    yield
    # aclose() в redis-py>=5, close() — в более старых.
    closer = getattr(app.state.redis, 'aclose', app.state.redis.close)
    await closer()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

"""
Авторизация (fastapi-users)
"""

# POST /auth/cookie/login : POST /auth/cookie/logout
app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix='/auth/cookie', tags=['auth']
)
# POST /auth/register
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix='/auth',
    tags=['auth'],
)
# GET/PATCH /users/me : GET/PATCH/DELETE /users/{id}
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix='/users',
    tags=['users'],
)

"""
CRUD проектов и файлов
"""

app.include_router(projects.router)
app.include_router(files.router)


"""
Сборка проекта в диаграмму
"""

app.include_router(build.router)

"""
Опциональная AI-генерация связей
"""

app.include_router(ai.router)


@app.get('/')
async def root() -> dict:
    return {'service': settings.app_name, 'docs': '/docs'}


@app.get('/config')
async def config() -> dict:
    """Публичные флаги для фронтенда (какие фичи включены)."""
    return {'ai_enabled': settings.ai_enabled}


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
    except Exception as error:  # noqa: BLE001
        return {'database': 'error', 'detail': str(error)}
