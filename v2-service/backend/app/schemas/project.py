"""Pydantic-схемы проекта."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    """
    Параметры создания проекта.

    :param name: имя проекта
    :param parent_id: UUID родительского проекта (None — корневой проект)
    :param engine: язык корневого проекта ('v1'/'v3'); у подпроекта игнорируется
        (наследуется от родителя). По умолчанию 'v1'.
    """
    name: str = Field(min_length=1, max_length=100)
    parent_id: uuid.UUID | None = None
    engine: Literal['v1', 'v3'] = 'v1'


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
    :param engine: язык проекта ('v1'/'v3')
    :param name: имя проекта
    :param created_at: время создания
    :param updated_at: время последнего обновления
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parent_id: uuid.UUID | None
    engine: str
    name: str
    created_at: datetime
    updated_at: datetime
