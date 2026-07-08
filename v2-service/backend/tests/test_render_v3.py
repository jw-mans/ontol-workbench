"""Тесты движка ontol-v3 (TDL → SVG) и диспетчеризации сборки по расширению.

Рендер v3 идёт через бинарь Graphviz ``dot``, а сам пакет ``uml_dsl`` может быть
не установлен в тестовой среде — поэтому:
  - ошибки парсера/семантической валидации проверяем, если есть ``uml_dsl``
    (они возникают ДО вызова ``dot``);
  - успешный рендер — только если доступен и ``uml_dsl``, и ``dot``.
Диспетчер и путь v1 (``.ontol``) от внешних бинарей не зависят.
"""

import importlib.util
import shutil

import pytest

from app.services.render import build_project

HAS_UML = importlib.util.find_spec('uml_dsl') is not None
HAS_DOT = shutil.which('dot') is not None

needs_uml = pytest.mark.skipif(not HAS_UML, reason='пакет uml_dsl не установлен')
needs_render = pytest.mark.skipif(
    not (HAS_UML and HAS_DOT), reason='нужны uml_dsl и graphviz dot'
)

VALID_TDL = """КЛАСС Животное АБСТРАКТНЫЙ
  АТРИБУТЫ
    + имя : Строка
КОНЕЦ КЛАСС

КЛАСС Собака
КОНЕЦ КЛАСС

ОБОБЩЕНИЕ Собака -> Животное
"""

# Цикл наследования — ошибка семантической валидации (ValueError до dot).
CYCLE_TDL = """КЛАСС А
КОНЕЦ КЛАСС
КЛАСС Б
КОНЕЦ КЛАСС
ОБОБЩЕНИЕ А -> Б
ОБОБЩЕНИЕ Б -> А
"""

# Одиночный дефис между полюсами связи — синтаксическая ошибка (ждём '--').
BAD_SYNTAX_TDL = """КЛАСС А
КОНЕЦ КЛАСС
КЛАСС Б
КОНЕЦ КЛАСС
АССОЦИАЦИЯ А - Б
"""

MINIMAL_ONTOL = """version: '1.0'
title: 'T'

types:
person: 'Человек', 'Описание'
"""


# --- build_tdl_svg: юнит движка v3 --------------------------------------- #


@needs_uml
def test_tdl_cycle_is_error():
    from app.services.render_v3 import build_tdl_svg

    svg, error = build_tdl_svg(CYCLE_TDL)
    assert svg is None
    assert error and 'цикл' in error.lower()


@needs_uml
def test_tdl_bad_syntax_is_error():
    from app.services.render_v3 import build_tdl_svg

    svg, error = build_tdl_svg(BAD_SYNTAX_TDL)
    assert svg is None
    assert error  # сообщение парсера


@needs_render
def test_tdl_valid_renders_svg():
    from app.services.render_v3 import build_tdl_svg

    svg, error = build_tdl_svg(VALID_TDL)
    assert error is None
    assert svg and svg.lstrip().startswith('<svg')


# --- build_project: диспетчер по расширению ------------------------------- #


@needs_render
def test_dispatch_tdl_returns_svg_only():
    res = build_project({'d.tdl': VALID_TDL}, 'd.tdl', 'http://unused')
    assert res.ok
    assert res.svg and res.svg.lstrip().startswith('<svg')
    # у v3 нет JSON/PlantUML/PNG
    assert res.json is None and res.puml is None and res.png_url is None


@needs_render
def test_dispatch_tdl_semantic_issue_warns_not_fails():
    # цикл наследования не валит сборку — диаграмма есть, а нарушение в warnings
    res = build_project({'d.tdl': CYCLE_TDL}, 'd.tdl', 'http://unused')
    assert res.ok
    assert res.svg and res.svg.lstrip().startswith('<svg')
    assert any('цикл' in w.lower() for w in res.warnings)


def test_dispatch_ontol_uses_v1_not_v3():
    # .ontol идёт по пути v1: JSON/PlantUML есть, SVG нет (PNG уходит в warnings
    # без живого PlantUML-сервера — это нормально).
    res = build_project({'m.ontol': MINIMAL_ONTOL}, 'm.ontol', 'http://unused')
    assert res.ok
    assert res.json is not None and res.puml is not None
    assert res.svg is None


def test_entry_not_found():
    res = build_project({'a.tdl': VALID_TDL}, 'missing.tdl', 'http://unused')
    assert res.ok is False and res.error


# --- Планарность --------------------------------------------------------- #

# Планарный граф (цепочка обобщений) — раскладывается без пересечений (ручная
# ветка рендера, dot не нужен).
PLANAR_TDL = """КЛАСС A
КОНЕЦ КЛАСС
КЛАСС B
КОНЕЦ КЛАСС
КЛАСС C
КОНЕЦ КЛАСС
ОБОБЩЕНИЕ B -> A
ОБОБЩЕНИЕ C -> B
"""


def _complete_graph_tdl(names: str) -> str:
    import itertools

    body = ''.join(f'КЛАСС {n}\nКОНЕЦ КЛАСС\n' for n in names)
    edges = ''.join(
        f'АССОЦИАЦИЯ {a} -- {b}\n' for a, b in itertools.combinations(names, 2)
    )
    return body + edges


K5_TDL = _complete_graph_tdl('ABCDE')  # полный граф на 5 вершинах — не планарен

# Два непересекающихся K5 (ABCDE и FGHIJ) — граф содержит ДВА подграфа-нарушителя.
TWO_K5_TDL = _complete_graph_tdl('ABCDE') + _complete_graph_tdl('FGHIJ')

# K3,3: двудольный на 6 вершинах (ABC ↔ DEF).
K33_TDL = ''.join(f'КЛАСС {n}\nКОНЕЦ КЛАСС\n' for n in 'ABCDEF') + ''.join(
    f'АССОЦИАЦИЯ {a} -- {b}\n' for a in 'ABC' for b in 'DEF'
)


@needs_uml
def test_planar_gets_layout_no_warning():
    from app.services.render_v3 import build_tdl

    res = build_tdl({'p.tdl': PLANAR_TDL}, 'p.tdl')
    assert res.ok and res.svg
    assert 'translate(' in res.svg  # нарисован по планарным позициям
    assert res.planarity is None


@needs_uml
def test_non_planar_k5_detected():
    from uml_dsl.planarity import analyze
    from uml_dsl.tdl_build import build_diagram
    from uml_dsl.tdl_lexer import lex
    from uml_dsl.tdl_parser import parse_tdl

    result = analyze(build_diagram(parse_tdl(lex(K5_TDL))))
    assert result.is_planar is False
    assert result.kind == 'K5'
    assert set('ABCDE') <= set(result.labels)
    assert 'K5' in (result.warning() or '')


@needs_uml
def test_non_planar_k33_detected():
    from uml_dsl.planarity import analyze
    from uml_dsl.tdl_build import build_diagram
    from uml_dsl.tdl_lexer import lex
    from uml_dsl.tdl_parser import parse_tdl

    result = analyze(build_diagram(parse_tdl(lex(K33_TDL))))
    assert result.is_planar is False
    assert result.kind == 'K3,3'
    assert set('ABCDEF') <= set(result.labels)


@needs_uml
def test_multiple_obstructions_detected():
    # Два непересекающихся K5 → два отдельных подграфа-нарушителя.
    from uml_dsl.planarity import analyze
    from uml_dsl.tdl_build import build_diagram
    from uml_dsl.tdl_lexer import lex
    from uml_dsl.tdl_parser import parse_tdl

    result = analyze(build_diagram(parse_tdl(lex(TWO_K5_TDL))))
    assert result.is_planar is False
    assert len(result.obstructions) == 2
    assert all(o.kind == 'K5' for o in result.obstructions)
    # labels — объединение обоих подграфов (все 10 классов подсвечиваются).
    assert set('ABCDEFGHIJ') <= set(result.labels)
    # каждый подграф локализован в своей пятёрке
    branch_sets = {frozenset(o.labels) for o in result.obstructions}
    assert frozenset('ABCDE') in branch_sets
    assert frozenset('FGHIJ') in branch_sets


# Два K5 (ABCDE и DEFGH) с общим ребром D–E — пересекаются и по вершинам, и по
# ребру, но остаются двумя разными подграфами-нарушителями.
SHARED_EDGE_TDL = _complete_graph_tdl('ABCDE') + _complete_graph_tdl('DEFGH')


@needs_uml
def test_obstructions_sharing_an_edge_both_detected():
    from uml_dsl.planarity import analyze
    from uml_dsl.tdl_build import build_diagram
    from uml_dsl.tdl_lexer import lex
    from uml_dsl.tdl_parser import parse_tdl

    result = analyze(build_diagram(parse_tdl(lex(SHARED_EDGE_TDL))))
    assert result.is_planar is False
    assert len(result.obstructions) == 2
    assert all(o.kind == 'K5' for o in result.obstructions)
    branch_sets = {frozenset(o.labels) for o in result.obstructions}
    assert frozenset('ABCDE') in branch_sets
    assert frozenset('DEFGH') in branch_sets
    # общие вершины D, E входят в оба подграфа (и подсвечиваются как часть обоих)
    assert {'D', 'E'} <= (frozenset('ABCDE') & frozenset('DEFGH'))


@needs_render
def test_non_planar_build_reports_planarity():
    from app.services.render_v3 import build_tdl

    res = build_tdl({'k.tdl': K5_TDL}, 'k.tdl')
    assert res.ok and res.svg  # рисуем «как есть»
    assert res.planarity and res.planarity['kind'] == 'K5'
    assert set('ABCDE') <= set(res.planarity['labels'])
    assert res.planarity['count'] == 1
    assert res.planarity['subgraphs'][0]['kind'] == 'K5'


@needs_render
def test_two_k5_build_reports_two_subgraphs():
    from app.services.render_v3 import build_tdl

    res = build_tdl({'k.tdl': TWO_K5_TDL}, 'k.tdl')
    assert res.ok and res.svg
    assert res.planarity and res.planarity['count'] == 2
    assert set('ABCDEFGHIJ') <= set(res.planarity['labels'])
    assert {s['kind'] for s in res.planarity['subgraphs']} == {'K5'}
