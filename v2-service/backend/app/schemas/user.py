"""Pydantic-схемы пользователя (на базе схем fastapi-users)."""

import uuid

from fastapi_users import schemas


class UserRead(schemas.BaseUser[uuid.UUID]):
    """
    Схема чтения пользователя (в ответе API).

    :param id: UUID пользователя
    :param email: email пользователя
    :param is_active: активен ли пользователь
    :param is_superuser: является ли пользователь суперпользователем
    :param is_verified: подтверждён ли email пользователя
    :param display_name: отображаемое имя пользователя (необязательное)
    """
    display_name: str | None = None


class UserCreate(schemas.BaseUserCreate):
    """
    Схема создания пользователя (в запросе API).

    :param email: email пользователя
    :param password: пароль пользователя
    :param display_name: отображаемое имя пользователя (необязательное)
    """
    display_name: str | None = None


class UserUpdate(schemas.BaseUserUpdate):
    """
    Схема обновления пользователя (в запросе API).

    :param password: новый пароль пользователя (необязательный)
    :param display_name: новое отображаемое имя пользователя (необязательное)
    """
    display_name: str | None = None
