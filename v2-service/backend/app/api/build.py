"""Сборка проекта в диаграмму. Доступ — только владельцу проекта.

Сама сборка выполняется фоновым воркером (arq): эндпоинт ставит задачу в очередь
и дожидается результата (await — событийный цикл не блокируется). Тяжёлый рендер
и стек ontol живут в воркере, не в процессе API.
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import get_owned_project
from app.config import settings
from app.models.project import Project
from app.queue import RENDER_BUILD
from app.schemas.build import BuildRequest

router = APIRouter(prefix='/projects', tags=['build'])


@router.post('/{project_id}/build')
async def build(
    data: BuildRequest,
    request: Request,
    project: Project = Depends(get_owned_project),
) -> dict:
    """Собрать проект и вернуть JSON, PlantUML и PNG (data-URL) точки входа.

    Ошибки парсинга/импорта и пустой проект приходят в поле ``error`` со
    статусом 200 — редактору удобнее показать их, чем ловить HTTP-ошибку.
    """
    redis = request.app.state.redis
    job = await redis.enqueue_job(RENDER_BUILD, str(project.id), data.entry)
    if job is None:
        raise HTTPException(status.HTTP_409_CONFLICT, 'Build already in progress')
    try:
        return await job.result(
            timeout=settings.build_timeout_seconds, poll_delay=0.2
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status.HTTP_504_GATEWAY_TIMEOUT, 'Build timed out'
        )
    except Exception as error:  # noqa: BLE001
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, f'Build failed: {error}'
        )
