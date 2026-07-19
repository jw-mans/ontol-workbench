"""
Фоновый воркер (arq).

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
from app.models.project import Project
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


async def _load_engine(project_id: str) -> str | None:
    async with async_session_maker() as session:
        project = await session.get(Project, uuid.UUID(project_id))
        return project.engine if project else None


async def _load_subtree_tdl(root_id: str) -> dict[str, str]:
    """Собрать ``.tdl``-файлы проекта и всех подпроектов (v3).

    Ключи — ``<project_id>/<имя>`` (уникальны между подпроектами; сборка v3
    сливает по именам классов, а не файлов).
    """
    collected: dict[str, str] = {}
    async with async_session_maker() as session:
        pending = [uuid.UUID(root_id)]
        seen: set[uuid.UUID] = set()
        while pending:
            pid = pending.pop()
            if pid in seen:
                continue
            seen.add(pid)
            files = await session.execute(select(File).where(File.project_id == pid))
            for f in files.scalars().all():
                if f.name.endswith('.tdl'):
                    collected[f'{pid}/{f.name}'] = f.content
            children = await session.execute(
                select(Project.id).where(Project.parent_id == pid)
            )
            pending.extend(children.scalars().all())
    return collected


async def _load_subtree_ontol(root_id: str) -> dict[str, str]:
    """Собрать ``.ontol``-файлы дерева с относительными путями (v1).

    Подпроект материализуется как подкаталог (имя каталога = имя подпроекта),
    поэтому ``import ... from "Подпроект/файл.ontol"`` резолвится по пути.
    Файлы корня лежат на верхнем уровне (без префикса).
    """
    collected: dict[str, str] = {}
    async with async_session_maker() as session:
        pending = [(uuid.UUID(root_id), '')]
        seen: set[uuid.UUID] = set()
        while pending:
            pid, prefix = pending.pop()
            if pid in seen:
                continue
            seen.add(pid)
            files = await session.execute(select(File).where(File.project_id == pid))
            for f in files.scalars().all():
                if f.name.endswith('.ontol'):
                    collected[f'{prefix}{f.name}'] = f.content
            children = await session.execute(
                select(Project.id, Project.name).where(Project.parent_id == pid)
            )
            for cid, cname in children.all():
                pending.append((cid, f'{prefix}{cname}/'))
    return collected


def _choose_entry(entry: str | None, files: dict[str, str]) -> str:
    return entry or (DEFAULT_ENTRY if DEFAULT_ENTRY in files else sorted(files)[0])


async def render_build(ctx: dict, project_id: str, entry: str | None) -> dict:
    """Собрать проект: прочитать файлы дерева из БД и отрендерить.

    Возвращает dict из ``BuildResult``. Язык берётся из проекта: v3 сливает
    ``.tdl`` всего поддерева в одну онтологию; v1 материализует дерево как
    подкаталоги (импорты между подпроектами резолвятся по пути).
    """
    engine = await _load_engine(project_id)

    if engine == 'v3':
        files = await _load_subtree_tdl(project_id)
        if not files:
            return asdict(BuildResult(ok=False, error='Project has no files'))
        chosen = next(iter(files))  # v3 сливает всё поддерево, точка входа любая
    else:
        own = await _load_files(project_id)
        if not own:
            return asdict(BuildResult(ok=False, error='Project has no files'))
        chosen = _choose_entry(entry, own)  # точка входа — файл корня
        files = await _load_subtree_ontol(project_id)

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
    # Раз в N секунд воркер пишет в Redis health-check ключ; 
    # его читает `arq app.worker.WorkerSettings --check` (healthcheck контейнера).
    health_check_interval = 30
    # Результат билда (инлайн-SVG / base64-PNG) тяжёлый — API забирает его сразу,
    # поэтому храним в Redis недолго, чтобы очередь не пухла.
    keep_result = 60
    # Рендер CPU-bound: много одновременных задач в одном процессе лишь толкаются
    # об GIL. Держим на процесс немного, а пропускную способность растим репликами
    # воркера (WORKER_REPLICAS в docker-compose).
    max_jobs = 4
