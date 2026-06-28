"""Общие зависимости роутеров."""

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.backend import current_active_user
from app.db import get_async_session
from app.models.project import Project
from app.models.user import User


async def get_owned_project(
    project_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> Project:
    """Вернуть проект по id, только если он принадлежит текущему пользователю.

    Чужой/несуществующий проект -> 404 (не раскрываем факт существования).
    """
    project = await session.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Project not found')
    return project
