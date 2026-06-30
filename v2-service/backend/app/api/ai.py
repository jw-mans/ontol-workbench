"""Опциональная AI-генерация связей (раздел hierarchy). Доступ — владельцу проекта.

Фича выключена по умолчанию (``settings.ai_enabled``). Когда включена, эндпоинт
ставит задачу воркеру (как и сборка) и ждёт результат. Возвращается предложение
связей + готовый к вставке фрагмент `.ontol` (файл не мутируется).
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import get_owned_project
from app.config import settings
from app.models.project import Project
from app.queue import AI_HIERARCHY
from app.schemas.ai import AIHierarchyRequest

router = APIRouter(prefix='/projects', tags=['ai'])


@router.post('/{project_id}/ai/hierarchy')
async def ai_hierarchy(
    data: AIHierarchyRequest,
    request: Request,
    project: Project = Depends(get_owned_project),
) -> dict:
    if not settings.ai_enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, 'AI feature is disabled'
        )

    redis = request.app.state.redis
    model = data.model or settings.ai_model
    job = await redis.enqueue_job(
        AI_HIERARCHY, str(project.id), data.entry, model
    )
    if job is None:
        raise HTTPException(status.HTTP_409_CONFLICT, 'AI job already in progress')
    try:
        return await job.result(
            timeout=settings.ai_timeout_seconds, poll_delay=0.5
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status.HTTP_504_GATEWAY_TIMEOUT, 'AI generation timed out'
        )
    except Exception as error:  # noqa: BLE001
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, f'AI generation failed: {error}'
        )
