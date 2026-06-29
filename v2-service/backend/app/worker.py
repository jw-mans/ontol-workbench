"""Фоновый воркер (arq).

Запуск:  arq app.worker.WorkerSettings

Задачи сами читают файлы проекта из БД по ``project_id`` (единый источник правды —
не таскаем контент через очередь). Блокирующая работа (парсинг, HTTP к PlantUML,
запрос к LLM) уводится в поток, чтобы не блокировать событийный цикл воркера.

- ``render_build`` — сборка диаграммы (всегда включена).
- ``ai_hierarchy`` — опциональная AI-генерация связей (требует [ai] + Ollama).
"""

import asyncio
import uuid
from dataclasses import asdict

from sqlalchemy import select

from app.config import settings
from app.db import async_session_maker
from app.models.file import File
from app.queue import AI_HIERARCHY, RENDER_BUILD, redis_settings
from app.services.ai import AIHierarchyResult, generate_hierarchy
from app.services.render import BuildResult, build_project

DEFAULT_ENTRY = 'main.ontol'


async def _load_files(project_id: str) -> dict[str, str]:
    async with async_session_maker() as session:
        result = await session.execute(
            select(File).where(File.project_id == uuid.UUID(project_id))
        )
        return {f.name: f.content for f in result.scalars().all()}


def _choose_entry(entry: str | None, files: dict[str, str]) -> str:
    return entry or (DEFAULT_ENTRY if DEFAULT_ENTRY in files else sorted(files)[0])


async def render_build(ctx: dict, project_id: str, entry: str | None) -> dict:
    """Собрать проект: прочитать его файлы из БД и отрендерить.

    Возвращает dict из ``BuildResult`` (ok/json/puml/png_url/warnings/error) —
    arq сохранит его как результат задачи в Redis.
    """
    files = await _load_files(project_id)
    if not files:
        return asdict(BuildResult(ok=False, error='Project has no files'))

    chosen = _choose_entry(entry, files)
    # build_project блокирующий — в отдельный поток.
    build_result = await asyncio.to_thread(
        build_project, files, chosen, settings.plantuml_url
    )
    return asdict(build_result)


async def ai_hierarchy(
    ctx: dict, project_id: str, entry: str | None, model: str
) -> dict:
    """Предложить связи (раздел hierarchy) для точки входа через LLM (Ollama)."""
    files = await _load_files(project_id)
    if not files:
        return asdict(AIHierarchyResult(ok=False, error='Project has no files'))

    chosen = _choose_entry(entry, files)
    # generate_hierarchy блокирующий (парсинг + запрос к LLM) — в поток.
    result = await asyncio.to_thread(
        generate_hierarchy, files, chosen, model, settings.ollama_url
    )
    return asdict(result)


# Имена функций совпадают с контрактами очереди (enqueue_job по имени).
assert render_build.__name__ == RENDER_BUILD
assert ai_hierarchy.__name__ == AI_HIERARCHY


class WorkerSettings:
    functions = [render_build, ai_hierarchy]
    redis_settings = redis_settings()
    # Раз в N секунд воркер пишет в Redis health-check ключ; его читает
    # `arq app.worker.WorkerSettings --check` (healthcheck контейнера).
    health_check_interval = 30
