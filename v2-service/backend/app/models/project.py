"""ORM-модель проекта — каталог `.ontol`-файлов, принадлежащий пользователю."""

import uuid
from datetime import datetime

from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Project(Base):
    __tablename__ = 'project'
    __table_args__ = (
        UniqueConstraint('owner_id', 'name', name='uq_project_owner_name'),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    files: Mapped[list['File']] = relationship(  # noqa: F821
        back_populates='project', cascade='all, delete-orphan'
    )
