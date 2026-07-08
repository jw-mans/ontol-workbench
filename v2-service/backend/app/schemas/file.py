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
    """
    Параметры создания файла.
    
    :param name: имя файла (без путей)
    :param content: текст файла (по умолчанию пустой)
    """
    name: str = Field(min_length=1, max_length=255)
    content: str = ''

    @field_validator('name')
    @classmethod
    def _flat(cls, v: str) -> str:
        return _validate_flat_name(v)


class FileUpdate(BaseModel):
    """
    Параметры обновления файла.
    
    :param content: текст файла (по умолчанию пустой)
    """
    content: str


class FileRename(BaseModel):
    """
    Параметры переименования файла.
    
    :param name: новое имя файла (без путей)
    """
    name: str = Field(min_length=1, max_length=255)

    @field_validator('name')
    @classmethod
    def _flat(cls, v: str) -> str:
        return _validate_flat_name(v)


class FileRead(BaseModel):
    """
    Схема чтения файла (в ответе API).

    :param id: UUID файла
    :param name: имя файла
    :param content: текст файла
    :param updated_at: время последнего обновления
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    content: str
    updated_at: datetime


class FileListItem(BaseModel):
    """
    Облегчённый элемент списка — без контента.
    
    :param id: UUID файла
    :param name: имя файла
    :param updated_at: время последнего обновления
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    updated_at: datetime
