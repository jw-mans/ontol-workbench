"""API endpoints для работы с онтологиями (v3/TDL)."""

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owned_project
from app.db import get_async_session
from app.models.directory import Directory
from app.models.file import File
from app.models.project import Project
from app.schemas.ontology import (
    OntologyBuildRequest,
    OntologyConcept,
    OntologyRelation,
    SemanticCheckResult,
    TDLFileCreateRequest,
)
from app.services.render_v3 import check_semantics, build_tdl_svg

router = APIRouter(prefix='/projects/{project_id}/ontologies', tags=['ontologies'])

logger = logging.getLogger(__name__)


async def _get_directory(
    directory_id: str, project: Project, session: AsyncSession
) -> Directory:
    """Получить директорию по ID, проверяя принадлежность проекту."""
    try:
        dir_uuid = uuid.UUID(directory_id)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Invalid directory ID format')
    
    result = await session.execute(
        select(Directory).where(
            Directory.id == dir_uuid,
            Directory.project_id == project.id,
        )
    )
    directory = result.scalars().first()
    if directory is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Directory not found')
    return directory


@router.post('/build', response_model=SemanticCheckResult)
async def build_ontology(
    data: OntologyBuildRequest,
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> SemanticCheckResult:
    """
    Построить онтологию из выбранных понятий и связей.
    
    Создаёт TDL-файл с описанием выбранных понятий и связей.
    Директория определяет область видимости онтологии.
    
    :param data: параметры построения онтологии
    :param project: проект, к которому принадлежит пользователь
    :param session: асинхронная сессия SQLAlchemy
    
    :return: SemanticCheckResult с результатами проверки
    """
    # Получаем директорию
    directory = await _get_directory(data.directory_id, project, session)
    
    # Генерируем TDL-код из выбранных понятий и связей
    tdl_content = _generate_tdl_from_ontology(data)
    
    # Проверяем семантическую целостность
    warnings, planarity, error = check_semantics([tdl_content], strict=False)
    
    if error:
        logger.error(
            "Semantic check failed",
            extra={
                "project_id": str(project.id),
                "directory_id": data.directory_id,
                "error": error,
            }
        )
        return SemanticCheckResult(
            is_valid=False,
            warnings=[],
            planarity=None,
            error=error
        )
    
    # Если всё валидно, создаем файл
    try:
        file = File(
            project_id=project.id,
            directory_id=directory.id,
            name=data.file_name if data.file_name.endswith('.tdl') else f"{data.file_name}.tdl",
            content=tdl_content,
        )
        session.add(file)
        await session.commit()
        await session.refresh(file)
        
        logger.info(
            "Ontology file created",
            extra={
                "project_id": str(project.id),
                "directory_id": data.directory_id,
                "file_id": str(file.id),
                "file_name": file.name,
            }
        )
        
        return SemanticCheckResult(
            is_valid=True,
            warnings=warnings if warnings else [],
            planarity=planarity,
            error=None
        )
    except Exception as e:
        await session.rollback()
        logger.error(
            "Failed to create ontology file",
            extra={
                "project_id": str(project.id),
                "directory_id": data.directory_id,
                "error": str(e),
            }
        )
        return SemanticCheckResult(
            is_valid=False,
            warnings=[],
            planarity=None,
            error=f"Failed to create file: {str(e)}"
        )


@router.post('/check', response_model=SemanticCheckResult)
async def check_ontology_semantics(
    data: TDLFileCreateRequest,
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> SemanticCheckResult:
    """
    Проверить семантическую целостность TDL-контента.
    
    Не создаёт файл, только проверяет валидность.
    Полезно для валидации в реальном времени в редакторе.
    
    :param data: параметры TDL-файла
    :param project: проект, к которому принадлежит пользователь
    :param session: асинхронная сессия SQLAlchemy
    
    :return: SemanticCheckResult с результатами проверки
    """
    # Проверяем семантическую целостность
    warnings, planarity, error = check_semantics([data.content], strict=False)
    
    return SemanticCheckResult(
        is_valid=error is None,
        warnings=warnings if warnings else [],
        planarity=planarity,
        error=error
    )


@router.post('/check_directory', response_model=SemanticCheckResult)
async def check_directory_semantics(
    directory_id: str,
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> SemanticCheckResult:
    """
    Проверить семантическую целостность всех TDL-файлов в директории.
    
    Объединяет все .tdl файлы в директории и проверяет целостность.
    Не рендерит SVG, только проверяет модель.
    
    :param directory_id: UUID директории
    :param project: проект, к которому принадлежит пользователь
    :param session: асинхронная сессия SQLAlchemy
    
    :return: SemanticCheckResult с результатами проверки
    """
    directory = await _get_directory(directory_id, project, session)
    
    # Собираем все .tdl файлы в директории
    result = await session.execute(
        select(File).where(
            File.project_id == project.id,
            File.directory_id == directory.id,
            File.name.endswith('.tdl'),
        )
    )
    tdl_files = result.scalars().all()
    
    if not tdl_files:
        return SemanticCheckResult(
            is_valid=True,
            warnings=["No .tdl files in directory"],
            planarity=None,
            error=None
        )
    
    # Собираем контент всех файлов
    tdl_contents = [f.content for f in tdl_files]
    
    # Проверяем семантическую целостность
    warnings, planarity, error = check_semantics(tdl_contents, strict=False)
    
    return SemanticCheckResult(
        is_valid=error is None,
        warnings=warnings if warnings else [],
        planarity=planarity,
        error=error
    )


def _generate_tdl_from_ontology(data: OntologyBuildRequest) -> str:
    """Генерирует TDL-код из выбранных понятий и связей."""
    lines = []
    
    # Генерируем понятия
    for concept in data.concepts:
        lines.extend(_generate_concept(concept))
        lines.append("")
    
    # Генерируем связи
    for relation in data.relations:
        lines.extend(_generate_relation(relation))
        lines.append("")
    
    return "\n".join(lines).strip()


def _generate_concept(concept: OntologyConcept) -> list[str]:
    """Генерирует TDL-код для одного понятия."""
    lines = []
    
    # Определяем тип и открываем блок
    type_map = {
        "class": "КЛАСС",
        "interface": "ИНТЕРФЕЙС",
        "data_type": "ТИП_ДАННЫХ",
        "enum": "ПЕРЕЧИСЛЕНИЕ",
        "template": "ШАБЛОН",
    }
    
    type_keyword = type_map.get(concept.type, "КЛАСС")
    lines.append(f"{type_keyword} {concept.name}")
    
    # Добавляем абстрактность
    if concept.is_abstract and concept.type == "class":
        lines[-1] = f"{type_keyword} {concept.name} АБСТРАКТНЫЙ"
    
    # Генерируем атрибуты
    if concept.attributes:
        lines.append("АТРИБУТЫ")
        for attr in concept.attributes:
            lines.append(f"  {attr}")
    
    # Генерируем операции
    if concept.operations:
        lines.append("ОПЕРАЦИИ")
        for op in concept.operations:
            lines.append(f"  {op}")
    
    lines.append("КОНЕЦ " + type_keyword.split()[0])
    return lines


def _generate_relation(relation: OntologyRelation) -> list[str]:
    """Генерирует TDL-код для одной связи."""
    type_map = {
        "generalization": "ОБОБЩЕНИЕ",
        "association": "АССОЦИАЦИЯ",
        "aggregation": "АГРЕГАЦИЯ",
        "composition": "КОМПОЗИЦИЯ",
        "dependency": "ЗАВИСИМОСТЬ",
        "realization": "РЕАЛИЗАЦИЯ",
    }
    
    type_keyword = type_map.get(relation.relation_type, "АССОЦИАЦИЯ")
    
    if relation.relation_type == "generalization":
        # Обобщение: Specific -> General
        return [f"{type_keyword} {relation.from_concept} -> {relation.to_concept}"]
    
    elif relation.relation_type == "dependency":
        # Зависимость: Client -> Supplier [стереотип]
        return [f"{type_keyword} {relation.from_concept} -> {relation.to_concept} use"]
    
    elif relation.relation_type == "realization":
        # Реализация: Implementer -> Interface
        return [f"{type_keyword} {relation.from_concept} -> {relation.to_concept}"]
    
    else:
        # Ассоциация, агрегация, композиция
        # A [multiplicity] : role -- B [multiplicity] : role [ИМЯ "name"]
        line = f"{type_keyword}"
        
        from_part = relation.from_concept
        if relation.multiplicity_from:
            from_part += f" {relation.multiplicity_from}"
        if relation.name:
            from_part += f" : {relation.from_concept.lower()}"
        
        to_part = relation.to_concept
        if relation.multiplicity_to:
            to_part += f" {relation.multiplicity_to}"
        if relation.name:
            to_part += f" : {relation.to_concept.lower()}"
        
        line += f" {from_part} -- {to_part}"
        
        if relation.name:
            line += f' ИМЯ "{relation.name}"'
        
        return [line]
