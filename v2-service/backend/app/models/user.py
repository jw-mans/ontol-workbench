"""ORM-модель пользователя."""

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    """
    ORM-модель пользователя.

    :param id: UUID пользователя
    :param email: email пользователя
    :param hashed_password: хэш пароля пользователя
    :param is_active: активен ли пользователь
    :param is_superuser: является ли пользователь суперпользователем
    :param is_verified: подтверждён ли email пользователя
    :param display_name: отображаемое имя пользователя (необязательное)
    """
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
