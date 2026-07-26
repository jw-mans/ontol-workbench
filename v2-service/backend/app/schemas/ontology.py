"""Pydantic-схемы для конструктора онтологий (v3/TDL)."""

from typing import Literal

from pydantic import BaseModel, Field


class OntologyConcept(BaseModel):
    """
    Понятие (классификатор) в онтологии.
    
    :param name: имя понятия (класса)
    :param type: тип понятия (class/interface/data_type/enum/template)
    :param is_abstract: является ли понятие абстрактным
    :param attributes: список атрибутов (опционально)
    :param operations: список операций (опционально)
    """
    name: str = Field(..., description="Имя понятия (должно быть уникальным в онтологии)")
    type: Literal["class", "interface", "data_type", "enum", "template"] = Field(
        default="class", description="Тип понятия"
    )
    is_abstract: bool = Field(default=False, description="Абстрактное ли понятие")
    attributes: list[str] = Field(default_factory=list, description="Список атрибутов (имя: тип)")
    operations: list[str] = Field(default_factory=list, description="Список операций")


class OntologyRelation(BaseModel):
    """
    Связь между понятиями в онтологии.
    
    :param relation_type: тип связи (generalization/association/aggregation/composition/dependency/realization)
    :param from_concept: имя источника связи
    :param to_concept: имя получателя связи
    :param name: имя связи (опционально)
    :param multiplicity_from: кратность от источника (опционально)
    :param multiplicity_to: кратность к получателю (опционально)
    """
    relation_type: Literal[
        "generalization", "association", "aggregation", 
        "composition", "dependency", "realization"
    ] = Field(..., description="Тип связи")
    from_concept: str = Field(..., description="Имя понятия-источника")
    to_concept: str = Field(..., description="Имя понятия-получателя")
    name: str | None = Field(default=None, description="Имя связи (опционально)")
    multiplicity_from: str | None = Field(
        default=None, 
        description="Кратность от источника: [1], [0..1], [0..*], [*]"
    )
    multiplicity_to: str | None = Field(
        default=None, 
        description="Кратность к получателю: [1], [0..1], [0..*], [*]"
    )


class OntologyBuildRequest(BaseModel):
    """
    Запрос на построение онтологии из выбранных понятий и связей.
    
    :param directory_id: UUID директории (куда будет создан новый TDL-файл)
    :param concepts: список выбранных понятий
    :param relations: список выбранных связей
    :param file_name: имя создаваемого TDL-файла (по умолчанию "ontology.tdl")
    :param template: тип шаблона ("empty" или "from_relations")
    """
    directory_id: str = Field(..., description="UUID директории для создания файла")
    concepts: list[OntologyConcept] = Field(
        default_factory=list, 
        description="Список выбранных понятий"
    )
    relations: list[OntologyRelation] = Field(
        default_factory=list, 
        description="Список выбранных связей"
    )
    file_name: str = Field(
        default="ontology.tdl", 
        description="Имя создаваемого TDL-файла"
    )
    template: Literal["empty", "from_relations"] = Field(
        default="from_relations",
        description="Тип шаблона: пустой или с построением из связей"
    )


class SemanticCheckResult(BaseModel):
    """
    Результат проверки семантической целостности онтологии.
    
    :param is_valid: валидна ли онтология
    :param warnings: список предупреждений
    :param planarity: диагностика планарности (если есть проблемы)
    :param error: текст ошибки (если есть)
    """
    is_valid: bool = Field(..., description="Валидна ли онтология")
    warnings: list[str] = Field(default_factory=list, description="Список предупреждений")
    planarity: dict | None = Field(default=None, description="Диагностика планарности")
    error: str | None = Field(default=None, description="Текст ошибки")


class TDLFileCreateRequest(BaseModel):
    """
    Запрос на создание TDL-файла.
    
    :param directory_id: UUID директории
    :param file_name: имя файла
    :param content: содержимое файла
    """
    directory_id: str = Field(..., description="UUID директории")
    file_name: str = Field(..., description="Имя TDL-файла")
    content: str = Field(..., description="Содержимое TDL-файла")
