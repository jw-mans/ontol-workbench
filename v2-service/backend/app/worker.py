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
    
    Если dir_id=None, собирает файлы из корня проекта (без директорий) и всех её поддиректорий.
    Возвращает словарь {относительный_путь: содержимое}.
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
        
        for dir_obj in dirs_list:
            await _collect_recursive(dir_obj.id, f'{prefix_internal}{dir_obj.name}/')
    
    # Собираем файлы из указанной директории и всех поддиректорий
    # Если dir_id=None, это означает, что мы хотим собрать файлы из корня (directory_id IS NULL)
    # и всех поддиректорий
    await _collect_recursive(dir_id, prefix)
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


async def _load_project_files(project_id: uuid.UUID) -> dict[str, str]:
    """Собрать все .ontol-файлы проекта и всех его подпроектов.
    
    Подпроекты materialize как подкаталоги (имя каталога = имя подпроекта).
    Возвращает словарь {относительный_путь: содержимое} для всех файлов дерева проектов.
    """
    collected: dict[str, str] = {}
    
    async with async_session_maker() as session:
        # Сначала собираем все директории проекта, чтобы понять структуру
        # Затем собираем файлы с учетом их местоположения в директориях
        
        # Собираем файлы из корня проекта (directory_id IS NULL)
        root_files = await session.execute(
            select(File).where(
                File.project_id == project_id,
                File.directory_id == None  # noqa: E711
            )
        )
        for f in root_files.scalars().all():
            if f.name.endswith('.ontol'):
                collected[f.name] = f.content
        
        # Собираем все директории проекта
        dirs_result = await session.execute(
            select(Directory).where(
                Directory.project_id == project_id
            )
        )
        directories = dirs_result.scalars().all()
        
        # Для каждой директории собираем файлы с правильным префиксом
        for dir_obj in directories:
            # Находим путь к директории
            dir_path = _get_directory_path(session, dir_obj)
            
            # Собираем файлы из этой директории
            dir_files = await session.execute(
                select(File).where(
                    File.project_id == project_id,
                    File.directory_id == dir_obj.id
                )
            )
            for f in dir_files.scalars().all():
                if f.name.endswith('.ontol'):
                    collected[f"{dir_path}/{f.name}"] = f.content
        
        # Добавляем подпроекты
        children = await session.execute(
            select(Project.id, Project.name).where(Project.parent_id == project_id)
        )
        for cid, cname in children.all():
            # Собираем файлы подпроекта с префиксом
            subproject_files = await _load_project_files_recursive(session, cid, cname)
            for path, content in subproject_files.items():
                if path.endswith('.ontol'):
                    collected[path] = content
    
    return collected


async def _load_project_files_recursive(session, project_id: uuid.UUID, prefix: str) -> dict[str, str]:
    """Рекурсивно собрать все .ontol-файлы проекта и подпроектов с префиксом."""
    collected: dict[str, str] = {}
    
    # Собираем файлы из корня подпроекта
    root_files = await session.execute(
        select(File).where(
            File.project_id == project_id,
            File.directory_id == None  # noqa: E711
        )
    )
    for f in root_files.scalars().all():
        if f.name.endswith('.ontol'):
            collected[f"{prefix}/{f.name}"] = f.content
    
    # Собираем файлы из директорий подпроекта
    dirs_result = await session.execute(
        select(Directory).where(
            Directory.project_id == project_id
        )
    )
    directories = dirs_result.scalars().all()
    
    for dir_obj in directories:
        dir_path = _get_directory_path_recursive(session, dir_obj, prefix)
        
        dir_files = await session.execute(
            select(File).where(
                File.project_id == project_id,
                File.directory_id == dir_obj.id
            )
        )
        for f in dir_files.scalars().all():
            if f.name.endswith('.ontol'):
                collected[f"{dir_path}/{f.name}"] = f.content
    
    # Рекурсивно добавляем подпроекты
    children = await session.execute(
        select(Project.id, Project.name).where(Project.parent_id == project_id)
    )
    for cid, cname in children.all():
        subproject_files = await _load_project_files_recursive(session, cid, f"{prefix}/{cname}")
        for path, content in subproject_files.items():
            if path.endswith('.ontol'):
                collected[path] = content
    
    return collected


def _get_directory_path(session, dir_obj: 'Directory') -> str:
    """Построить путь к директории от корня проекта."""
    path_parts = []
    current = dir_obj
    
    while current.parent_directory is not None:
        path_parts.append(current.name)
        current = current.parent_directory
    
    path_parts.append(current.name)
    return '/'.join(reversed(path_parts))


def _get_directory_path_recursive(session, dir_obj: 'Directory', prefix: str) -> str:
    """Построить путь к директории с учетом префикса."""
    path_parts = [prefix]
    current = dir_obj
    
    while current.parent_directory is not None:
        path_parts.append(current.name)
        current = current.parent_directory
    
    path_parts.append(current.name)
    return '/'.join(reversed(path_parts))


async def _load_subtree_tdl(root_id: str) -> dict[str, str]:
    """Собрать ``.tdl``-файлы проекта и всех подпроектов (v3).

    Ключи — ``<project_id>/<имя>`` (уникальны между подпроектами; сборка v3
    сливает по именам классов, не файлов).
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
    """Собрать проект: прочитать файлы из БД и отрендерить.

    Возвращает dict из ``BuildResult``. Язык берётся из проекта: v3 сливает
    ``.tdl`` всего поддерева в одну онтологию; v1 материализует только файлы
    текущего проекта (включая подпроекты как подкаталоги).
    """
    engine = await _load_engine(project_id)

    if engine == 'v3':
        files = await _load_subtree_tdl(project_id)
        if not files:
            return asdict(BuildResult(ok=False, error='Project has no files'))
        chosen = next(iter(files))  # v3 сливает всё поддерево, точка входа любая
    else:
        files = await _load_project_files(uuid.UUID(project_id))
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
