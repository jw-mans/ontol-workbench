"""ORM-модель директории проекта. Директории позволяют организовать файлы в иерархическую структуру."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.file import File


class Directory(Base):
    """ORM-модель директории проекта. Директории позволяют организовать файлы в иерархическую структуру."""
    
    __tablename__ = 'directory'

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey('project.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    parent_directory_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        ForeignKey('directory.id', ondelete='CASCADE'),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    files: Mapped[list["File"]] = relationship(  # noqa: F821
        back_populates='directory', cascade='all, delete-orphan'
    )
    children: Mapped[list["Directory"]] = relationship(
        back_populates='parent', cascade='all, delete-orphan'
    )
    parent: Mapped["Directory"] = relationship(  # noqa: F821
        back_populates='children', remote_side=[id]
    )
    parent_directory = parent  # Алиас для удобства
