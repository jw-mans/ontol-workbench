"""Бэкенд авторизации: httpOnly-cookie + JWT-стратегия.

Cookie хранит подписанный JWT (stateless). Если позже понадобятся отзываемые
серверные сессии — заменить ``JWTStrategy`` на ``DatabaseStrategy`` (потребует
таблицу токенов и миграцию).
"""

import uuid

from fastapi_users import FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    CookieTransport,
    JWTStrategy,
)

from app.auth.users import get_user_manager
from app.config import settings
from app.models.user import User

cookie_transport = CookieTransport(
    cookie_name='ontolauth',
    cookie_max_age=settings.access_token_lifetime_seconds,
    cookie_secure=settings.cookie_secure,
    cookie_httponly=True,
    cookie_samesite='lax',
)


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.secret,
        lifetime_seconds=settings.access_token_lifetime_seconds,
    )


auth_backend = AuthenticationBackend(
    name='cookie',
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

# Зависимость для защищённых эндпоинтов: текущий активный пользователь.
current_active_user = fastapi_users.current_user(active=True)
