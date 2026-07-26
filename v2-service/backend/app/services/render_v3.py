"""
Сборка онтологии на TDL (ontol-v3) в SVG через пакет ``uml_dsl`` (Graphviz).

Отдельный движок от v1: свой язык TDL, рендер через бинарь ``dot``. Пакет
``uml_dsl`` ставится в образ (``pip install -e src/ontol-v3``), сам ``dot``
ставится apt-пакетом ``graphviz``.

Онтология в v3 привязана к **директории**, а не к проекту:
- Каждый ``.tdl`` файл рендерится отдельно
- Для проверки семантической целостности собираются все ``.tdl`` файлы в директории
- Конструктор онтологий позволяет создать новую онтологию в выбранной директории
"""

from __future__ import annotations

from app.services.render import BuildResult


def _render(
    text: str, *, strict: bool = False
) -> tuple[str | None, list[str], dict | None, str | None]:
    """
    Рендер одного TDL-текста в SVG.

    :param text: текст ``.tdl``
    :param strict: True = строгая семантика, False = мягко (только предупреждения)

    :return: svg (или None), предупреждения, планарность (или None), ошибка (или None)
    """
    try:
        from uml_dsl.tdl_lexer import LexerError
        from uml_dsl.tdl_parser import ParseError
        from uml_dsl.tdl_run import tdl_to_svg_analyzed
    except ImportError as error:  # пакет uml_dsl не установлен в образе
        return None, [], None, f'Движок ontol-v3 (uml_dsl) недоступен: {error}'

    try:
        svg, warnings, planarity = tdl_to_svg_analyzed(text, strict=strict)
    except LexerError as error:
        return None, [], None, f'Ошибка лексера: {error}'
    except ParseError as error:
        return None, [], None, f'Ошибка парсера: {error}'
    except ValueError as error:  # ошибка модели / семантической валидации
        return None, [], None, f'Ошибка модели: {error}'
    except RuntimeError as error:  # graphviz dot не найден / упал
        return None, [], None, str(error)

    return svg, warnings, planarity, None


def _merge_and_check_semantics(
    texts: list[str], *, strict: bool = False
) -> tuple[list[str], dict | None, str | None]:
    """
    Слить несколько TDL-текстов в одну онтологию и проверить семантическую целостность.
    Не рендерит SVG, только проверяет валидность объединённой модели.

    :param texts: тексты ``.tdl`` (несколько файлов директории)
    :param strict: True = строгая семантика, False = мягко (только предупреждения)

    :return: (список предупреждений, планарность (или None), ошибка (или None))
    """
    try:
        from uml_dsl.tdl_lexer import LexerError
        from uml_dsl.tdl_parser import ParseError
        from uml_dsl.tdl_run import merge_tdl_documents, build_diagram
    except ImportError as error:
        return [], None, f'Движок ontol-v3 (uml_dsl) недоступен: {error}'

    try:
        # Сливаем все тексты в один документ
        doc = merge_tdl_documents(texts)
        # Строим диаграмму
        diagram = build_diagram(doc)
        # Проверяем валидность (без рендера)
        warnings = diagram.validate_all(strict=strict)
        
        # Анализируем планарность графа (для диагностики)
        from uml_dsl.planarity import analyze
        result = analyze(diagram)
        planarity = None
        if not result.is_planar and result.obstructions:
            planarity = {
                'kind': result.kind,
                'labels': result.labels,
                'message': result.warning(),
                'subgraphs': [
                    {'kind': o.kind, 'labels': o.labels} for o in result.obstructions
                ],
                'count': len(result.obstructions),
            }
        
        return warnings, planarity, None
    except LexerError as error:
        return [], None, f'Ошибка лексера при слиянии: {error}'
    except ParseError as error:
        return [], None, f'Ошибка парсера при слиянии: {error}'
    except ValueError as error:
        return [], None, f'Ошибка модели при слиянии: {error}'


def _tdl_texts(files: dict[str, str]) -> list[str]:
    """Тексты всех ``.tdl``-файлов набора, по имени (детерминированный порядок)."""
    return [content for name, content in sorted(files.items()) if name.endswith('.tdl')]


def build_tdl(files: dict[str, str], entry: str) -> BuildResult:
    """
    Собрать ``.tdl`` проект: рендер entry-файла и проверка семантической целостности
    только этого файла (без слияния с другими файлами).

    :param files: словарь имя -> текст (файлы проекта и подпроектов)
    :param entry: точка входа (относительный путь к ``.tdl`` файлу)

    :return: BuildResult
    """
    # 1. Рендерим entry-файл отдельно
    if entry not in files:
        return BuildResult(ok=False, error=f'Entry file {entry!r} not found')
    
    entry_text = files[entry]
    svg, warnings, planarity, error = _render(entry_text, strict=False)
    if error:
        return BuildResult(ok=False, error=error)
    
    return BuildResult(
        ok=True,
        svg=svg,
        warnings=warnings if warnings else [],
        planarity=planarity
    )


def build_tdl_svg(text: str, strict: bool = True) -> tuple[str | None, str | None]:
    """
    TDL -> SVG (одна онтология из одного текста). Для юнит-тестов; strict по умолчанию.

    :param text: текст TDL
    :param strict: True = строгая семантика, False = мягко (только предупреждения)

    :return: svg (или None), ошибка (или None)
    """
    svg, _warnings, _planarity, error = _render(text, strict=strict)
    return svg, error


def check_semantics(texts: list[str], strict: bool = False) -> tuple[list[str], dict | None, str | None]:
    """
    Проверить семантическую целостность объединённой онтологии без рендера.

    :param texts: тексты ``.tdl`` для проверки
    :param strict: True = строгая семантика

    :return: (список предупреждений, планарность (или None), ошибка (или None))
    """
    return _merge_and_check_semantics(texts, strict=strict)


def get_concepts_from_tdl(text: str) -> list[dict]:
    """
    Извлечь все понятия из TDL-текста.

    :param text: текст ``.tdl``
    :return: список понятий с их типами и свойствами
    """
    try:
        from uml_dsl.tdl_lexer import lex
        from uml_dsl.tdl_parser import parse_tdl
        from uml_dsl.tdl_build import build_diagram
    except ImportError:
        return []

    try:
        tokens = lex(text)
        doc = parse_tdl(tokens)
        diagram = build_diagram(doc)

        concepts = []
        for name, classifier in diagram.classifiers.items():
            # Определяем тип классификатора
            type_map = {
                'Class': 'class',
                'Interface': 'interface',
                'DataType': 'data_type',
                'Enum': 'enum',
                'Template': 'template',
            }
            classifier_type = type_map.get(type(classifier).__name__, 'class')

            concept = {
                'name': name,
                'type': classifier_type,
                'is_abstract': getattr(classifier, 'is_abstract', False),
                'attributes': [],
                'operations': [],
            }

            # Собираем атрибуты
            if hasattr(classifier, 'attributes') and classifier.attributes:
                for attr in classifier.attributes:
                    attr_str = _format_attribute(attr)
                    if attr_str:
                        concept['attributes'].append(attr_str)

            # Собираем операции
            if hasattr(classifier, 'operations') and classifier.operations:
                for op in classifier.operations:
                    op_str = _format_operation(op)
                    if op_str:
                        concept['operations'].append(op_str)

            concepts.append(concept)

        return concepts
    except Exception:
        return []


def _format_attribute(attr) -> str | None:
    """Форматировать атрибут в строку для UI."""
    if not hasattr(attr, 'name'):
        return None

    parts = []
    
    # Видимость
    if hasattr(attr, 'visibility') and attr.visibility:
        visibility_map = {'public': '+', 'private': '-', 'protected': '#', 'package': '~'}
        parts.append(visibility_map.get(str(attr.visibility).lower(), '+'))
    
    # Имя
    parts.append(attr.name)

    # Тип
    if hasattr(attr, 'type_') and attr.type_:
        parts.append(f': {attr.type_}')

    # Кратность
    if hasattr(attr, 'multiplicity') and attr.multiplicity:
        if attr.multiplicity.lower:
            if attr.multiplicity.lower == attr.multiplicity.upper:
                parts.append(f'[{attr.multiplicity.lower}]')
            elif attr.multiplicity.upper is None:
                parts.append(f'[0..*]')
            else:
                parts.append(f'[{attr.multiplicity.lower}..{attr.multiplicity.upper}]')

    return ' '.join(parts)


def _format_operation(op) -> str | None:
    """Форматировать операцию в строку для UI."""
    if not hasattr(op, 'name'):
        return None

    parts = []
    
    # Видимость
    if hasattr(op, 'visibility') and op.visibility:
        visibility_map = {'public': '+', 'private': '-', 'protected': '#', 'package': '~'}
        parts.append(visibility_map.get(str(op.visibility).lower(), '+'))
    
    # Имя
    parts.append(op.name)
    parts.append('(')

    # Параметры
    if hasattr(op, 'parameters') and op.parameters:
        param_strs = []
        for param in op.parameters:
            p = [param.name]
            if hasattr(param, 'type_') and param.type_:
                p.append(f': {param.type_}')
            param_strs.append(''.join(p))
        parts.append(', '.join(param_strs))

    parts.append(')')

    # Возвращаемый тип
    if hasattr(op, 'return_type') and op.return_type:
        parts.append(f': {op.return_type}')

    return ''.join(parts)


def get_all_concepts_from_directory(files: dict[str, str]) -> list[dict]:
    """
    Извлечь все понятия из всех TDL-файлов в директории.

    :param files: словарь имя_файла -> текст_файла
    :return: список всех понятий с уникальными именами
    """
    all_concepts = []
    seen_names = set()

    tdl_contents = [content for name, content in files.items() if name.endswith('.tdl')]
    
    for content in tdl_contents:
        concepts = get_concepts_from_tdl(content)
        for concept in concepts:
            if concept['name'] not in seen_names:
                seen_names.add(concept['name'])
                all_concepts.append(concept)

    return all_concepts


def get_all_relations_from_directory(files: dict[str, str]) -> list[dict]:
    """
    Извлечь все связи из всех TDL-файлов в директории.

    :param files: словарь имя_файла -> текст_файла
    :return: список всех связей
    """
    try:
        from uml_dsl.tdl_lexer import lex
        from uml_dsl.tdl_parser import parse_tdl
        from uml_dsl.tdl_run import merge_tdl_documents, build_diagram
    except ImportError:
        return []

    tdl_contents = [content for name, content in files.items() if name.endswith('.tdl')]
    
    if not tdl_contents:
        return []

    try:
        # Сливаем все тексты в один документ
        doc = merge_tdl_documents(tdl_contents)
        # Строим диаграмму
        diagram = build_diagram(doc)

        relations = []
        print('До обобщений')
        # Обобщения
        for gen in diagram.generalizations:
            relations.append({
                'relation_type': 'generalization',
                'from_concept': gen.specific.name,
                'to_concept': gen.general.name,
            })
        print('До ассоциаций')
        # Ассоциации
        for assoc in diagram.associations:
            # Для простых ассоциаций с двумя полюсами
            if len(assoc.ends) >= 2:
                end1 = assoc.ends[0]
                end2 = assoc.ends[1]
                
                # Определяем тип ассоциации по агрегации
                # Проверяем по enum значениям
                from uml_dsl.enums import AggregationKind
                is_composition = (
                    getattr(end1, 'aggregation', AggregationKind.NONE) == AggregationKind.COMPOSITION or
                    getattr(end2, 'aggregation', AggregationKind.NONE) == AggregationKind.COMPOSITION
                )
                is_aggregation = (
                    getattr(end1, 'aggregation', AggregationKind.NONE) == AggregationKind.AGGREGATION or
                    getattr(end2, 'aggregation', AggregationKind.NONE) == AggregationKind.AGGREGATION
                )
                
                if is_composition:
                    rel_type = 'composition'
                elif is_aggregation:
                    rel_type = 'aggregation'
                else:
                    rel_type = 'association'

                # Определяем участников
                from_concept = end1.participant.name
                to_concept = end2.participant.name

                # Собираем кратность
                multiplicity_from = None
                multiplicity_to = None
                
                if hasattr(end1, 'multiplicity') and end1.multiplicity:
                    mult = end1.multiplicity
                    if mult.lower == mult.upper:
                        multiplicity_from = f'[{mult.lower}]'
                    elif mult.upper is None:
                        multiplicity_from = '[0..*]'
                    else:
                        multiplicity_from = f'[{mult.lower}..{mult.upper}]'

                if hasattr(end2, 'multiplicity') and end2.multiplicity:
                    mult = end2.multiplicity
                    if mult.lower == mult.upper:
                        multiplicity_to = f'[{mult.lower}]'
                    elif mult.upper is None:
                        multiplicity_to = '[0..*]'
                    else:
                        multiplicity_to = f'[{mult.lower}..{mult.upper}]'

                relations.append({
                    'relation_type': rel_type,
                    'from_concept': from_concept,
                    'to_concept': to_concept,
                    'multiplicity_from': multiplicity_from,
                    'multiplicity_to': multiplicity_to,
                })
        print('До зависимостей')
        # Зависимости
        for dep in diagram.dependencies:
            client_name = dep.client.name
            supplier_name = dep.supplier.name
            
            relations.append({
                'relation_type': 'dependency',
                'from_concept': client_name,
                'to_concept': supplier_name,
            })
        print('До реализаций')
        # Реализации
        for real in diagram.realizations:
            implementer_name = real.implementer.name
            interface_name = real.interface_.name
            
            relations.append({
                'relation_type': 'realization',
                'from_concept': implementer_name,
                'to_concept': interface_name,
            })

        return relations
    except Exception as e:
        print(f"Error in get_all_relations_from_directory: {e}")
        return []
