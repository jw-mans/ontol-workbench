#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from review_chapter import CATEGORY_LABELS, CATEGORY_ORDER, build_review


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = next(
    (path for path in (SCRIPT_DIR, *SCRIPT_DIR.parents) if (path / ".git").exists()),
    SCRIPT_DIR,
)


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_paragraph_index(paragraphs_dir: Path) -> list[dict[str, Any]]:
    return json.loads((paragraphs_dir / "index.json").read_text(encoding="utf-8"))


def chapter_sort_key(chapter: str) -> int:
    return int(chapter)


def chapter_dir_name(chapter: str) -> str:
    return f"chapter_{int(chapter):02d}"


def chapter_image_count(reference_dir: Path, chapter: str) -> int:
    chapter_dir = reference_dir / chapter_dir_name(chapter)
    return sum(1 for _ in chapter_dir.glob("paragraph_*/*.png"))


def display_path(path: Path, base: Path) -> str:
    return os.path.relpath(path.resolve(), REPO_ROOT.resolve()).replace(os.sep, "/")


def category_totals(summaries: list[dict[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for summary in summaries:
        counter.update(summary.get("category_counts", {}))
    return {category: counter.get(category, 0) for category in CATEGORY_ORDER}


def chapter_table_rows(summaries: list[dict[str, Any]], reference_dir: Path) -> list[str]:
    rows = [
        "| Глава | Параграфов | Эталонных картинок | Сырых связей DiGr | Эталонных связей | Corrected TDL | Рендер |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for summary in summaries:
        chapter = str(summary["chapter"])
        rows.append(
            "| {chapter} | {paragraphs} | {images} | {raw} | {truth} | {corrected} | {rendered} |".format(
                chapter=chapter,
                paragraphs=len(summary.get("paragraphs", [])),
                images=chapter_image_count(reference_dir, chapter),
                raw=summary.get("raw_unique_relations", 0),
                truth=summary.get("textbook_relations_in_chapter_scope", 0),
                corrected=summary.get("corrected_relations", 0),
                rendered="OK" if summary.get("rendered") else "ERROR",
            )
        )
    return rows


def write_root_readme(out_dir: Path, reference_dir: Path, summaries: list[dict[str, Any]]) -> None:
    lines = [
        "# Сверка DiGr с эталонными онтологиями",
        "",
        "В этой папке лежит общий результат сверки по главам учебника. Каждая глава вынесена в отдельный каталог `chapter_XX`.",
        "",
        "## Корень папки",
        "",
        "- `README.md` — описание структуры результата.",
        "- `report.md` — общий отчет по всем главам.",
        "- `overview.json` — машинно-читаемая сводка по главам.",
        "",
        "## Каталог главы",
        "",
        "В каждом `chapter_XX/` лежат:",
        "",
        "- `raw.tdl` — общий сырой TDL по главе до исправлений.",
        "- `raw_relations.jsonl` — уникальные связи, которые DiGr выдал до сверки и исправлений.",
        "- `relations_review.jsonl` — построчная сверка найденных связей с эталоном.",
        "- `missed_from_textbook.jsonl` — эталонные связи, которые DiGr не нашел.",
        "- `corrected_relations.jsonl` — связи, вошедшие в исправленный TDL.",
        "- `corrected.tdl` — исправленная версия по главе.",
        "- `corrected.svg` — рендер исправленной версии, если глава проходит валидацию рендера.",
        "- `summary.json` — агрегированная статистика по главе и параграфам.",
        "- `paragraphs/` — разбор той же главы по параграфам.",
        "",
        "Сырые SVG не сохраняются: до исправлений часть raw TDL может не рендериться, а картинка часто не является полезным артефактом.",
        "",
        "## Эталон",
        "",
        f"Эталонные данные лежат в `{display_path(reference_dir, out_dir)}`: связи хранятся в `relations.json`, а картинки эталонных онтологий — в PNG-файлах рядом с ними. Каталоги `chapter_XX/paragraph_X_Y/` нужны только для группировки по главам и параграфам.",
        "",
        "## Главы",
        "",
        *chapter_table_rows(summaries, reference_dir),
    ]
    (out_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_root_report(out_dir: Path, reference_dir: Path, summaries: list[dict[str, Any]]) -> None:
    totals = category_totals(summaries)
    total_paragraphs = sum(len(summary.get("paragraphs", [])) for summary in summaries)
    rendered = sum(1 for summary in summaries if summary.get("rendered"))

    lines = [
        "# Общая сверка DiGr с учебником",
        "",
        "## Итог",
        "",
        f"- Глав: {len(summaries)}",
        f"- Параграфов в сверке: {total_paragraphs}",
        f"- Глав с успешным рендером: {rendered}",
        f"- Глав с ошибкой рендера: {len(summaries) - rendered}",
        f"- Уникальных сырых связей DiGr по главам: {sum(summary.get('raw_unique_relations', 0) for summary in summaries)}",
        f"- Эталонных связей учебника по главам: {sum(summary.get('textbook_relations_in_chapter_scope', 0) for summary in summaries)}",
        f"- Связей в corrected TDL по главам: {sum(summary.get('corrected_relations', 0) for summary in summaries)}",
        "",
        "## Категории",
        "",
        *(f"- `{category}` — {CATEGORY_LABELS[category]}: {totals[category]}" for category in CATEGORY_ORDER),
        "",
        "## По Главам",
        "",
        *chapter_table_rows(summaries, reference_dir),
        "",
        "## Примечания",
        "",
        "- Сверка читает эталонные `relations.json` из вложенных папок параграфов.",
        "- Эталонные связи должны попадать в `relations.json` только из ручного источника `reference_relations.json`; автоматические пары DiGr не используются как эталон.",
        "- Если связь есть в эталоне, но не найдена DiGr, она остается только в отчете и не добавляется в corrected TDL.",
    ]
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def review_all(args: argparse.Namespace) -> dict[str, Any]:
    paragraphs_dir = Path(args.paragraphs_dir)
    reference_dir = Path(args.reference_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    paragraph_index = load_paragraph_index(paragraphs_dir)
    chapters = sorted(
        {item["paragraph_id"].split(".", 1)[0] for item in paragraph_index},
        key=chapter_sort_key,
    )
    if args.chapters:
        selected = {chapter.strip() for chapter in args.chapters.split(",") if chapter.strip()}
        chapters = [chapter for chapter in chapters if chapter in selected]

    summaries: list[dict[str, Any]] = []
    for chapter in chapters:
        chapter_out_dir = out_dir / chapter_dir_name(chapter)
        namespace = argparse.Namespace(
            chapter=chapter,
            paragraphs_dir=str(paragraphs_dir),
            ground_truth=str(reference_dir / chapter_dir_name(chapter)),
            out_dir=str(chapter_out_dir),
            render=args.render,
            ontol_v3_root=args.ontol_v3_root,
        )
        summary = build_review(namespace)
        summaries.append(summary)
        if not args.keep_chapter_readmes:
            readme_path = chapter_out_dir / "README.md"
            if readme_path.exists():
                readme_path.unlink()
        if not args.keep_chapter_reports:
            report_path = chapter_out_dir / "report.md"
            if report_path.exists():
                report_path.unlink()

    overview = {
        "chapters": chapters,
        "chapter_summaries": summaries,
        "category_totals": category_totals(summaries),
    }
    write_json(out_dir / "overview.json", overview)
    write_root_readme(out_dir, reference_dir, summaries)
    write_root_report(out_dir, reference_dir, summaries)
    return overview


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review all chapters against DM reference ontology folders")
    parser.add_argument("--paragraphs-dir", default=str(SCRIPT_DIR / "data" / "paragraphs"))
    parser.add_argument("--reference-dir", default=str(SCRIPT_DIR / "data" / "dm_reference_ontologies"))
    parser.add_argument("--out-dir", default=str(SCRIPT_DIR / "data" / "chapter_reviews"))
    parser.add_argument("--chapters", default=None, help="Comma-separated chapter numbers, for example: 1,2,3")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--ontol-v3-root", default=None)
    parser.add_argument("--keep-chapter-readmes", action="store_true")
    parser.add_argument("--keep-chapter-reports", action="store_true")
    args = parser.parse_args(argv)

    overview = review_all(args)
    print(json.dumps(
        {
            "chapters": overview["chapters"],
            "category_totals": overview["category_totals"],
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
