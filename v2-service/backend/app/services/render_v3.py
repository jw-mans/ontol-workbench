"""
Сборка TDL-файла (ontol-v3) в SVG через пакет ``uml_dsl`` (Graphviz).

Отдельный движок от v1: свой язык TDL, рендер через бинарь ``dot``. Пакет
``uml_dsl`` ставится в образ (``pip install -e src/ontol-v3``), сам ``dot``
ставится apt-пакетом ``graphviz``. Файл однофайловый — импортов между файлами в
TDL нет, поэтому материализация каталога не нужна.
"""

from __future__ import annotations

from app.services.render import BuildResult


def _render(
    text: str, *, analyzed: bool, strict: bool = False
) -> tuple[str | None, list[str], dict | None, str | None]:
    """
    Отрендерить TDL -> ``(svg, warnings, planarity, error)``.

    :param text: текст TDL
    :param analyzed: True = анализ планарности, False = только рендер
    :param strict: True = строгая семантика, False = lenient (только предупреждения)

    :return: svg (или None), список предупреждений, планарность (или None), ошибка (или None)
    """
    try:
        from uml_dsl.tdl_lexer import LexerError
        from uml_dsl.tdl_parser import ParseError

        if analyzed:
            from uml_dsl.tdl_run import tdl_to_svg_analyzed
        else:
            from uml_dsl.tdl_run import tdl_to_svg
    except ImportError as error:  # пакет uml_dsl не установлен в образе
        return None, [], None, f'Движок ontol-v3 (uml_dsl) недоступен: {error}'

    try:
        if analyzed:
            svg, warnings, planarity = tdl_to_svg_analyzed(text, strict=strict)
        else:
            svg, warnings, planarity = tdl_to_svg(text, strict=strict), [], None
    except LexerError as error:
        return None, [], None, f'Ошибка лексера: {error}'
    except ParseError as error:
        return None, [], None, f'Ошибка парсера: {error}'
    except ValueError as error:  # ошибка модели / семантической валидации
        return None, [], None, f'Ошибка модели: {error}'
    except RuntimeError as error:  # graphviz dot не найден / упал
        return None, [], None, str(error)

    return svg, warnings, planarity, None


def build_tdl(files: dict[str, str], entry: str) -> BuildResult:
    """
    Собрать ``.tdl`` в ``BuildResult`` (аналог v1 ``build_ontol``), мягко.

    :param files: словарь имя -> текст TDL
    :param entry: имя файла, с которого начинать сборку

    :return: BuildResult
    """
    svg, warnings, planarity, error = _render(files[entry], analyzed=True, strict=False)
    if error:
        return BuildResult(ok=False, error=error)
    return BuildResult(ok=True, svg=svg, warnings=warnings, planarity=planarity)


def build_tdl_svg(text: str, strict: bool = True) -> tuple[str | None, str | None]:
    """
    TDL -> SVG без анализа планарности. Для юнит-тестов; strict по умолчанию.

    :param text: текст TDL
    :param strict: True = строгая семантика, False = lenient (только предупреждения)
    
    :return: svg (или None), ошибка (или None)
    """
    svg, _warnings, _planarity, error = _render(text, analyzed=False, strict=strict)
    return svg, error
