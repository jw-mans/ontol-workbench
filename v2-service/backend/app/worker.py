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
from app.models.directory import Directory
from app.models.file import File
from app.models.project import Project
from app.queue import AI_HIERARCHY, RENDER_BUILD, redis_settings
from app.services.ai import AIHierarchyResult, generate_hierarchy
from app.services.render import BuildResult, build_project

DEFAULT_ENTRY = 'main.ontol'


async def _collect_files_with_dirs(
    session,
    project_id: uuid.UUID,
    prefix: str,
    dir_id: uuid.UUID | None = None,
) -> dict[str, str]:
    """Собрать .ontol/.tdl файлы из директории и всех поддиректорий.
    
    Возвращает словарь {относительный_путь: содержимое}.
    Используется как в _load_files, так и в _load_subtree_ontol.
    """
    collected: dict[str, str] = {}
    
    async def _collect_recursive(dir_id_internal: uuid.UUID | None, prefix_internal: str) -> None:
        files_result = await session.execute(
            select(File).where(
                File.project_id == project_id,
                File.directory_id == dir_id_internal
            )
        )
        files_list = files_result.scalars().all()
        
        # Отладка: выводим собраны ли файлы
        if not collected and not files_list and dir_id_internal is None:
            # Это первый вызов (корневая директория), проверим, есть ли файлы вообще
            all_files = await session.execute(select(File).where(File.project_id == project_id))
            all_list = all_files.scalars().all()
            print(f"DEBUG _collect_files_with_dirs: project_id={project_id}, total files={len(all_list)}")
            for f in all_list:
                print(f"  - file: name='{f.name}', directory_id={f.directory_id}")
        
        for f in files_list:
            if f.name.endswith(('.ontol', '.tdl')):
                collected[f'{prefix_internal}{f.name}'] = f.content
        
        dirs_result = await session.execute(
            select(Directory).where(
                Directory.project_id == project_id,
                Directory.parent_directory_id == dir_id_internal
            )
        )
        dirs_list = dirs_result.scalars().all()
        if dirs_list:
            print(f"DEBUG _collect_recursive: dir_id={dir_id_internal}, found {len(dirs_list)} directories")
        
        for dir_obj in dirs_list:
            await _collect_recursive(dir_obj.id, f'{prefix_internal}{dir_obj.name}/')
    
    await _collect_recursive(dir_id, prefix)
    print(f"DEBUG _collect_files_with_dirs: collected {len(collected)} files: {list(collected.keys())}")
    return collected


async def _load_files(project_id: str) -> dict[str, str]:
    """Собрать все .ontol-файлы проекта с относительными путями.
    
    Возвращает словарь {относительный_путь: содержимое}, где относительный путь
    учитывает директорию, в которой лежит файл (если файл в корне - путь пустой).
    """
    async with async_session_maker() as session:
        return await _collect_files_with_dirs(
            session, uuid.UUID(project_id), ''
        )


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
    
    Файлы внутри проекта могут быть в директориях (через directory_id),
    они собираются с относительными путями от проекта.
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
            
            # Собираем файлы этого проекта (включая все его директории)
            files = await _collect_files_with_dirs(session, pid, prefix)
            # Фильтруем только .ontol файлы (для v3 используется другая функция)
            for path, content in files.items():
                if path.endswith('.ontol'):
                    collected[path] = content
            
            # Добавляем подпроекты в очередь
            children = await session.execute(
                select(Project.id, Project.name).where(Project.parent_id == pid)
            )
            for cid, cname in children.all():
                pending.append((cid, f'{prefix}{cname}/'))
    return collected


def _choose_entry(entry: str | None, files: dict[str, str]) -> str:
    """Выбрать точку входа.
    
    Если entry указан явно - используем его.
    Иначе ищем main.ontol, если нет - берем первую доступную точку входа.
    
    Важно: entry может быть указана как имя файла (для обратной совместимости)
    или как полный путь (для файлов в поддиректориях).
    """
    if entry:
        # Проверяем, есть ли entry в files как есть
        if entry in files:
            return entry
        # Если нет, пробуем добавить .ontol (если его нет)
        if not entry.endswith('.ontol') and f'{entry}.ontol' in files:
            return f'{entry}.ontol'
        # Если файл в поддиректории, entry может быть просто именем
        # Ищем файл с таким именем в любом пути
        basename = entry if entry.endswith('.ontol') else f'{entry}.ontol'
        for path in files:
            if path.endswith(basename):
                return path
    
    # Дефолт: ищем main.ontol
    if DEFAULT_ENTRY in files:
        return DEFAULT_ENTRY
    
    # Если main.ontol нет, ищем его с расширением
    for path in files:
        if path.endswith('.ontol'):
            return path
    
    # Если ничего не найдено, возвращаем первую доступную точку входа
    return sorted(files.keys())[0] if files else ''


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
