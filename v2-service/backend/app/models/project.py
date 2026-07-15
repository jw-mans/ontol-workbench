"""ORM-модель проекта.

Проект — узел дерева: держит свои файлы и может иметь подпроекты (``parent_id``).
Сборка узла сливает его ``.tdl`` и ``.tdl`` всех потомков в одну онтологию.
"""

import uuid
from datetime import datetime

from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Project(Base):
    """
    ORM-модель проекта (узел дерева проектов/подпроектов).

    :param id: UUID проекта
    :param owner_id: UUID владельца проекта (пользователя)
    :param parent_id: UUID родительского проекта или None (корень)
    :param name: имя проекта
    :param created_at: время создания проекта
    :param updated_at: время последнего обновления проекта
    :param files: список файлов проекта
    :param children: список подпроектов
    """

    __tablename__ = 'project'
    # Имя уникально среди соседей (одного родителя) у одного владельца.
    __table_args__ = (
        UniqueConstraint(
            'owner_id', 'parent_id', 'name', name='uq_project_owner_parent_name'
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        ForeignKey('project.id', ondelete='CASCADE'),
        nullable=True,
        index=True,
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
    children: Mapped[list['Project']] = relationship(
        back_populates='parent', cascade='all, delete-orphan'
    )
    parent: Mapped['Project | None'] = relationship(
        back_populates='children', remote_side=[id]
    )
