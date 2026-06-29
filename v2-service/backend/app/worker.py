"""Фоновый воркер сборки (arq).

Запуск:  arq app.worker.WorkerSettings

Задача ``render_build`` сама читает файлы проекта из БД по ``project_id`` (единый
источник правды — не таскаем контент через очередь), затем рендерит ядром ontol.
Рендер блокирующий (парсинг + HTTP к PlantUML), поэтому уводим его в поток, чтобы
не блокировать событийный цикл воркера.
"""

import asyncio
import uuid
from dataclasses import asdict

from sqlalchemy import select

from app.config import settings
from app.db import async_session_maker
from app.models.file import File
from app.queue import RENDER_BUILD, redis_settings
from app.services.render import BuildResult, build_project

DEFAULT_ENTRY = 'main.ontol'


async def render_build(ctx: dict, project_id: str, entry: str | None) -> dict:
    """Собрать проект: прочитать его файлы из БД и отрендерить.

    Возвращает dict из ``BuildResult`` (ok/json/puml/png_url/warnings/error) —
    arq сохранит его как результат задачи в Redis.
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(File).where(File.project_id == uuid.UUID(project_id))
        )
        files = {f.name: f.content for f in result.scalars().all()}

    if not files:
        return asdict(BuildResult(ok=False, error='Project has no files'))

    chosen = entry or (DEFAULT_ENTRY if DEFAULT_ENTRY in files else sorted(files)[0])
    
    build_result = await asyncio.to_thread( # блокирующий => в отдельный поток
        build_project, files, chosen, settings.plantuml_url
    )
    return asdict(build_result)


assert render_build.__name__ == RENDER_BUILD


class WorkerSettings:
    functions = [render_build]
    redis_settings = redis_settings()
    # Раз в N секунд воркер пишет в Redis health-check ключ; его читает
    # `arq app.worker.WorkerSettings --check` (healthcheck контейнера).
    health_check_interval = 30
