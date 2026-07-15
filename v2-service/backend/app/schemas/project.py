"""Pydantic-схемы проекта."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    """
    Параметры создания проекта.

    :param name: имя проекта
    :param parent_id: UUID родительского проекта (None — корневой проект)
    """
    name: str = Field(min_length=1, max_length=100)
    parent_id: uuid.UUID | None = None


class ProjectUpdate(BaseModel):
    """
    Параметры обновления проекта.
    
    :param name: новое имя проекта
    """
    name: str = Field(min_length=1, max_length=100)


class ProjectRead(BaseModel):
    """
    Схема чтения проекта (в ответе API).
    
    :param id: UUID проекта
    :param parent_id: UUID родительского проекта (None — корень)
    :param name: имя проекта
    :param created_at: время создания
    :param updated_at: время последнего обновления
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    created_at: datetime
    updated_at: datetime
