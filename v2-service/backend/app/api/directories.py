"""CRUD директорий внутри проекта. Доступ — только владельцу проекта."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owned_project
from app.db import get_async_session
from app.models.directory import Directory
from app.models.file import File
from app.models.project import Project
from app.schemas.file import DirectoryCreate, DirectoryListItem, DirectoryRead, DirectoryRename

router = APIRouter(prefix='/projects/{project_id}/directories', tags=['directories'])


async def _get_directory(
    directory_id: uuid.UUID, project: Project, session: AsyncSession
) -> Directory:
    directory = await session.get(Directory, directory_id)
    if directory is None or directory.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Directory not found')
    return directory


@router.get('', response_model=list[DirectoryListItem])
async def list_directories(
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
    parent_id: uuid.UUID | None = None,
) -> list[Directory]:
    """
    Вернуть список директорий проекта.

    :param project: проект, к которому принадлежит пользователь
    :param session: асинхронная сессия SQLAlchemy
    :param parent_id: UUID родительской директории (для корневых передать NULL)

    :return: список директорий
    """
    result = await session.execute(
        select(Directory)
        .where(
            Directory.project_id == project.id,
            Directory.parent_directory_id == parent_id,
        )
        .order_by(Directory.name)
    )
    return list(result.scalars().all())


@router.post('', response_model=DirectoryRead, status_code=status.HTTP_201_CREATED)
async def create_directory(
    data: DirectoryCreate,
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
    parent_id: uuid.UUID | None = None,
) -> Directory:
    """
    Создать новую директорию в проекте.

    :param data: параметры запроса (имя директории)
    :param project: проект, к которому принадлежит пользователь
    :param session: асинхронная сессия SQLAlchemy
    :param parent_id: UUID родительской директории (для корневой передать NULL)

    :return: созданная директория
    """
    # Проверяем, существует ли директория с таким именем у этого родителя
    stmt = select(Directory).where(
        Directory.project_id == project.id,
        Directory.parent_directory_id == parent_id,
        Directory.name == data.name.strip(),
    )
    result = await session.execute(stmt)
    existing = result.scalars().first()
    
    if existing:
        raise HTTPException(
            status.HTTP_409_CONFLICT, 'Directory with this name already exists in this location'
        )
    
    directory = Directory(
        project_id=project.id,
        parent_directory_id=parent_id,
        name=data.name,
    )
    session.add(directory)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, 'Directory with this name already exists'
        )
    await session.refresh(directory)
    return directory


@router.get('/{directory_id}', response_model=DirectoryRead)
async def get_directory(
    directory_id: uuid.UUID,
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> Directory:
    """
    Вернуть директорию проекта по id.

    :param directory_id: UUID директории
    :param project: проект, к которому принадлежит пользователь
    :param session: асинхронная сессия SQLAlchemy

    :return: директория проекта
    """
    return await _get_directory(directory_id, project, session)


@router.patch('/{directory_id}', response_model=DirectoryRead)
async def rename_directory(
    directory_id: uuid.UUID,
    data: DirectoryRename,
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> Directory:
    """
    Переименовать директорию.

    :param directory_id: UUID директории
    :param data: параметры запроса (новое имя)
    :param project: проект, к которому принадлежит пользователь
    :param session: асинхронная сессия SQLAlchemy

    :return: обновленная директория
    """
    directory = await _get_directory(directory_id, project, session)
    directory.name = data.name
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, 'Directory with this name already exists'
        )
    await session.refresh(directory)
    return directory


@router.delete('/{directory_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_directory(
    directory_id: uuid.UUID,
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """
    Удалить директорию проекта по id. Удаление разрешено только для пустых директорий.

    :param directory_id: UUID директории
    :param project: проект, к которому принадлежит пользователь
    :param session: асинхронная сессия SQLAlchemy

    :return: None
    """
    directory = await _get_directory(directory_id, project, session)

    # Проверяем, что директория пустая (нет файлов и поддиректорий)
    files_result = await session.execute(
        select(File).where(File.directory_id == directory.id)
    )
    if files_result.scalars().first() is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, 'Directory is not empty'
        )

    children_result = await session.execute(
        select(Directory).where(Directory.parent_directory_id == directory.id)
    )
    if children_result.scalars().first() is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, 'Directory is not empty'
        )

    await session.delete(directory)
    await session.commit()
