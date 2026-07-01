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


@needs_uml
def test_dispatch_tdl_error_no_svg():
    res = build_project({'d.tdl': CYCLE_TDL}, 'd.tdl', 'http://unused')
    assert res.ok is False
    assert res.error and res.svg is None


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
