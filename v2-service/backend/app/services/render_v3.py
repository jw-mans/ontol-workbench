"""Сборка TDL-файла (ontol-v3) в SVG через пакет ``uml_dsl`` (Graphviz).

Отдельный движок от v1: свой язык TDL, рендер через бинарь ``dot``. Пакет
``uml_dsl`` ставится в образ (``pip install -e src/ontol-v3``), сам ``dot``
ставится apt-пакетом ``graphviz``. Файл однофайловый — импортов между файлами в
TDL нет, поэтому материализация каталога не нужна.
"""

from __future__ import annotations

from app.services import storage
from app.services.render import BuildResult, content_digest


def _render(
    text: str, *, analyzed: bool
) -> tuple[str | None, list[str], dict | None, str | None]:
    """Отрендерить TDL -> ``(svg, warnings, planarity, error)``."""
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
            svg, warnings, planarity = tdl_to_svg_analyzed(text)
        else:
            svg, warnings, planarity = tdl_to_svg(text), [], None
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
    """Собрать ``.tdl``-файл в ``BuildResult`` (симметрично v1 ``build_ontol``).

    SVG заливается в MinIO (content-addressed), в ответ — presigned-ссылка
    ``svg_url``. Если S3 недоступен — деградируем на инлайн-``svg`` + warning,
    чтобы диаграмма всё равно отрисовалась.
    """
    svg, warnings, planarity, error = _render(files[entry], analyzed=True)
    if error:
        return BuildResult(ok=False, error=error)
    try:
        key = storage.artifact_key(content_digest('v3', entry, files), 'svg')
        storage.put_bytes(key, svg.encode('utf-8'), 'image/svg+xml')
        return BuildResult(
            ok=True,
            svg_url=storage.presigned_get(key),
            warnings=warnings,
            planarity=planarity,
        )
    except Exception as err:  # noqa: BLE001 — S3 недоступен: инлайн-фолбэк
        return BuildResult(
            ok=True,
            svg=svg,
            warnings=[*warnings, f'SVG upload failed: {err}'],
            planarity=planarity,
        )


def build_tdl_svg(text: str) -> tuple[str | None, str | None]:
    """Отрендерить TDL-текст в SVG (без анализа планарности). Для юнит-тестов."""
    svg, _warnings, _planarity, error = _render(text, analyzed=False)
    return svg, error
