"""Точка входа FastAPI.

Поднимает приложение с CORS и healthcheck. Подключает роутеры auth (Фаза 1) и
projects/files CRUD (Фаза 2). Роутер build добавится в Фазе 3
(см. ../../docs/V2_PLAN.md).

Запуск:
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import files, projects
from app.auth.backend import auth_backend, fastapi_users
from app.config import settings
from app.db import engine
from app.schemas.user import UserCreate, UserRead, UserUpdate

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# --- Авторизация (fastapi-users) ------------------------------------------- #
# POST /auth/cookie/login · POST /auth/cookie/logout
app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix='/auth/cookie', tags=['auth']
)
# POST /auth/register
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix='/auth',
    tags=['auth'],
)
# GET/PATCH /users/me · GET/PATCH/DELETE /users/{id}
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix='/users',
    tags=['users'],
)

# --- CRUD проектов и файлов (Фаза 2) --------------------------------------- #
app.include_router(projects.router)
app.include_router(files.router)


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
