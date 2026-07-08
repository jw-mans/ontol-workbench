"""CRUD проектов. Доступ — только владельцу."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owned_project
from app.auth.backend import current_active_user
from app.db import get_async_session
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate

router = APIRouter(prefix='/projects', tags=['projects'])


@router.get('', response_model=list[ProjectRead])
async def list_projects(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[Project]:
    """
    Вернуть список проектов текущего пользователя (имя + id). Контент не возвращается, чтобы
    не перегружать API и фронтенд. 
    Контент запрашивается отдельным эндпоинтом (GET /projects/{project_id}/files).

    :param user: текущий пользователь
    :param session: асинхронная сессия SQLAlchemy

    :return: список проектов текущего пользователя (имя + id)
    """
    result = await session.execute(
        select(Project).where(Project.owner_id == user.id).order_by(Project.name)
    )
    return list(result.scalars().all())


@router.post('', response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> Project:
    """
    Создать новый проект. Имя обязано быть уникальным для пользователя.

    :param data: параметры запроса (имя проекта)
    :param user: текущий пользователь
    :param session: асинхронная сессия SQLAlchemy

    :return: созданный проект
    """
    project = Project(owner_id=user.id, name=data.name)
    session.add(project)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, 'Project with this name already exists'
        )
    await session.refresh(project)
    return project


@router.get('/{project_id}', response_model=ProjectRead)
async def get_project(project: Project = Depends(get_owned_project)) -> Project:
    """
    Вернуть проект по id, только если он принадлежит текущему пользователю.
    
    :param project: проект, к которому принадлежит пользователь
    
    :return: проект
    """
    return project


@router.patch('/{project_id}', response_model=ProjectRead)
async def rename_project(
    data: ProjectUpdate,
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> Project:
    """
    Переименовать проект. Имя обязано быть уникальным для пользователя.

    :param data: параметры запроса (новое имя проекта)
    :param project: проект, к которому принадлежит пользователь
    :param session: асинхронная сессия SQLAlchemy

    :return: обновленный проект
    """
    project.name = data.name
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, 'Project with this name already exists'
        )
    await session.refresh(project)
    return project


@router.delete('/{project_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """
    Удалить проект по id. Контент не возвращается, чтобы фронтенд мог его отобразить.

    :param project: проект, к которому принадлежит пользователь
    :param session: асинхронная сессия SQLAlchemy

    :return: None
    """
    await session.delete(project)
    await session.commit()
