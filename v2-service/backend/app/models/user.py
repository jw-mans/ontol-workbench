"""ORM-модель пользователя.

Базовые поля (id: UUID, email, hashed_password, is_active, is_superuser,
is_verified) даёт ``SQLAlchemyBaseUserTableUUID`` из fastapi-users. Добавляем
своё необязательное отображаемое имя.
"""

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
