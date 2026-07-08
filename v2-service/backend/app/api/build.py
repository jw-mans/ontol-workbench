"""
Сборка проекта в диаграмму. Доступ — только владельцу проекта.

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
    """
    Собрать проект и вернуть JSON, PlantUML и PNG (data-URL) точки входа.

    Один активный билд на проект: 
    1. короткий Redis-лок (SET NX EX) схлопывает спам-клики и 
       параллельные сборки одного проекта; 
    2. Лок самоочищается по TTL, если API упадёт посреди билда; 
    3. каждая сборка — свежая (уникальный job id), без риска 
       отдать устаревший кэш результата.

    :param data: параметры запроса (точка входа, URL PlantUML)
    :param request: объект запроса FastAPI
    :param project: проект, к которому принадлежит пользователь
    
    :return: словарь с результатом сборки (ok/json/puml/png_url/warnings/error)
    """
    redis = request.app.state.redis
    
    lock_key = f'build:lock:{project.id}'
    if not await redis.set(
        lock_key, '1', ex=settings.build_timeout_seconds + 10, nx=True
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, 'Build already in progress')
    try:
        job = await redis.enqueue_job(RENDER_BUILD, str(project.id), data.entry)
        return await job.result(
            timeout=settings.build_timeout_seconds, poll_delay=0.2
        )
    except asyncio.TimeoutError:
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, 'Build timed out')
    except HTTPException:
        raise
    except Exception as error:  # noqa: BLE001
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, f'Build failed: {error}'
        )
    finally:
        await redis.delete(lock_key)
