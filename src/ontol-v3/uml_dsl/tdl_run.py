#!/usr/bin/env python3
"""
TDL → SVG: чтение файла .tdl, разбор, сборка модели, рендер в SVG.
Запуск: python -m uml_dsl.tdl_run <файл.tdl> [выход.svg|выход.png]
       или из корня: python -m uml_dsl.tdl_run examples/tdl/basic/example.tdl
       для PNG: python -m uml_dsl.tdl_run examples/tdl/basic/example.tdl out.png
"""
from __future__ import annotations

import sys
from pathlib import Path

# Корень проекта
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from uml_dsl.tdl_lexer import lex, LexerError
from uml_dsl.tdl_parser import parse_tdl, ParseError
from uml_dsl.tdl_build import build_diagram
from uml_dsl.graphviz_render import diagram_to_graphviz_svg


def tdl_to_svg(
    tdl_text: str,
    width: int = 900,
    height: int = 500,
    theme: str = "light",
    strict: bool = True,
) -> str:
    tokens = lex(tdl_text)
    doc = parse_tdl(tokens)
    diagram = build_diagram(doc)
    diagram.validate_all(strict=strict)
    return diagram_to_graphviz_svg(diagram, theme=theme)


def tdl_to_svg_analyzed(
    tdl_text: str, strict: bool = True
) -> tuple[str, list[str], dict | None]:
    """TDL → (SVG, warnings, planarity) с проверкой планарности.

    Планарен → раскладываем без пересечений рёбер (планарное вложение), planarity
    = None. Не планарен → рендерим как есть (graphviz) и возвращаем
    ``planarity = {kind, labels, message, subgraphs, count}``: ``kind`` — тип
    основного подграфа, ``labels`` — объединение классов всех подграфов-нарушителей
    (для красной подсветки), ``subgraphs`` — разбивка по каждому подграфу
    (``{kind, labels}``), ``count`` — их число.
    """
    tokens = lex(tdl_text)
    doc = parse_tdl(tokens)
    diagram = build_diagram(doc)
    # при strict=False нарушения вернутся списком, а не бросят исключение
    warnings = diagram.validate_all(strict=strict)
    return _analyzed_from_diagram(diagram, warnings)


def _analyzed_from_diagram(
    diagram, warnings: list[str]
) -> tuple[str, list[str], dict | None]:
    """Планарная раскладка (если возможна) и рендер готовой диаграммы в SVG."""
    from uml_dsl.planarity import analyze

    result = analyze(diagram)
    planarity: dict | None = None
    if result.is_planar and result.positions:
        diagram.positions = result.positions
        diagram.manual_layout = True
    elif not result.is_planar:
        planarity = {
            'kind': result.kind,
            'labels': result.labels,
            'message': result.warning(),
            'subgraphs': [
                {'kind': o.kind, 'labels': o.labels} for o in result.obstructions
            ],
            'count': len(result.obstructions),
        }
    return diagram_to_graphviz_svg(diagram), warnings, planarity


def merge_tdl_documents(texts):
    """Слить несколько TDL-текстов в один документ.

    Типы (классы, интерфейсы, типы данных, перечисления, шаблоны, классы
    ассоциаций) дедуплятся по имени — одноимённый считается тем же понятием,
    берётся первое объявление. Связи и команды размещения объединяются, точные
    дубли отбрасываются.
    """
    from uml_dsl.tdl_ast import (
        AssociationClassDecl,
        ClassDecl,
        DataTypeDecl,
        Document,
        EnumDecl,
        InterfaceDecl,
        LayoutBlock,
        TemplateDecl,
    )

    named = (
        ClassDecl, InterfaceDecl, DataTypeDecl,
        EnumDecl, TemplateDecl, AssociationClassDecl,
    )
    declarations: list = []
    seen_named: set[tuple[str, str]] = set()
    seen_other: list = []
    layout_commands: list = []

    for text in texts:
        doc = parse_tdl(lex(text))
        for decl in doc.declarations:
            if isinstance(decl, named):
                key = (type(decl).__name__, decl.name)
                if key in seen_named:
                    continue
                seen_named.add(key)
                declarations.append(decl)
            else:
                if decl in seen_other:
                    continue
                seen_other.append(decl)
                declarations.append(decl)
        if doc.layout is not None:
            layout_commands.extend(doc.layout.commands)

    layout = LayoutBlock(commands=layout_commands) if layout_commands else None
    return Document(declarations=declarations, layout=layout)


def tdl_merged_to_svg_analyzed(
    texts, strict: bool = True
) -> tuple[str, list[str], dict | None]:
    """Слить набор TDL-текстов в одну онтологию и отрендерить (с планарностью)."""
    diagram = build_diagram(merge_tdl_documents(texts))
    warnings = diagram.validate_all(strict=strict)
    return _analyzed_from_diagram(diagram, warnings)


def main() -> int:
    if len(sys.argv) < 2:
        print("Использование: python -m uml_dsl.tdl_run <файл.tdl> [выход.svg|выход.png]", file=sys.stderr)
        return 1
    tdl_path = Path(sys.argv[1])
    if not tdl_path.is_absolute():
        tdl_path = (Path.cwd() / tdl_path).resolve()
    if not tdl_path.exists():
        print(f"Файл не найден: {tdl_path}", file=sys.stderr)
        return 1
    out_path = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else tdl_path.with_suffix(".svg")

    try:
        text = tdl_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Ошибка чтения: {e}", file=sys.stderr)
        return 1

    try:
        svg = tdl_to_svg(text)
    except LexerError as e:
        print(f"Ошибка лексера: {e}", file=sys.stderr)
        return 1
    except ParseError as e:
        print(f"Ошибка парсера: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Ошибка модели: {e}", file=sys.stderr)
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    suf = out_path.suffix.lower()
    if suf == ".png":
        try:
            from uml_dsl.export import svg_to_png
            svg_to_png(svg, output=out_path)
        except ImportError as e:
            print(f"Для PNG нужен cairosvg: pip install cairosvg. {e}", file=sys.stderr)
            return 1
    elif suf == ".jpg" or suf == ".jpeg":
        try:
            from uml_dsl.export import svg_to_jpg
            svg_to_jpg(svg, output=out_path)
        except ImportError as e:
            print(f"Для JPG нужны cairosvg и Pillow: pip install cairosvg Pillow. {e}", file=sys.stderr)
            return 1
    else:
        out_path.write_text(svg, encoding="utf-8")
    print(f"Сохранено: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
