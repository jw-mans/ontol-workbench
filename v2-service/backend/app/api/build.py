"""Сборка проекта в диаграмму. Доступ — только владельцу проекта."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owned_project
from app.config import settings
from app.db import get_async_session
from app.models.file import File
from app.models.project import Project
from app.schemas.build import BuildRequest
from app.services.render import build_project

router = APIRouter(prefix='/projects', tags=['build'])

DEFAULT_ENTRY = 'main.ontol'


@router.post('/{project_id}/build')
async def build(
    data: BuildRequest,
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Собрать проект: вернуть JSON, PlantUML и PNG (data-URL) точки входа.

    Ошибки парсинга/импорта возвращаются в поле ``error`` со статусом 200 —
    редактору удобнее показать их, чем ловить HTTP-ошибку.
    """
    result = await session.execute(
        select(File).where(File.project_id == project.id)
    )
    files = {f.name: f.content for f in result.scalars().all()}
    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Project has no files')

    entry = data.entry or (DEFAULT_ENTRY if DEFAULT_ENTRY in files else sorted(files)[0])

    build_result = await run_in_threadpool(
        build_project, files, entry, settings.plantuml_url
    )
    return asdict(build_result)
