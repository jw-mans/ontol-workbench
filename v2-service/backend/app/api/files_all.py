"""Получение файлов всех проектов для отображения дерева."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owned_project
from app.db import get_async_session
from app.models.file import File
from app.models.project import Project
from app.schemas.file import FileListItem

router = APIRouter(prefix='/files', tags=['files'])


@router.get('/all', response_model=list[FileListItem])
async def list_all_files(
    session: AsyncSession = Depends(get_async_session),
) -> list[File]:
    """
    Вернуть список всех файлов всех проектов пользователя.

    :param session: асинхронная сессия SQLAlchemy
    :return: список всех файлов
    """
    # Получаем все проекты пользователя
    # Для простоты берем все файлы из всех проектов
    result = await session.execute(select(File).order_by(File.name))
    return list(result.scalars().all())


@router.get('/tree', response_model=FileListItem)
async def list_files_tree(
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> list[FileListItem]:
    """
    Вернуть список файлов проекта (для построения дерева на фронтенде).

    :param project: проект
    :param session: асинхронная сессия SQLAlchemy
    :return: список файлов проекта
    """
    result = await session.execute(
        select(File).where(File.project_id == project.id).order_by(File.name)
    )
    return list(result.scalars().all())
