"""Сборка TDL-файла (ontol-v3) в SVG через пакет ``uml_dsl`` (Graphviz).

Отдельный движок от v1: свой язык TDL, рендер через бинарь ``dot``. Пакет
``uml_dsl`` ставится в образ (``pip install -e src/ontol-v3``), сам ``dot``
ставится apt-пакетом ``graphviz``. Файл однофайловый — импортов между файлами в
TDL нет, поэтому материализация каталога не нужна.
"""

from __future__ import annotations


def build_tdl_svg(text: str) -> tuple[str | None, str | None]:
    """Отрендерить TDL-текст в SVG.

    Возвращает ``(svg, error)``: при успехе — SVG-строка и ``None``; при ошибке —
    ``None`` и человекочитаемое сообщение. Ошибки лексера/парсера/модели и
    семантическая валидация (циклы наследования, конфликты композиции) приходят
    как ``ValueError`` из ``tdl_to_svg`` → в ``error``.
    """
    try:
        from uml_dsl.tdl_lexer import LexerError
        from uml_dsl.tdl_parser import ParseError
        from uml_dsl.tdl_run import tdl_to_svg
    except ImportError as error:  # пакет uml_dsl не установлен в образе
        return None, f'Движок ontol-v3 (uml_dsl) недоступен: {error}'

    try:
        svg = tdl_to_svg(text)
    except LexerError as error:
        return None, f'Ошибка лексера: {error}'
    except ParseError as error:
        return None, f'Ошибка парсера: {error}'
    except ValueError as error:  # ошибка модели / семантической валидации
        return None, f'Ошибка модели: {error}'
    except RuntimeError as error:  # graphviz dot не найден / упал
        return None, str(error)

    return svg, None
