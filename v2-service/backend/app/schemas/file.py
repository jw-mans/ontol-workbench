"""Pydantic-схемы файла проекта."""

import os
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _validate_flat_name(value: str) -> str:
    """Имя файла — плоское (без путей/traversal)."""
    base = value.strip()
    if not base or base in ('.', '..') or base != os.path.basename(base):
        raise ValueError('Invalid file name')
    return base


class FileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    content: str = ''

    @field_validator('name')
    @classmethod
    def _flat(cls, v: str) -> str:
        return _validate_flat_name(v)


class FileUpdate(BaseModel):
    content: str


class FileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    content: str
    updated_at: datetime


class FileListItem(BaseModel):
    """Облегчённый элемент списка — без контента."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    updated_at: datetime
