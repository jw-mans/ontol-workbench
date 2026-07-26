"""API endpoints для работы с онтологиями (v3/TDL)."""

import uuid
import logging
from typing import Any, Dict, Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
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
    TDLGenerateRequest,
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
    
    logger.info(f"Looking for directory {dir_uuid} in project {project.id}")
    result = await session.execute(
        select(Directory).where(
            Directory.id == dir_uuid,
            Directory.project_id == project.id,
        )
    )
    directory = result.scalars().first()
    if directory is None:
        logger.error(f"Directory {dir_uuid} not found in project {project.id}")
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Directory not found')
    logger.info(f"Found directory {directory.id} with name '{directory.name}'")
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
            error=None,
            file_id=str(file.id),
            file_name=file.name
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
    request: dict = Body(...),
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> SemanticCheckResult:
    """
    Проверить семантическую целостность всех TDL-файлов в директории.
    
    Объединяет все .tdl файлы в директории и проверяет целостность.
    Не рендерит SVG, только проверяет модель.
    
    :param request: тело запроса с directory_id
    :param project: проект, к которому принадлежит пользователь
    :param session: асинхронная сессия SQLAlchemy
    
    :return: SemanticCheckResult с результатами проверки
    """
    import pprint
    
    directory_id = request.get('directory_id')
    
    # Для корневых файлов directory_id может быть None
    if not directory_id:
        logger.info(f"Checking root directory (directory_id is None) for project {project.id}")
        # Собираем все .tdl файлы из корня (directory_id IS NULL)
        result = await session.execute(
            select(File).where(
                File.project_id == project.id,
                File.directory_id == None,  # noqa: E711
                File.name.endswith('.tdl'),
            )
        )
    else:
        logger.info(f"Checking directory {directory_id} for project {project.id}")
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
    logger.info(f"Found {len(tdl_files)} .tdl files in directory {directory_id or 'root'}")
    for f in tdl_files:
        logger.info(f"  - File: {f.name}, directory_id: {f.directory_id}, content length: {len(f.content)}")
    
    # Debug: print ALL files in project for diagnosis
    all_files_result = await session.execute(
        select(File).where(File.project_id == project.id)
    )
    all_files = all_files_result.scalars().all()
    logger.info(f"Total files in project {project.id}: {len(all_files)}")
    for f in all_files:
        logger.info(f"  - ALL File: {f.name}, directory_id: {f.directory_id}")
    
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


@router.post('/generate_tdl', response_model=str)
async def generate_tdl_from_ontology(
    data: TDLGenerateRequest,
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> str:
    """
    Сгенерировать TDL-код из выбранных понятий и связей.
    
    Не создаёт файл, только генерирует TDL-код для превью.
    
    :param data: параметры генерации TDL
    :param project: проект, к которому принадлежит пользователь
    :param session: асинхронная сессия SQLAlchemy
    
    :return: TDL-код в виде строки
    """
    return _generate_tdl_from_ontology(
        OntologyBuildRequest(
            directory_id=data.directory_id,
            concepts=data.concepts,
            relations=data.relations,
        )
    )


@router.post('/analyze_directory', response_model=SemanticCheckResult)
async def analyze_diagram_in_directory(
    request: dict = Body(...),
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> SemanticCheckResult:
    """
    Анализировать диаграмму относительно корневой директории (для TDL файлов).
    
    Рендерит каждый .tdl файл отдельно и проверяет семантическую целостность
    всей директории. Предоставляет детальную информацию о планарности графа.
    
    :param request: тело запроса с directory_id
    :param project: проект, к которому принадлежит пользователь
    :param session: асинхронная сессия SQLAlchemy
    
    :return: SemanticCheckResult с результатами анализа
    """
    import pprint
    
    directory_id = request.get('directory_id')
    
    # Для корневых файлов directory_id может быть None
    if not directory_id:
        logger.info(f"Checking root directory (directory_id is None) for project {project.id}")
        # Собираем все .tdl файлы из корня (directory_id IS NULL)
        result = await session.execute(
            select(File).where(
                File.project_id == project.id,
                File.directory_id == None,  # noqa: E711
                File.name.endswith('.tdl'),
            )
        )
    else:
        logger.info(f"Checking directory {directory_id} for project {project.id}")
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
    logger.info(f"Found {len(tdl_files)} .tdl files in directory {directory_id or 'root'}")
    for f in tdl_files:
        logger.info(f"  - File: {f.name}, directory_id: {f.directory_id}, content length: {len(f.content)}")
    
    # Debug: print ALL files in project for diagnosis
    all_files_result = await session.execute(
        select(File).where(File.project_id == project.id)
    )
    all_files = all_files_result.scalars().all()
    logger.info(f"Total files in project {project.id}: {len(all_files)}")
    for f in all_files:
        logger.info(f"  - ALL File: {f.name}, directory_id: {f.directory_id}")
    
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


@router.post('/get_all_concepts')
async def get_all_concepts_from_directory(
    request: dict = Body(...),
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """
    Получить все понятия из всех TDL-файлов в директории.
    
    Используется для конструктора онтологий - показывает список
    существующих понятий, которые можно выбрать для построения новой онтологии.
    
    :param request: тело запроса с directory_id
    :param project: проект, к которому принадлежит пользователь
    :param session: асинхронная сессия SQLAlchemy
    
    :return: список понятий
    """
    directory_id = request.get('directory_id')
    
    # Для корневых файлов directory_id может быть None
    if not directory_id:
        logger.info(f"Getting concepts from root directory (directory_id is None) for project {project.id}")
        # Собираем все .tdl файлы из корня (directory_id IS NULL)
        result = await session.execute(
            select(File).where(
                File.project_id == project.id,
                File.directory_id == None,  # noqa: E711
                File.name.endswith('.tdl'),
            )
        )
    else:
        logger.info(f"Getting concepts from directory {directory_id} for project {project.id}")
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
    logger.info(f"Found {len(tdl_files)} .tdl files in directory {directory_id or 'root'}")
    
    if not tdl_files:
        return {
            'concepts': [],
            'relations': [],
            'error': 'No .tdl files in directory',
        }
    
    # Собираем контент всех файлов
    files_dict = {f.name: f.content for f in tdl_files}
    
    # Извлекаем понятия и связи
    from app.services.render_v3 import get_all_concepts_from_directory, get_all_relations_from_directory
    
    concepts = get_all_concepts_from_directory(files_dict)
    relations = get_all_relations_from_directory(files_dict)
    
    logger.info(f"Extracted {len(concepts)} concepts and {len(relations)} relations")
    for c in concepts:
        logger.info(f"  - Concept: {c['name']} ({c['type']})")
    for r in relations:
        logger.info(f"  - Relation: {r['from_concept']} -> {r['to_concept']} ({r['relation_type']})")
    
    return {
        'concepts': concepts,
        'relations': relations,
        'error': None,
    }


class ConceptListRequest(BaseModel):
    directory_id: Optional[str] = None
    search: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)


class RelationsForConceptsRequest(BaseModel):
    directory_id: Optional[str] = None
    concept_names: List[str] = Field(default_factory=list)


@router.post('/concepts', response_model=Dict[str, Any])
async def get_concepts_with_pagination(
    request: ConceptListRequest,
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """
    Получить понятия с пагинацией и поиском.
    
    Используется для конструктора онтологий - показывает список
    существующих понятий с пагинацией (10 на страницу) и поиском.
    
    :param request: параметры пагинации и поиска
    :param project: проект, к которому принадлежит пользователь
    :param session: асинхронная сессия SQLAlchemy
    
    :return: словарь с понятиями, общим количеством и пагинацией
    """
    directory_id = request.directory_id
    
    # Для корневых файлов directory_id может быть None
    if not directory_id:
        logger.info(f"Getting concepts from root directory (directory_id is None) for project {project.id}")
        result = await session.execute(
            select(File).where(
                File.project_id == project.id,
                File.directory_id == None,  # noqa: E711
                File.name.endswith('.tdl'),
            )
        )
    else:
        logger.info(f"Getting concepts from directory {directory_id} for project {project.id}")
        directory = await _get_directory(directory_id, project, session)
        
        result = await session.execute(
            select(File).where(
                File.project_id == project.id,
                File.directory_id == directory.id,
                File.name.endswith('.tdl'),
            )
        )
    
    tdl_files = result.scalars().all()
    logger.info(f"Found {len(tdl_files)} .tdl files in directory {directory_id or 'root'}")
    
    if not tdl_files:
        return {
            'concepts': [],
            'relations': [],
            'total': 0,
            'page': request.page,
            'page_size': request.page_size,
            'total_pages': 0,
            'error': 'No .tdl files in directory',
        }
    
    # Собираем контент всех файлов
    files_dict = {f.name: f.content for f in tdl_files}
    
    # Извлекаем понятия и связи
    from app.services.render_v3 import get_all_concepts_from_directory, get_all_relations_from_directory
    
    concepts = get_all_concepts_from_directory(files_dict)
    relations = get_all_relations_from_directory(files_dict)
    
    logger.info(f"Extracted {len(concepts)} concepts and {len(relations)} relations")
    
    # Поиск по понятиям
    if request.search:
        search_lower = request.search.lower()
        concepts = [
            c for c in concepts
            if search_lower in c['name'].lower() or search_lower in c.get('type', '').lower()
        ]
    
    # Пагинация
    total = len(concepts)
    total_pages = (total + request.page_size - 1) // request.page_size if total > 0 else 0
    start = (request.page - 1) * request.page_size
    end = start + request.page_size
    paginated_concepts = concepts[start:end]
    
    logger.info(f"Pagination: page={request.page}, page_size={request.page_size}, total={total}, total_pages={total_pages}")
    
    return {
        'concepts': paginated_concepts,
        'relations': relations,
        'total': total,
        'page': request.page,
        'page_size': request.page_size,
        'total_pages': total_pages,
        'error': None,
    }


class RelationsForConceptsRequest(BaseModel):
    directory_id: Optional[str] = None
    concept_names: List[str] = Field(default_factory=list)


@router.post('/relations_for_concepts', response_model=Dict[str, Any])
async def get_relations_for_selected_concepts(
    request: RelationsForConceptsRequest,
    project: Project = Depends(get_owned_project),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """
    Получить связи между выбранными понятиями.
    
    Используется для фазы 2 конструктора онтологий - показывает
    связи только между уже выбранными понятиями.
    
    :param request: параметры с именами понятий
    :param project: проект, к которому принадлежит пользователь
    :param session: асинхронная сессия SQLAlchemy
    
    :return: список связей между выбранными понятиями
    """
    print(f"\n===relations_for_concepts called===")
    print(f"directory_id: {request.directory_id}")
    print(f"concept_names: {request.concept_names}")
    
    directory_id = request.directory_id
    concept_names = request.concept_names
    
    logger.info(f"Getting relations for concepts {concept_names} in directory {directory_id} for project {project.id}")
    
    # Для корневых файлов directory_id может быть None
    if not directory_id:
        logger.info(f"Getting relations from root directory (directory_id is None) for project {project.id}")
        result = await session.execute(
            select(File).where(
                File.project_id == project.id,
                File.directory_id == None,  # noqa: E711
                File.name.endswith('.tdl'),
            )
        )
    else:
        logger.info(f"Getting relations from directory {directory_id} for project {project.id}")
        directory = await _get_directory(directory_id, project, session)
        
        result = await session.execute(
            select(File).where(
                File.project_id == project.id,
                File.directory_id == directory.id,
                File.name.endswith('.tdl'),
            )
        )
    
    tdl_files = result.scalars().all()
    logger.info(f"Found {len(tdl_files)} .tdl files in directory {directory_id or 'root'}")
    
    if not tdl_files:
        return {
            'relations': [],
            'error': 'No .tdl files in directory',
        }
    
    # Собираем контент всех файлов
    files_dict = {f.name: f.content for f in tdl_files}
    
    # Извлекаем все связи
    from app.services.render_v3 import get_all_relations_from_directory
    all_relations = get_all_relations_from_directory(files_dict)
    
    logger.info(f"Extracted {len(all_relations)} total relations from directory")
    
    # Добавим логирование каждой связи
    for i, r in enumerate(all_relations):
        if i < 10:  # Покажем первые 10
            logger.info(f"  - Relation {i+1}: {r['from_concept']} -> {r['to_concept']} ({r['relation_type']})")
        elif i == 10:
            logger.info(f"  ... and {len(all_relations) - 10} more")
    
    # Фильтруем связи только между выбранными понятиями
    selected_names_set = set(concept_names)
    logger.info(f"Selected concepts: {concept_names}")
    filtered_relations = [
        r for r in all_relations
        if r['from_concept'] in selected_names_set and r['to_concept'] in selected_names_set
    ]
    
    logger.info(f"Filtered to {len(filtered_relations)} relations between selected concepts")
    for r in filtered_relations:
        logger.info(f"  - Filtered: {r['from_concept']} -> {r['to_concept']} ({r['relation_type']})")
    
    logger.info(f"Extracted {len(filtered_relations)} relations between {len(concept_names)} selected concepts")
    
    return {
        'relations': filtered_relations,
        'error': None,
    }


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
