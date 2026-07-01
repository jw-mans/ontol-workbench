"""
Парсер SVG с data-атрибутами обратно в Pydantic-модель UML.
Использует BeautifulSoup для парсинга XML.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple, Any

from pydantic import BaseModel, Field, ValidationError

from .models import (
    Class, Attribute, Operation, Parameter,
    MultiplicityRange, Visibility, Scope, Stereotype
)
from .relationships import (
    Association, AssociationEnd, Dependency, 
    Generalization, Realization, AggregationKind
)
from .diagram import ClassDiagram, ClassPosition


class ParseResult(BaseModel):
    """Результат парсинга SVG в Pydantic-модель."""
    success: bool
    diagram: Optional[ClassDiagram] = None
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


def parse_transform(transform_str: str) -> Tuple[float, float]:
    """Извлекает координаты из transform="translate(x,y)"."""
    if not transform_str or "translate" not in transform_str:
        return (0.0, 0.0)
    # translate(10,20) или translate(10 20)
    import re
    match = re.search(r'translate\(([^,)]+)[,\s]+([^)]+)\)', transform_str)
    if match:
        return (float(match.group(1)), float(match.group(2)))
    return (0.0, 0.0)


def _data_attr(elem: ET.Element, *names: str, default: Optional[str] = None) -> Optional[str]:
    for name in names:
        value = elem.get(name)
        if value not in (None, ""):
            return value
    return default


def _parse_optional_bool(value: Optional[str]) -> Optional[bool]:
    if value is None or value == "":
        return None
    return {"true": True, "false": False}.get(value.lower())


def parse_svg_to_diagram(svg_content: str) -> ParseResult:
    """
    Парсит SVG с data-атрибутами и восстанавливает ClassDiagram.
    
    Собирает ошибки и предупреждения вместо выбрасывания исключений.
    
    Args:
        svg_content: содержимое SVG-файла
        
    Returns:
        ParseResult с диаграммой, ошибками и предупреждениями
    """
    errors: List[str] = []
    warnings: List[str] = []
    
    try:
        root = ET.fromstring(svg_content)
    except ET.ParseError as e:
        return ParseResult(
            success=False,
            errors=[f"Ошибка парсинга XML: {e}"]
        )
    
    # Проверка наличия классов
    class_elements = root.findall('.//*[@data-type="class"]')
    if not class_elements:
        return ParseResult(
            success=False,
            errors=["Диаграмма не содержит размеченных классов. Убедитесь, что SVG сгенерирован TDL."]
        )
    
    # Создаём пустую диаграмму
    diagram = ClassDiagram(title="Imported from SVG")
    
    # 1. Сначала парсим все классы (они нужны для ссылок в отношениях)
    class_positions = {}
    
    for elem in class_elements:
        class_id = elem.get('data-id')
        if not class_id:
            errors.append(f"Класс без атрибута data-id (элемент {elem.tag})")
            continue
            
        # Извлекаем данные из атрибутов
        name = elem.get('data-name', class_id)
        stereo = elem.get('data-stereotype')
        is_abstract = elem.get('data-abstract') == 'true'
        attr_count = int(elem.get('data-attributes-count', '0'))
        op_count = int(elem.get('data-operations-count', '0'))
        
        # Создаём класс (пока без атрибутов и операций — их нет в SVG)
        # В реальном парсере нужно будет восстанавливать и их из текста
        cls = Class(
            name=name,
            stereotype=Stereotype(stereo) if stereo else None,
            is_abstract=is_abstract,
        )
        
        diagram.add_classifier(cls)
        
        # Сохраняем позицию
        transform = elem.get('transform', '')
        x, y = parse_transform(transform)
        
        # Ищем rect с размерами (первый внутри группы)
        rect = elem.find('.//rect')
        if rect is not None:
            width = float(rect.get('width', '120'))
            height = float(rect.get('height', '60'))
        else:
            width, height = 120, 60
            
        class_positions[name] = ClassPosition(
            classifier_name=name,
            x=x, y=y,
            width=width, height=height
        )
    
    # Добавляем все позиции в диаграмму
    diagram.positions.update(class_positions)
    
    # 2. Парсим отношения (ассоциации)
    for elem in root.findall('.//*[@data-type="association"]'):
        src = _data_attr(elem, 'data-end1-class', 'data-src')
        tgt = _data_attr(elem, 'data-end2-class', 'data-tgt')
        
        if not src or not tgt:
            warnings.append("Association without data-end1-class/data-end2-class or legacy data-src/data-tgt ignored")
            continue
            
        src_cls = diagram.classifiers.get(src)
        tgt_cls = diagram.classifiers.get(tgt)
        
        if not src_cls:
            errors.append(f"Ассоциация: класс-источник '{src}' не найден")
            continue
        if not tgt_cls:
            errors.append(f"Ассоциация: класс-целевой '{tgt}' не найден")
            continue
        
        # Создаём полюса ассоциации
        src_multiplicity = _data_attr(elem, 'data-end1-multiplicity', 'data-src-multiplicity')
        tgt_multiplicity = _data_attr(elem, 'data-end2-multiplicity', 'data-tgt-multiplicity')
        
        src_agg = _data_attr(elem, 'data-end1-aggregation', 'data-src-aggregation', default='none') or 'none'
        tgt_agg = _data_attr(elem, 'data-end2-aggregation', 'data-tgt-aggregation', default='none') or 'none'
        
        src_nav = _data_attr(elem, 'data-end1-navigable', 'data-src-navigable')
        tgt_nav = _data_attr(elem, 'data-end2-navigable', 'data-tgt-navigable')
        src_role = _data_attr(elem, 'data-end1-role', 'data-src-role')
        tgt_role = _data_attr(elem, 'data-end2-role', 'data-tgt-role')
        
        # Парсим кратность с обработкой ошибок
        src_mult_obj = None
        if src_multiplicity:
            try:
                src_mult_obj = MultiplicityRange.from_str(src_multiplicity)
            except (ValueError, IndexError) as e:
                errors.append(f"Association '{src}->{tgt}': invalid end1 multiplicity '{src_multiplicity}'")
                continue
        
        tgt_mult_obj = None
        if tgt_multiplicity:
            try:
                tgt_mult_obj = MultiplicityRange.from_str(tgt_multiplicity)
            except (ValueError, IndexError) as e:
                errors.append(f"Association '{src}->{tgt}': invalid end2 multiplicity '{tgt_multiplicity}'")
                continue
        
        try:
            end1 = AssociationEnd(
                participant=src_cls,
                multiplicity=src_mult_obj,
                aggregation=AggregationKind(src_agg),
                role=src_role,
                navigable=_parse_optional_bool(src_nav),
            )

            end2 = AssociationEnd(
                participant=tgt_cls,
                multiplicity=tgt_mult_obj,
                aggregation=AggregationKind(tgt_agg),
                role=tgt_role,
                navigable=_parse_optional_bool(tgt_nav),
            )

            assoc = Association(
                name=elem.get('data-name'),
                is_derived=elem.get('data-derived') == 'true',
                ends=[end1, end2]
            )
        except (ValueError, ValidationError) as e:
            errors.append(f"Association '{src}->{tgt}' is invalid: {e}")
            continue

        diagram.add_association(assoc)
    
    # 3. Парсим зависимости
    for elem in root.findall('.//*[@data-type="dependency"]'):
        src = elem.get('data-src')
        tgt = elem.get('data-tgt')
        
        if not src or not tgt:
            warnings.append(f"Зависимость без data-src или data-tgt (игнорируется)")
            continue
            
        src_cls = diagram.classifiers.get(src)
        tgt_cls = diagram.classifiers.get(tgt)
        
        if not src_cls:
            errors.append(f"Зависимость: класс-клиент '{src}' не найден")
            continue
        if not tgt_cls:
            errors.append(f"Зависимость: класс-поставщик '{tgt}' не найден")
            continue
        
        stereo = elem.get('data-stereotype')
        # Используем стереотип только если он задан и не пустой
        stereotype = stereo if stereo else None
        
        dep = Dependency(
            client=src_cls,
            supplier=tgt_cls,
            stereotype=stereotype
        )
        
        diagram.dependencies.append(dep)
    
    # 4. Парсим обобщения
    for elem in root.findall('.//*[@data-type="generalization"]'):
        src = elem.get('data-src')
        tgt = elem.get('data-tgt')
        
        if not src or not tgt:
            warnings.append(f"Обобщение без data-src или data-tgt (игнорируется)")
            continue
            
        src_cls = diagram.classifiers.get(src)
        tgt_cls = diagram.classifiers.get(tgt)
        
        if not src_cls:
            errors.append(f"Обобщение: класс-частный '{src}' не найден")
            continue
        if not tgt_cls:
            errors.append(f"Обобщение: класс-общий '{tgt}' не найден")
            continue
        
        is_substitutable = elem.get('data-substitutable') != 'false'
        
        gen = Generalization(
            specific=src_cls,
            general=tgt_cls,
            is_substitutable=is_substitutable
        )
        
        diagram.generalizations.append(gen)
    
    # 5. Парсим реализации
    for elem in root.findall('.//*[@data-type="realization"]'):
        src = elem.get('data-src')
        tgt = elem.get('data-tgt')
        
        if not src or not tgt:
            warnings.append(f"Реализация без data-src или data-tgt (игнорируется)")
            continue
            
        src_cls = diagram.classifiers.get(src)
        tgt_cls = diagram.classifiers.get(tgt)
        
        if not src_cls:
            errors.append(f"Реализация: класс-реализатор '{src}' не найден")
            continue
        if not tgt_cls:
            errors.append(f"Реализация: интерфейс '{tgt}' не найден")
            continue
        
        real = Realization(
            implementer=src_cls,
            interface_=tgt_cls
        )
        
        diagram.realizations.append(real)
    
    # Возвращаем результат с диаграммой и любыми накопленными предупреждениями
    return ParseResult(
        success=not errors,
        diagram=diagram,
        warnings=warnings if not errors else [],  # не включаем предупреждения если были ошибки
        errors=errors
    )


# Добавляем вспомогательный метод в MultiplicityRange
def multiplicity_range_from_str(s: str) -> MultiplicityRange:
    """Парсит строку вида '1..*' или '0..1' или '*'."""
    if not s:
        return MultiplicityRange(lower=0, upper=None)
    
    if s == '*':
        return MultiplicityRange(lower=0, upper=None)
    
    if '..' in s:
        parts = s.split('..')
        lower = int(parts[0])
        upper = None if parts[1] == '*' else int(parts[1])
        return MultiplicityRange(lower=lower, upper=upper)
    
    # Одиночное число
    val = int(s)
    return MultiplicityRange(lower=val, upper=val)

# Monkey-patch для удобства
MultiplicityRange.from_str = staticmethod(multiplicity_range_from_str)
