"""
Сборка онтологии на TDL (ontol-v3) в SVG через пакет ``uml_dsl`` (Graphviz).

Отдельный движок от v1: свой язык TDL, рендер через бинарь ``dot``. Пакет
``uml_dsl`` ставится в образ (``pip install -e src/ontol-v3``), сам ``dot``
ставится apt-пакетом ``graphviz``. Все ``.tdl``-файлы проекта (и подпроектов)
сливаются в одну онтологию: одноимённые классы дедуплятся, связи объединяются.
"""

from __future__ import annotations

from app.services.render import BuildResult


def _render(
    texts: list[str], *, strict: bool = False
) -> tuple[str | None, list[str], dict | None, str | None]:
    """
    Слить набор TDL-текстов в одну онтологию и отрендерить.

    :param texts: тексты ``.tdl`` (несколько файлов проекта)
    :param strict: True = строгая семантика, False = мягко (только предупреждения)

    :return: svg (или None), предупреждения, планарность (или None), ошибка (или None)
    """
    try:
        from uml_dsl.tdl_lexer import LexerError
        from uml_dsl.tdl_parser import ParseError
        from uml_dsl.tdl_run import tdl_merged_to_svg_analyzed
    except ImportError as error:  # пакет uml_dsl не установлен в образе
        return None, [], None, f'Движок ontol-v3 (uml_dsl) недоступен: {error}'

    try:
        svg, warnings, planarity = tdl_merged_to_svg_analyzed(texts, strict=strict)
    except LexerError as error:
        return None, [], None, f'Ошибка лексера: {error}'
    except ParseError as error:
        return None, [], None, f'Ошибка парсера: {error}'
    except ValueError as error:  # ошибка модели / семантической валидации
        return None, [], None, f'Ошибка модели: {error}'
    except RuntimeError as error:  # graphviz dot не найден / упал
        return None, [], None, str(error)

    return svg, warnings, planarity, None


def _tdl_texts(files: dict[str, str]) -> list[str]:
    """Тексты всех ``.tdl``-файлов набора, по имени (детерминированный порядок)."""
    return [content for name, content in sorted(files.items()) if name.endswith('.tdl')]


def build_tdl(files: dict[str, str], entry: str) -> BuildResult:
    """
    Собрать онтологию из всех ``.tdl`` набора в ``BuildResult`` (мягкий режим).

    :param files: словарь имя -> текст (файлы проекта и подпроектов)
    :param entry: точка входа (используется лишь для выбора движка выше)

    :return: BuildResult
    """
    texts = _tdl_texts(files) or [files[entry]]
    svg, warnings, planarity, error = _render(texts, strict=False)
    if error:
        return BuildResult(ok=False, error=error)
    return BuildResult(ok=True, svg=svg, warnings=warnings, planarity=planarity)


def build_tdl_svg(text: str, strict: bool = True) -> tuple[str | None, str | None]:
    """
    TDL -> SVG (одна онтология из одного текста). Для юнит-тестов; strict по умолчанию.

    :param text: текст TDL
    :param strict: True = строгая семантика, False = мягко (только предупреждения)

    :return: svg (или None), ошибка (или None)
    """
    svg, _warnings, _planarity, error = _render([text], strict=strict)
    return svg, error
