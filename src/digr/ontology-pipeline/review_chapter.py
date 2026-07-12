#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from build_paragraphs import normalize_kind, render_svg
from build_tdl import relation_line, unique_slug

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = next(
    (path for path in (SCRIPT_DIR, *SCRIPT_DIR.parents) if (path / ".git").exists()),
    SCRIPT_DIR,
)

RAW_PARAGRAPH_ARTIFACTS = (
    "odmkeys.jsonl",
    "pairs_raw.jsonl",
    "relations_raw.jsonl",
    "chunks.jsonl",
    "raw.tdl",
    "raw_render_error.txt",
)

CATEGORY_ORDER = (
    "found_on_diagram_correct",
    "found_on_diagram_wrong_direction",
    "found_on_diagram_wrong_type",
    "found_on_diagram_wrong_direction_and_type",
    "found_not_on_diagram_accepted",
    "found_not_on_diagram_rejected",
    "not_found_from_diagram",
)

CATEGORY_LABELS = {
    "found_on_diagram_correct": "Найдены на диаграммах и верны",
    "found_on_diagram_wrong_direction": "Найдены на диаграммах, но неверно направление",
    "found_on_diagram_wrong_type": "Найдены на диаграммах, но неверен тип",
    "found_on_diagram_wrong_direction_and_type": "Найдены на диаграммах, но неверны направление и тип",
    "found_not_on_diagram_accepted": "Найдены вне диаграмм и приняты в corrected TDL",
    "found_not_on_diagram_rejected": "Найдены вне диаграмм, но отклонены валидаторными правилами",
    "not_found_from_diagram": "Есть в учебнике, но не найдены DiGr",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
        + ("\n" if rows else ""),
        encoding="utf-8",
    )


def ordered_category_counts(counter: Counter[str]) -> dict[str, int]:
    return {category: counter.get(category, 0) for category in CATEGORY_ORDER}


def format_render_error(error: str | None) -> str | None:
    if not error:
        return None
    parts = [part.strip() for part in error.split(";") if part.strip()]
    if len(parts) <= 1:
        return error
    return "\n".join(parts)


def repo_display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return os.path.relpath(resolved, REPO_ROOT.resolve()).replace(os.sep, "/")
    except ValueError:
        return path.as_posix()


def copy_raw_paragraph_artifacts(source_dir: Path, paragraph_dir: Path) -> None:
    raw_dir = paragraph_dir / "raw"
    if raw_dir.exists():
        shutil.rmtree(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    for filename in RAW_PARAGRAPH_ARTIFACTS:
        source_path = source_dir / filename
        if source_path.exists():
            shutil.copy2(source_path, raw_dir / filename)


def pair_key(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((a, b)))


def stable_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def ground_truth_key(item: dict[str, Any]) -> tuple[str, ...]:
    return (
        stable_value(item.get("name1")),
        stable_value(item.get("name2")),
        stable_value(item.get("type")),
        stable_value(item.get("predicate")),
        stable_value(item.get("predicateInv")),
        stable_value(item.get("pole1")),
        stable_value(item.get("pole2")),
        stable_value(item.get("paragraph")),
        stable_value(item.get("page")),
        stable_value(item.get("diagram")),
    )


def load_ground_truth_rows(path: Path) -> list[dict[str, Any]]:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))

    if not path.is_dir():
        return []

    rows: list[dict[str, Any]] = []
    for relations_path in sorted(path.glob("**/relations.json")):
        loaded = json.loads(relations_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, list):
            raise ValueError(f"Expected list in {relations_path}")
        rows.extend(loaded)
    return rows


def alignment_path_for(ground_truth_path: Path) -> Path:
    if ground_truth_path.is_dir():
        return ground_truth_path.parent / "name_alignment.json"
    return ground_truth_path.parent / "name_alignment.json"


def clean_concept_name(value: Any) -> str:
    text = stable_value(value)
    text = text.replace("\\", " ")
    return re.sub(r"\s+", " ", text).strip()


def concept_lookup_key(value: Any) -> str:
    text = clean_concept_name(value)
    text = (
        text.replace("ё", "е")
        .replace("Ё", "Е")
        .replace("–", "-")
        .replace("—", "-")
        .replace("--", "-")
    )
    return re.sub(r"\s+", " ", text).strip().casefold()


def load_name_alignment(ground_truth_path: Path) -> dict[str, Any]:
    alignment_path = alignment_path_for(ground_truth_path)
    if not alignment_path.exists():
        return {
            "mappings": {},
            "mappings_by_lookup": {},
            "ignored_concepts": set(),
            "ignored_by_lookup": set(),
        }

    data = json.loads(alignment_path.read_text(encoding="utf-8"))
    mappings = {
        clean_concept_name(source): clean_concept_name(target)
        for source, target in data.get("mappings", {}).items()
    }
    return {
        "mappings": mappings,
        "mappings_by_lookup": {
            concept_lookup_key(source): target
            for source, target in mappings.items()
        },
        "ignored_concepts": {
            clean_concept_name(concept)
            for concept in data.get("ignored_concepts", [])
        },
        "ignored_by_lookup": {
            concept_lookup_key(concept)
            for concept in data.get("ignored_concepts", [])
        },
    }


def apply_concept_mapping(value: Any, alignment: dict[str, Any]) -> str:
    concept = clean_concept_name(value)
    if concept in alignment["mappings"]:
        return alignment["mappings"][concept]
    return alignment["mappings_by_lookup"].get(concept_lookup_key(concept), concept)


def is_ignored_concept(value: Any, alignment: dict[str, Any]) -> bool:
    concept = clean_concept_name(value)
    mapped = apply_concept_mapping(concept, alignment)
    return (
        concept in alignment["ignored_concepts"]
        or mapped in alignment["ignored_concepts"]
        or concept_lookup_key(concept) in alignment["ignored_by_lookup"]
        or concept_lookup_key(mapped) in alignment["ignored_by_lookup"]
    )


def path_exists(graph: dict[str, set[str]], start: str, target: str) -> bool:
    stack = [start]
    seen: set[str] = set()
    while stack:
        node = stack.pop()
        if node == target:
            return True
        if node in seen:
            continue
        seen.add(node)
        stack.extend(graph.get(node, ()))
    return False


def relation_tdl(title: str, relations: list[dict[str, Any]]) -> str:
    taken: dict[str, str] = {}
    for row in relations:
        unique_slug(row["concept_a"], taken)
        unique_slug(row["concept_b"], taken)

    lines = [f"-- {title}", ""]
    for concept in sorted(taken):
        lines.append(f"КЛАСС {taken[concept]}")
        lines.append(f"-- {concept}")
        lines.append("КОНЕЦ КЛАСС")
        lines.append("")

    for row in relations:
        a = taken[row["concept_a"]]
        b = taken[row["concept_b"]]
        lines.append(relation_line(row["relation_type"], a, b))
    return "\n".join(lines) + "\n"


def add_safely(
    relation: dict[str, Any],
    inheritance_graph: dict[str, set[str]],
    composition_parts: dict[str, str],
) -> tuple[bool, str | None]:
    a = relation["concept_a"]
    b = relation["concept_b"]
    kind = relation["relation_type"]

    if kind == "generalization":
        if a == b:
            return False, "self inheritance"
        if path_exists(inheritance_graph, b, a):
            return False, "inheritance cycle"
        inheritance_graph.setdefault(a, set()).add(b)
        return True, None

    if kind == "composition":
        owner = composition_parts.get(b)
        if owner is not None and owner != a:
            return False, f"composition part already belongs to {owner}"
        composition_parts[b] = a
        return True, None

    return True, None


def build_review(args: argparse.Namespace) -> dict[str, Any]:
    paragraphs_root = Path(args.paragraphs_dir)
    ground_truth_path = Path(args.ground_truth)
    name_alignment = load_name_alignment(ground_truth_path)
    ignored_concepts = name_alignment["ignored_concepts"]
    index = json.loads((paragraphs_root / "index.json").read_text(encoding="utf-8"))
    chapter_prefix = f"{args.chapter}."
    paragraphs = [item for item in index if item["paragraph_id"].startswith(chapter_prefix)]
    if not paragraphs:
        raise ValueError(f"No paragraphs found for chapter {args.chapter}")

    concepts_by_paragraph: dict[str, set[str]] = {}
    chapter_concepts: set[str] = set()
    raw_by_pair: dict[tuple[str, str], dict[str, Any]] = {}

    for paragraph in paragraphs:
        folder = paragraphs_root / paragraph["folder"]
        paragraph_id = paragraph["paragraph_id"]
        concepts = {
            apply_concept_mapping(row["index"], name_alignment)
            for row in read_jsonl(folder / "odmkeys.jsonl")
            if not is_ignored_concept(row["index"], name_alignment)
        }
        concepts_by_paragraph[paragraph_id] = concepts
        chapter_concepts.update(concepts)

        for row in read_jsonl(folder / "relations_raw.jsonl"):
            if (
                is_ignored_concept(row["concept_a"], name_alignment)
                or is_ignored_concept(row["concept_b"], name_alignment)
            ):
                continue
            concept_a = apply_concept_mapping(row["concept_a"], name_alignment)
            concept_b = apply_concept_mapping(row["concept_b"], name_alignment)
            key = (concept_a, concept_b)
            existing = raw_by_pair.get(key)
            if existing is None:
                raw_by_pair[key] = {
                    "concept_a": concept_a,
                    "concept_b": concept_b,
                    "raw_concept_a": clean_concept_name(row["concept_a"]),
                    "raw_concept_b": clean_concept_name(row["concept_b"]),
                    "predicted_relation_type": normalize_kind(row.get("predicted_relation_type")),
                    "paragraphs": [paragraph_id],
                    "reference_chunks": [row.get("reference_chunk")],
                    "raw_status": row.get("status"),
                    "raw_ground_truth_type": row.get("ground_truth_type"),
                }
            else:
                existing["paragraphs"].append(paragraph_id)
                if row.get("reference_chunk"):
                    existing["reference_chunks"].append(row.get("reference_chunk"))

    ground_truth_all_raw: list[dict[str, Any]] = []
    for row in load_ground_truth_rows(ground_truth_path):
        if (
            is_ignored_concept(row.get("name1"), name_alignment)
            or is_ignored_concept(row.get("name2"), name_alignment)
        ):
            continue
        aligned_row = dict(row)
        aligned_row["original_name1"] = clean_concept_name(row.get("name1"))
        aligned_row["original_name2"] = clean_concept_name(row.get("name2"))
        aligned_row["name1"] = apply_concept_mapping(row.get("name1"), name_alignment)
        aligned_row["name2"] = apply_concept_mapping(row.get("name2"), name_alignment)
        ground_truth_all_raw.append(aligned_row)
    ground_truth_seen: set[tuple[str, ...]] = set()
    ground_truth_all: list[dict[str, Any]] = []
    for item in ground_truth_all_raw:
        key = ground_truth_key(item)
        if key in ground_truth_seen:
            continue
        ground_truth_seen.add(key)
        ground_truth_all.append(item)

    ground_truth: list[dict[str, Any]] = []
    for index, item in enumerate(ground_truth_all):
        source_paragraph = item.get("paragraph")
        if source_paragraph:
            in_chapter = str(source_paragraph).startswith(chapter_prefix)
        else:
            in_chapter = item["name1"] in chapter_concepts and item["name2"] in chapter_concepts
        if not in_chapter:
            continue

        ground_truth.append(
            {
                "id": index,
                "concept_a": item["name1"],
                "concept_b": item["name2"],
                "relation_type": normalize_kind(item["type"]),
                "ground_truth_type": item["type"],
                "ground_truth_paragraph": source_paragraph,
                "ground_truth_page": item.get("page"),
                "ground_truth_diagram": item.get("diagram"),
                "ground_truth_predicate": item.get("predicate"),
                "ground_truth_predicate_inv": item.get("predicateInv"),
            }
        )

    gt_by_unordered: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in ground_truth:
        gt_by_unordered[pair_key(row["concept_a"], row["concept_b"])].append(row)

    rows: list[dict[str, Any]] = []
    claimed_ground_truth: set[int] = set()

    for (a, b), raw in sorted(raw_by_pair.items()):
        predicted = raw["predicted_relation_type"]
        candidates = gt_by_unordered.get(pair_key(a, b), [])

        exact_matching = [
            gt for gt in candidates
            if gt["concept_a"] == a and gt["concept_b"] == b and gt["relation_type"] == predicted
        ]
        exact = [
            gt for gt in candidates
            if gt["concept_a"] == a and gt["concept_b"] == b
        ]
        reverse_matching = [
            gt for gt in candidates
            if gt["concept_a"] == b and gt["concept_b"] == a and gt["relation_type"] == predicted
        ]
        reverse = [
            gt for gt in candidates
            if gt["concept_a"] == b and gt["concept_b"] == a
        ]

        chosen_gt = next(
            (
                options[0]
                for options in (exact_matching, exact, reverse_matching, reverse, candidates)
                if options
            ),
            None,
        )

        if chosen_gt is not None:
            claimed_ground_truth.add(chosen_gt["id"])
            exact_direction = chosen_gt["concept_a"] == a and chosen_gt["concept_b"] == b
            type_matches = predicted == chosen_gt["relation_type"]
            if exact_direction and type_matches:
                category = "found_on_diagram_correct"
            elif exact_direction:
                category = "found_on_diagram_wrong_type"
            elif type_matches:
                category = "found_on_diagram_wrong_direction"
            else:
                category = "found_on_diagram_wrong_direction_and_type"
            corrected_a = chosen_gt["concept_a"]
            corrected_b = chosen_gt["concept_b"]
            corrected_kind = chosen_gt["relation_type"]
            ground_truth_type = chosen_gt["ground_truth_type"]
            decision = "use_textbook_relation"
            ground_truth_paragraph = chosen_gt.get("ground_truth_paragraph")
            ground_truth_page = chosen_gt.get("ground_truth_page")
            ground_truth_diagram = chosen_gt.get("ground_truth_diagram")
            ground_truth_predicate = chosen_gt.get("ground_truth_predicate")
        else:
            category = "found_not_on_diagram_candidate"
            corrected_a = a
            corrected_b = b
            corrected_kind = predicted
            ground_truth_type = None
            decision = "accept_if_valid"
            ground_truth_paragraph = None
            ground_truth_page = None
            ground_truth_diagram = None
            ground_truth_predicate = None

        rows.append(
            {
                "category": category,
                "decision": decision,
                "concept_a": a,
                "concept_b": b,
                "predicted_relation_type": predicted,
                "ground_truth_type": ground_truth_type,
                "corrected_concept_a": corrected_a,
                "corrected_concept_b": corrected_b,
                "corrected_relation_type": corrected_kind,
                "paragraphs": sorted(set(raw["paragraphs"])),
                "ground_truth_paragraph": ground_truth_paragraph,
                "ground_truth_page": ground_truth_page,
                "ground_truth_diagram": ground_truth_diagram,
                "ground_truth_predicate": ground_truth_predicate,
                "reference_chunk": next((x for x in raw["reference_chunks"] if x), None),
            }
        )

    for gt in ground_truth:
        if gt["id"] in claimed_ground_truth:
            continue
        if gt.get("ground_truth_paragraph"):
            paragraph_ids = [gt["ground_truth_paragraph"]]
        else:
            paragraph_ids = [
                paragraph_id
                for paragraph_id, concepts in concepts_by_paragraph.items()
                if gt["concept_a"] in concepts and gt["concept_b"] in concepts
            ]
        rows.append(
            {
                "category": "not_found_from_diagram",
                "decision": "report_only",
                "concept_a": gt["concept_a"],
                "concept_b": gt["concept_b"],
                "predicted_relation_type": None,
                "ground_truth_type": gt["ground_truth_type"],
                "corrected_concept_a": gt["concept_a"],
                "corrected_concept_b": gt["concept_b"],
                "corrected_relation_type": gt["relation_type"],
                "paragraphs": paragraph_ids,
                "ground_truth_paragraph": gt.get("ground_truth_paragraph"),
                "ground_truth_page": gt.get("ground_truth_page"),
                "ground_truth_diagram": gt.get("ground_truth_diagram"),
                "ground_truth_predicate": gt.get("ground_truth_predicate"),
                "reference_chunk": None,
            }
        )

    priority = {
        "found_on_diagram_correct": 0,
        "found_on_diagram_wrong_direction": 1,
        "found_on_diagram_wrong_type": 2,
        "found_on_diagram_wrong_direction_and_type": 3,
        "found_not_on_diagram_candidate": 4,
    }
    corrected_relations: list[dict[str, Any]] = []
    included_keys: set[tuple[str, str, str]] = set()
    inheritance_graph: dict[str, set[str]] = {}
    composition_parts: dict[str, str] = {}

    for row in sorted(rows, key=lambda item: (priority.get(item["category"], 99), item["corrected_concept_a"], item["corrected_concept_b"])):
        if row["decision"] == "report_only":
            row["included_in_corrected_tdl"] = False
            continue
        relation = {
            "concept_a": row["corrected_concept_a"],
            "concept_b": row["corrected_concept_b"],
            "relation_type": row["corrected_relation_type"],
        }
        key = (relation["concept_a"], relation["concept_b"], relation["relation_type"])
        if key in included_keys:
            row["included_in_corrected_tdl"] = False
            row["validation_decision"] = "duplicate"
            continue
        accepted, reason = add_safely(relation, inheritance_graph, composition_parts)
        row["included_in_corrected_tdl"] = accepted
        if accepted:
            included_keys.add(key)
            corrected_relations.append(relation)
            if row["category"] == "found_not_on_diagram_candidate":
                row["category"] = "found_not_on_diagram_accepted"
                row["decision"] = "accepted_by_validation_rules"
        else:
            row["validation_decision"] = reason
            if row["category"] == "found_not_on_diagram_candidate":
                row["category"] = "found_not_on_diagram_rejected"
                row["decision"] = "rejected_by_validation_rules"

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(out_dir / "relations_review.jsonl", rows)
    write_jsonl(
        out_dir / "missed_from_textbook.jsonl",
        [row for row in rows if row["category"] == "not_found_from_diagram"],
    )
    write_jsonl(
        out_dir / "corrected_relations.jsonl",
        [
            row
            for row in rows
            if row.get("included_in_corrected_tdl")
        ],
    )

    raw_relations = [
        {
            "concept_a": raw["concept_a"],
            "concept_b": raw["concept_b"],
            "relation_type": raw["predicted_relation_type"],
            "paragraphs": sorted(set(raw["paragraphs"])),
            "reference_chunk": next(
                (chunk for chunk in raw.get("reference_chunks", []) if chunk),
                None,
            ),
            "raw_status": raw.get("raw_status"),
            "raw_ground_truth_type": raw.get("raw_ground_truth_type"),
        }
        for raw in raw_by_pair.values()
        if raw.get("predicted_relation_type")
    ]
    raw_relations.sort(
        key=lambda row: (
            row["concept_a"],
            row["concept_b"],
            row["relation_type"],
        )
    )
    write_jsonl(out_dir / "raw_relations.jsonl", raw_relations)
    (out_dir / "raw.tdl").write_text(
        relation_tdl(f"Chapter {args.chapter}: raw DiGr relations", raw_relations),
        encoding="utf-8",
    )

    corrected_tdl = relation_tdl(f"Chapter {args.chapter}: reviewed DiGr relations", corrected_relations)
    tdl_path = out_dir / "corrected.tdl"
    svg_path = out_dir / "corrected.svg"
    tdl_path.write_text(corrected_tdl, encoding="utf-8")

    render_error = None
    if args.render:
        render_error = render_svg(tdl_path, svg_path, Path(args.ontol_v3_root) if args.ontol_v3_root else None)
        render_error = format_render_error(render_error)
        error_path = out_dir / "corrected_render_error.txt"
        if render_error:
            if svg_path.exists():
                svg_path.unlink()
            error_path.write_text(render_error + "\n", encoding="utf-8")
        elif error_path.exists():
            error_path.unlink()

    category_counts = Counter(row["category"] for row in rows)
    ordered_counts = ordered_category_counts(category_counts)
    summary = {
        "chapter": args.chapter,
        "paragraphs": [item["paragraph_id"] for item in paragraphs],
        "ground_truth_source": repo_display_path(Path(args.ground_truth)),
        "ignored_concepts": sorted(ignored_concepts),
        "chapter_concepts": len(chapter_concepts),
        "raw_unique_relations": len(raw_by_pair),
        "textbook_relations_in_chapter_scope": len(ground_truth),
        "textbook_unique_relation_pairs_in_chapter_scope": len(gt_by_unordered),
        "category_counts": ordered_counts,
        "corrected_relations": len(corrected_relations),
        "rendered": args.render and render_error is None,
        "render_error": render_error,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    report_lines = [
        f"# Сверка DiGr с учебником: глава {args.chapter}",
        "",
        "## Итог",
        "",
        f"- Параграфы: {', '.join(summary['paragraphs'])}",
        f"- Понятий odmkey в области главы: {summary['chapter_concepts']}",
        f"- Уникальных связей, найденных DiGr: {summary['raw_unique_relations']}",
        f"- Эталонных связей учебника в области главы: {summary['textbook_relations_in_chapter_scope']}",
        f"- Уникальных пар понятий в эталонных связях: {summary['textbook_unique_relation_pairs_in_chapter_scope']}",
        f"- Игнорируемых annotation/comment-понятий: {len(summary['ignored_concepts'])}",
        f"- Связей в исправленном TDL: {summary['corrected_relations']}",
        "",
        "## Категории",
        "",
        *(f"- `{category}` — {CATEGORY_LABELS[category]}: {ordered_counts[category]}" for category in CATEGORY_ORDER),
        "",
        "## Правило исправления",
        "",
        "Если связь найдена DiGr и есть на диаграмме учебника, в corrected TDL используется тип и направление из учебника.",
        "Если связь найдена DiGr, но отсутствует на диаграмме, она добавляется только если не создает цикл наследования и не нарушает ограничение композиции.",
        "Если связь есть на диаграмме учебника, но не найдена DiGr, она остается только в отчете и не добавляется в corrected TDL.",
        "",
        "## Примечания",
        "",
        f"- Машинно-читаемый эталон: `{summary['ground_truth_source']}`.",
        "- Если эталон передан папкой, скрипт читает все вложенные `relations.json` из параграфов.",
    ]
    if render_error:
        report_lines.extend(["", "## Ошибка рендера", "", render_error])
    (out_dir / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    (out_dir / "README.md").write_text(
        "\n".join(
            [
                f"# Результаты сверки главы {args.chapter}",
                "",
                "В этой папке лежит полный результат по главе: сырой вывод DiGr, сверка с машинно-читаемым эталоном, исправленный TDL и результат рендера.",
                "Сырые SVG не сохраняются: до исправлений часть raw TDL может не рендериться, а картинка часто не является полезным артефактом.",
                "",
                "## Корень папки",
                "",
                "- `raw.tdl` — общий сырой TDL по главе до исправлений.",
                "- `raw_relations.jsonl` — уникальные связи, которые DiGr выдал до сверки и исправлений.",
                "- `relations_review.jsonl` — построчная сверка найденных связей с эталоном.",
                "- `missed_from_textbook.jsonl` — эталонные связи, которые DiGr не нашел.",
                "- `corrected_relations.jsonl` — связи, вошедшие в исправленный TDL.",
                "- `corrected.tdl` — исправленная версия по главе.",
                "- `corrected.svg` — рендер исправленной версии.",
                "- `summary.json` — агрегированная статистика по главе и параграфам.",
                "- `report.md` — отчет.",
                "",
                "## Параграфы",
                "",
                "В `paragraphs/<paragraph>/raw/` лежат исходные данные параграфа: `odmkeys.jsonl`, `pairs_raw.jsonl`, `relations_raw.jsonl`, `chunks.jsonl` и `raw.tdl`.",
                "Каталог `data/paragraphs` считается временным слоем сборки. Если нужно пересобрать эту папку заново, сначала нужно запустить `build_paragraphs.py`, а потом `review_chapter.py`.",
                "",
                "## Эталон",
                "",
                f"Сейчас сверка идет с `{summary['ground_truth_source']}`. Это может быть один JSON-файл или папка с `relations.json` по параграфам.",
                "Для визуальной сверки рядом с эталонными связями можно хранить PNG-страницы с онтологиями из учебника.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    paragraph_summaries: list[dict[str, Any]] = []
    paragraph_out_root = out_dir / "paragraphs"
    paragraph_out_root.mkdir(parents=True, exist_ok=True)

    for paragraph in paragraphs:
        paragraph_id = paragraph["paragraph_id"]
        paragraph_rows = [
            dict(row)
            for row in rows
            if paragraph_id in row.get("paragraphs", [])
        ]
        paragraph_relations = [
            {
                "concept_a": row["corrected_concept_a"],
                "concept_b": row["corrected_concept_b"],
                "relation_type": row["corrected_relation_type"],
            }
            for row in paragraph_rows
            if row.get("included_in_corrected_tdl")
        ]

        paragraph_dir = paragraph_out_root / paragraph["folder"]
        paragraph_dir.mkdir(parents=True, exist_ok=True)
        copy_raw_paragraph_artifacts(paragraphs_root / paragraph["folder"], paragraph_dir)
        write_jsonl(paragraph_dir / "relations_review.jsonl", paragraph_rows)
        write_jsonl(
            paragraph_dir / "missed_from_textbook.jsonl",
            [row for row in paragraph_rows if row["category"] == "not_found_from_diagram"],
        )
        write_jsonl(
            paragraph_dir / "corrected_relations.jsonl",
            [row for row in paragraph_rows if row.get("included_in_corrected_tdl")],
        )

        paragraph_tdl_path = paragraph_dir / "corrected.tdl"
        paragraph_svg_path = paragraph_dir / "corrected.svg"
        paragraph_tdl_path.write_text(
            relation_tdl(
                f"Paragraph {paragraph_id}: reviewed DiGr relations",
                paragraph_relations,
            ),
            encoding="utf-8",
        )

        paragraph_render_error = None
        if args.render:
            paragraph_render_error = render_svg(
                paragraph_tdl_path,
                paragraph_svg_path,
                Path(args.ontol_v3_root) if args.ontol_v3_root else None,
            )
            paragraph_render_error = format_render_error(paragraph_render_error)
            paragraph_error_path = paragraph_dir / "corrected_render_error.txt"
            if paragraph_render_error:
                if paragraph_svg_path.exists():
                    paragraph_svg_path.unlink()
                paragraph_error_path.write_text(paragraph_render_error + "\n", encoding="utf-8")
            elif paragraph_error_path.exists():
                paragraph_error_path.unlink()

        paragraph_counts = Counter(row["category"] for row in paragraph_rows)
        paragraph_ordered_counts = ordered_category_counts(paragraph_counts)
        paragraph_summary = {
            "paragraph_id": paragraph_id,
            "paragraph_title": paragraph["paragraph_title"],
            "folder": paragraph["folder"],
            "relations_reviewed": len(paragraph_rows),
            "corrected_relations": len(paragraph_relations),
            "category_counts": paragraph_ordered_counts,
            "rendered": args.render and paragraph_render_error is None,
            "render_error": paragraph_render_error,
        }
        paragraph_summaries.append(paragraph_summary)
        (paragraph_dir / "summary.json").write_text(
            json.dumps(paragraph_summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    paragraph_report_lines = [
        "",
        "## По параграфам",
        "",
        "| Параграф | Связей в сверке | Corrected TDL | Рендер |",
        "|---|---:|---:|---|",
    ]
    for item in paragraph_summaries:
        paragraph_report_lines.append(
            "| {paragraph_id} | {relations_reviewed} | {corrected_relations} | {rendered} |".format(
                paragraph_id=item["paragraph_id"],
                relations_reviewed=item["relations_reviewed"],
                corrected_relations=item["corrected_relations"],
                rendered="OK" if item["rendered"] else "ERROR",
            )
        )
    with (out_dir / "report.md").open("a", encoding="utf-8") as file:
        file.write("\n".join(paragraph_report_lines) + "\n")

    summary["paragraph_reviews"] = paragraph_summaries
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review DiGr paragraph TDL against textbook relations for one chapter")
    parser.add_argument("--chapter", default="1")
    parser.add_argument("--paragraphs-dir", default="data/paragraphs")
    parser.add_argument("--ground-truth", default="data/dm_reference_ontologies/chapter_01")
    parser.add_argument("--out-dir", default="data/chapter_reviews/chapter_01")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--ontol-v3-root", default=None)
    args = parser.parse_args(argv)

    summary = build_review(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
