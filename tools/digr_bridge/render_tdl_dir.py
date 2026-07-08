#!/usr/bin/env python3
"""
Прогнать папку .tdl от DiGR через ontol-v3: сложить SVG, кривые — в отчёт.

`python tools/digr_bridge/render_tdl_dir.py`
`python tools/digr_bridge/render_tdl_dir.py --in <папка> --out <папка>`
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_ONTOL_V3 = _REPO / "src" / "ontol-v3"
if str(_ONTOL_V3) not in sys.path:
    sys.path.insert(0, str(_ONTOL_V3))

_DEFAULT_IN = _REPO / "src" / "digr" / "ontology-pipeline" / "data" / "tdl"
_DEFAULT_OUT = _REPO / "tools" / "digr_bridge" / "out"


@dataclass
class FileReport:
    name: str
    status: str  # ok | ok_nonplanar | invalid_syntax | invalid_model | render_env
    classes: int = 0
    relations: int = 0
    svg: str | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)


@contextlib.contextmanager
def _quiet():
    # проглатываем stdout: движок печатает отладку на каждый validate_all
    with contextlib.redirect_stdout(io.StringIO()):
        yield


def _process(text: str, lenient: bool = False) -> tuple[FileReport, str | None]:
    """
    Отчёт и SVG (или None) по одному TDL. При lenient семантика уходит в
    предупреждения, синтаксис всё равно ошибка.
    """
    from uml_dsl.tdl_lexer import lex, LexerError
    from uml_dsl.tdl_parser import parse_tdl, ParseError
    from uml_dsl.tdl_build import build_diagram

    rep = FileReport(name="", status="ok")

    try:
        with _quiet():
            doc = parse_tdl(lex(text))
            diagram = build_diagram(doc)
            model_warnings = diagram.validate_all(strict=not lenient)
    except (LexerError, ParseError) as e:
        rep.status = "invalid_syntax"
        rep.error = f"{type(e).__name__}: {e}"
        return rep, None
    except ValueError as e:  # только строгий режим: первое нарушение = отказ
        rep.status = "invalid_model"
        rep.error = str(e)
        return rep, None
    if model_warnings:
        rep.warnings.extend(model_warnings)

    rep.classes = len(getattr(diagram, "classifiers", []) or [])
    rep.relations = (
        len(getattr(diagram, "generalizations", []))
        + len(getattr(diagram, "dependencies", []))
        + len(getattr(diagram, "associations", []))
        + len(getattr(diagram, "realizations", []))
    )

    # рендер
    from uml_dsl.tdl_run import tdl_to_svg_analyzed

    try:
        with _quiet():
            svg, warnings, planarity = tdl_to_svg_analyzed(text, strict=not lenient)
    except RuntimeError as e:  # dot не найден или упал
        rep.status = "render_env"
        rep.error = str(e)
        return rep, None

    rep.warnings = list(warnings)
    if planarity is not None:
        rep.status = "ok_nonplanar"
        rep.warnings.append(planarity.get("message", "непланарный граф"))
    return rep, svg


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Рендер папки DiGR .tdl через ontol-v3")
    ap.add_argument("--in", dest="in_dir", default=str(_DEFAULT_IN))
    ap.add_argument("--out", dest="out_dir", default=str(_DEFAULT_OUT))
    ap.add_argument(
        "--lenient",
        action="store_true",
        help="мягкий режим: рисовать невалидные модели с предупреждением "
        "(как v2-service), а не отклонять",
    )
    args = ap.parse_args(argv)

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)
    if not in_dir.is_dir():
        print(f"Папка не найдена: {in_dir}", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(in_dir.glob("*.tdl"))
    if not files:
        print(f"В {in_dir} нет .tdl", file=sys.stderr)
        return 2

    reports: list[FileReport] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        rep, svg = _process(text, lenient=args.lenient)
        rep.name = path.name
        if svg is not None:
            svg_path = out_dir / (path.stem + ".svg")
            svg_path.write_text(svg, encoding="utf-8")
            rep.svg = svg_path.name
        reports.append(rep)

    _write_reports(out_dir, in_dir, reports)
    _print_summary(reports, out_dir)
    # Ненулевой код, если есть по-настоящему кривые онтологии (не env).
    bad = [r for r in reports if r.status.startswith("invalid")]
    return 1 if bad else 0


def _write_reports(out_dir: Path, in_dir: Path, reports: list[FileReport]) -> None:
    (out_dir / "report.json").write_text(
        json.dumps(
            {"source": str(in_dir), "files": [asdict(r) for r in reports]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    lines = [
        f"# Отчёт моста DiGR -> ontol-v3",
        "",
        f"Источник: `{in_dir}`  ·  файлов: {len(reports)}",
        "",
        "| Файл | Статус | Классы | Связи | Замечание |",
        "|---|---|---:|---:|---|",
    ]
    for r in reports:
        note = "; ".join(x for x in (r.error, "; ".join(r.warnings)) if x)
        note = note.replace("|", "\\|")
        if len(note) > 120:
            note = note[:117] + "…"
        lines.append(
            f"| {r.name} | {_STATUS_LABEL.get(r.status, r.status)} "
            f"| {r.classes} | {r.relations} | {note} |"
        )
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


_STATUS_LABEL = {
    "ok": "OK",
    "ok_nonplanar": "OK (непланарный)",
    "invalid_syntax": "СИНТАКСИС",
    "invalid_model": "МОДЕЛЬ",
    "render_env": "нет graphviz",
}


def _print_summary(reports: list[FileReport], out_dir: Path) -> None:
    # Кириллица в stdout под Windows-консолью (cp1251) иначе падает.
    if hasattr(sys.stdout, "reconfigure"):
        with contextlib.suppress(Exception):
            sys.stdout.reconfigure(encoding="utf-8")
    by = {}
    for r in reports:
        by[r.status] = by.get(r.status, 0) + 1
    print("Итог:")
    for status, n in sorted(by.items()):
        print(f"  {_STATUS_LABEL.get(status, status):20} {n}")
    print(f"SVG и отчёт: {out_dir}")
    print(f"  report.md / report.json")


if __name__ == "__main__":
    raise SystemExit(main())
