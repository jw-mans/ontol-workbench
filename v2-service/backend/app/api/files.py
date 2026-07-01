"""CRUD файлов внутри проекта. Доступ — только владельцу проекта."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owned_project
from app.db import get_async_session
from app.models.file import File
from app.models.project import Project
from app.schemas.file import (
    FileCreate,
    FileListItem,
    FileRead,
    FileRename,
    FileUpdate,
)

ONTOL_EXT = '.ontol'
# Расширения известных движков: .ontol → v1 (PlantUML), .tdl → v3 (Graphviz).
KNOWN_EXTS = (ONTOL_EXT, '.tdl')

router = APIRouter(prefix='/projects/{project_id}/files', tags=['files'])


def _with_ext(name: str) -> str:
    """Гарантировать расширение движка: .tdl оставляем, иначе по умолчанию .ontol."""
    return name if name.endswith(KNOWN_EXTS) else name + ONTOL_EXT


async def _get_file(
    file_id: uuid.UUID, project: Project, session: AsyncSession
) -> File:
    file = await session.get(File, file_id)
    if file is None or file.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'File not found')
    return file


@router.get('', response_model=list[FileListItem])
async def list_files(
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> list[File]:
    result = await session.execute(
        select(File).where(File.project_id == project.id).order_by(File.name)
    )
    return list(result.scalars().all())


@router.post('', response_model=FileRead, status_code=status.HTTP_201_CREATED)
async def create_file(
    data: FileCreate,
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> File:
    file = File(
        project_id=project.id, name=_with_ext(data.name), content=data.content
    )
    session.add(file)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, 'File with this name already exists'
        )
    await session.refresh(file)
    return file


@router.get('/{file_id}', response_model=FileRead)
async def get_file(
    file_id: uuid.UUID,
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> File:
    return await _get_file(file_id, project, session)


@router.put('/{file_id}', response_model=FileRead)
async def update_file(
    file_id: uuid.UUID,
    data: FileUpdate,
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> File:
    """Обновить контент файла (автосейв из редактора)."""
    file = await _get_file(file_id, project, session)
    file.content = data.content
    await session.commit()
    await session.refresh(file)
    return file


@router.patch('/{file_id}', response_model=FileRead)
async def rename_file(
    file_id: uuid.UUID,
    data: FileRename,
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> File:
    """Переименовать файл (имя обязано быть уникальным в проекте)."""
    file = await _get_file(file_id, project, session)
    file.name = _with_ext(data.name)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, 'File with this name already exists'
        )
    await session.refresh(file)
    return file


@router.delete('/{file_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: uuid.UUID,
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    file = await _get_file(file_id, project, session)
    await session.delete(file)
    await session.commit()
