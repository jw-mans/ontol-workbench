"""Pydantic-схемы файла проекта."""

import os
import uuid
from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _validate_flat_name(value: str) -> str:
    """Имя файла — плоское (без путей/traversal)."""
    base = value.strip()
    if not base or base in ('.', '..') or base != os.path.basename(base):
        raise ValueError('Invalid file name')
    return base


def _validate_path_name(value: str) -> str:
    """Имя для создания файла/директории (может содержать путь)."""
    base = value.strip()
    if not base or base in ('.', '..'):
        raise ValueError('Invalid name')
    # Разрешаем пути, но запрещаем traversal
    parts = base.split('/')
    for part in parts:
        if part in ('', '.', '..'):
            raise ValueError('Invalid path component')
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


class FileCreateWithPath(BaseModel):
    """
    Параметры создания файла с поддержкой пути.
    
    :param name: имя файла (может содержать путь, например: "utils/helpers")
    :param content: текст файла (по умолчанию пустой)
    """
    name: str = Field(min_length=1, max_length=255)
    content: str = ''

    @field_validator('name')
    @classmethod
    def _path(cls, v: str) -> str:
        return _validate_path_name(v)


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


class FileRenameWithPath(BaseModel):
    """
    Параметры переименования файла с поддержкой пути.
    
    :param name: новое имя файла (может содержать путь)
    """
    name: str = Field(min_length=1, max_length=255)

    @field_validator('name')
    @classmethod
    def _path(cls, v: str) -> str:
        return _validate_path_name(v)


class DirectoryCreate(BaseModel):
    """
    Параметры создания директории.
    
    :param name: имя директории
    """
    name: str = Field(min_length=1, max_length=255)

    @field_validator('name')
    @classmethod
    def _name(cls, v: str) -> str:
        base = v.strip()
        if not base or base in ('.', '..'):
            raise ValueError('Invalid directory name')
        return base


class DirectoryRename(BaseModel):
    """
    Параметры переименования директории.
    
    :param name: новое имя директории
    """
    name: str = Field(min_length=1, max_length=255)

    @field_validator('name')
    @classmethod
    def _name(cls, v: str) -> str:
        base = v.strip()
        if not base or base in ('.', '..'):
            raise ValueError('Invalid directory name')
        return base


class DirectoryRead(BaseModel):
    """
    Схема чтения директории (в ответе API).

    :param id: UUID директории
    :param project_id: UUID проекта
    :param parent_directory_id: UUID родительской директории или None
    :param name: имя директории
    :param created_at: время создания
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    parent_directory_id: uuid.UUID | None
    name: str
    created_at: datetime


class DirectoryListItem(BaseModel):
    """
    Облегчённый элемент списка директорий — без вложенных данных.
    
    :param id: UUID директории
    :param project_id: UUID проекта
    :param parent_directory_id: UUID родительской директории или None
    :param name: имя директории
    :param created_at: время создания
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    parent_directory_id: uuid.UUID | None
    name: str
    created_at: datetime


class FileRead(BaseModel):
    """
    Схема чтения файла (в ответе API).

    :param id: UUID файла
    :param name: имя файла
    :param content: текст файла
    :param updated_at: время последнего обновления
    :param directory_id: UUID директории или None
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    content: str
    updated_at: datetime
    directory_id: uuid.UUID | None = None


class FileListItem(BaseModel):
    """
    Облегчённый элемент списка — без контента.
    
    :param id: UUID файла
    :param name: имя файла
    :param updated_at: время последнего обновления
    :param directory_id: UUID директории или None
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    updated_at: datetime
    directory_id: uuid.UUID | None = None


# Структура FileDetail не требуется - используем FileRead как полный файл с контентом.
# Для совместимости с кодом, который ожидает FileDetail, определяем его как алиас.
FileDetail = FileRead
