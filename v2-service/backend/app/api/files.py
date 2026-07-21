"""CRUD файлов внутри проекта. Доступ — только владельцу проекта."""

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owned_project
from app.db import get_async_session
from app.models.directory import Directory
from app.models.file import File
from app.models.project import Project
from app.schemas.file import (
    FileCreate,
    FileCreateWithPath,
    FileDetail,
    FileListItem,
    FileRead,
    FileRename,
    FileRenameWithPath,
    FileUpdate,
)

# Расширение файла определяется языком проекта: v1 -> .ontol, v3 -> .tdl.
_ENGINE_EXT = {'v1': '.ontol', 'v3': '.tdl'}
KNOWN_EXTS = tuple(_ENGINE_EXT.values())

router = APIRouter(prefix='/projects/{project_id}/files', tags=['files'])

# Логгер для отслеживания операций с файлами
logger = logging.getLogger(__name__)


def _with_ext(name: str, engine: str) -> str:
    """Привести имя к расширению языка проекта (чтобы не смешивать .ontol/.tdl)."""
    ext = _ENGINE_EXT.get(engine, '.ontol')
    for known in KNOWN_EXTS:
        if name.endswith(known):
            name = name[: -len(known)]
            break
    return name + ext


async def _get_directory_for_path(
    project: Project, path: str, session: AsyncSession
) -> Directory | None:
    """Получить директорию по пути, создавая промежуточные при необходимости."""
    if not path:
        return None

    parts = path.split('/')
    current_dir = None

    for part in parts:
        result = await session.execute(
            select(Directory)
            .where(
                Directory.project_id == project.id,
                Directory.parent_directory_id == current_dir,
                Directory.name == part,
            )
        )
        directory = result.scalars().first()
        if directory is None:
            directory = Directory(
                project_id=project.id,
                parent_directory_id=current_dir,
                name=part,
            )
            session.add(directory)
            await session.flush()
        current_dir = directory.id

    return current_dir


async def _get_file(
    file_id: uuid.UUID, project: Project, session: AsyncSession
) -> File:
    file = await session.get(File, file_id)
    if file is None or file.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'File not found')
    return file


@router.get('', response_model=list[FileListItem])
async def list_files(
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> list[File]:
    """
    Вернуть список файлов проекта (имя + id). Контент не возвращается, чтобы
    не перегружать API и фронтенд. 
    Контент запрашивается отдельным эндпоинтом (GET /projects/{project_id}/files/{file_id}).

    :param project: проект, к которому принадлежит пользователь
    :param session: асинхронная сессия SQLAlchemy

    :return: список файлов проекта (имя + id)
    """
    result = await session.execute(
        select(File).where(File.project_id == project.id).order_by(File.name)
    )
    return list(result.scalars().all())


@router.post('', response_model=FileRead, status_code=status.HTTP_201_CREATED)
async def create_file(
    data: FileCreateWithPath,
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
    directory_id: uuid.UUID | None = None,
) -> File:
    """
    Создать новый файл в проекте. Имя может содержать путь (например: "utils/helpers").
    Промежуточные директории создаются автоматически.

    :param data: параметры запроса (имя файла с путем, контент)
    :param project: проект, к которому принадлежит пользователь
    :param session: асинхронная сессия SQLAlchemy
    :param directory_id: UUID директории для файла (если указан, игнорирует путь в имени)
    
    :return: созданный файл
    """
    # Если указан directory_id, используем его, иначе парсим путь из имени
    if directory_id is not None:
        # Проверяем, что директория принадлежит проекту
        dir_result = await session.execute(
            select(Directory).where(
                Directory.id == directory_id,
                Directory.project_id == project.id,
            )
        )
        directory = dir_result.scalars().first()
        if directory is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Directory not found')
        directory_id = directory.id
        # Имя файла должно быть просто имя (без путей)
        name = data.name.strip()
        parts = name.split('/')
        if len(parts) > 1:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, 
                'File name cannot contain path when directory_id is specified'
            )
        filename = name
        
        # Проверяем, существует ли уже файл с таким именем в этой директории
        ext_filename = _with_ext(filename, project.engine)
        file_stmt = select(File).where(
            File.project_id == project.id,
            File.directory_id == directory_id,
            File.name == ext_filename,
        )
        file_result = await session.execute(file_stmt)
        existing_file = file_result.scalars().first()
        
        if existing_file:
            raise HTTPException(
                status.HTTP_409_CONFLICT, 'File with this name already exists in this directory'
            )
    else:
        # Разбираем путь и имя
        name = data.name.strip()
        parts = name.split('/')
        filename = parts[-1]
        dir_path = '/'.join(parts[:-1]) if len(parts) > 1 else ''

        # Получаем или создаем директорию
        directory_id = None
        if dir_path:
            directory_id = await _get_directory_for_path(project, dir_path, session)
        
        # Проверяем, существует ли уже файл с таким именем в этой директории
        ext_filename = _with_ext(filename, project.engine)
        file_stmt = select(File).where(
            File.project_id == project.id,
            File.directory_id == directory_id,
            File.name == ext_filename,
        )
        file_result = await session.execute(file_stmt)
        existing_file = file_result.scalars().first()
        
        if existing_file:
            raise HTTPException(
                status.HTTP_409_CONFLICT, 'File with this name already exists'
            )

    file = File(
        project_id=project.id,
        directory_id=directory_id,
        name=ext_filename,
        content=data.content,
    )
    session.add(file)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, 'File with this name already exists'
        )
    await session.refresh(file)
    
    # Логируем создание файла
    logger.info(
        "File created",
        extra={
            "project_id": str(project.id),
            "file_id": str(file.id),
            "file_name": file.name,
            "file_path": data.name,
        },
    )
    
    return file


@router.get('/{file_id}', response_model=FileRead)
async def get_file(
    file_id: uuid.UUID,
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> File:
    """
    Вернуть файл проекта по id. Контент возвращается, чтобы фронтенд мог его отобразить.

    :param file_id: UUID файла
    :param project: проект, к которому принадлежит пользователь
    :param session: асинхронная сессия SQLAlchemy

    :return: файл проекта (имя + id + контент)
    """
    return await _get_file(file_id, project, session)


@router.put('/{file_id}', response_model=FileRead)
async def update_file(
    file_id: uuid.UUID,
    data: FileUpdate,
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> File:
    """
    Обновить контент файла (автосейв из редактора).

    :param file_id: UUID файла
    :param data: параметры запроса (контент)
    :param project: проект, к которому принадлежит пользователь
    :param session: асинхронная сессия SQLAlchemy

    :return: обновленный файл
    """
    file = await _get_file(file_id, project, session)
    file.content = data.content
    await session.commit()
    await session.refresh(file)
    return file


@router.patch('/{file_id}', response_model=FileRead)
async def rename_file(
    file_id: uuid.UUID,
    data: FileRenameWithPath,
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> File:
    """
    Переименовать файл (может изменить путь).

    :param file_id: UUID файла
    :param data: параметры запроса (новое имя с путем)
    :param project: проект, к которому принадлежит пользователь
    :param session: асинхронная сессия SQLAlchemy

    :return: обновленный файл
    """
    file = await _get_file(file_id, project, session)
    
    # Разбираем новый путь
    new_name = data.name.strip()
    parts = new_name.split('/')
    filename = parts[-1]
    dir_path = '/'.join(parts[:-1]) if len(parts) > 1 else ''

    # Получаем или создаем новую директорию
    directory_id = None
    if dir_path:
        directory_id = await _get_directory_for_path(project, dir_path, session)

    file.directory_id = directory_id
    file.name = _with_ext(filename, project.engine)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, 'File with this name already exists'
        )
    await session.refresh(file)
    return file


@router.delete('/{file_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: uuid.UUID,
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """ 
    Удалить файл проекта по id. Контент не возвращается, чтобы фронтенд мог его отобразить.

    :param file_id: UUID файла
    :param project: проект, к которому принадлежит пользователь
    :param session: асинхронная сессия SQLAlchemy

    :return: None
    """
    file = await _get_file(file_id, project, session)
    await session.delete(file)
    await session.commit()
