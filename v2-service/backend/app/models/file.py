"""ORM-модель файла проекта. Контент `.ontol` хранится прямо в БД (TEXT)."""

import uuid
from datetime import datetime

from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class File(Base):
    __tablename__ = 'file'
    __table_args__ = (
        UniqueConstraint('project_id', 'name', name='uq_file_project_name'),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey('project.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default='')
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project: Mapped['Project'] = relationship(  # noqa: F821
        back_populates='files'
    )
