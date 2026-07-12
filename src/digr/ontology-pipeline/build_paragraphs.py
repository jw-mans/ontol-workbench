#!/usr/bin/env python
from __future__ import annotations

import argparse
import bisect
import json
import re
import sys
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
for _p in (_ROOT / "engine" / "src", _ROOT / "relation-classifier"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from build_chunks_dataset import load_document, to_plain_word  # noqa: E402
from build_primary_ontology import LABEL_MAP, load_odmkeys  # noqa: E402
from build_tdl import RESERVED_WORDS, relation_line, unique_slug  # noqa: E402
from dsl import ActorDslEngine  # noqa: E402


SUBSECTION_TITLE_RE = re.compile(r"(?m)^(?!\s*%)\s*\\subsection\{([^}]*)\}")
NUMERIC_SUBSECTION_RE = re.compile(r"^(?P<id>\d+(?:\.\d+)+)\.?\s*(?P<title>.*)$")


@dataclass(slots=True)
class Paragraph:
    id: str
    title: str
    slug: str
    start: int
    end: int
    line: int


def jsonl_write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def line_index(text: str) -> list[int]:
    return [0] + [match.end() for match in re.finditer(r"\n", text)]


def line_of(starts: list[int], offset: int) -> int:
    return bisect.bisect_right(starts, offset)


def slugify(value: str) -> str:
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", value)
    slug = "_".join(word.lower() for word in words) or "paragraph"
    if slug[0].isdigit():
        slug = "p_" + slug
    if slug in RESERVED_WORDS:
        slug += "_"
    return slug


def load_paragraphs(engine: ActorDslEngine, document, *, include_unnumbered: bool) -> list[Paragraph]:
    result = engine.execute(document, "FIND subsection_scope RETURN nodes").to_dict()
    text = document.root.text
    lines = line_index(text)
    paragraphs: list[Paragraph] = []
    unnamed_count = 0

    for item in result["items"]:
        node = item["nodes"]
        start, end = node["start"], node["end"]
        head = text[start:min(start + 500, end)]
        match = SUBSECTION_TITLE_RE.search(head)
        if not match:
            continue
        match_start = start + match.start()
        line_start = text.rfind("\n", 0, match_start) + 1
        line_end = text.find("\n", match_start)
        if line_end == -1:
            line_end = len(text)
        if text[line_start:line_end].lstrip().startswith("%"):
            continue
        title = match.group(1).strip()
        numeric = NUMERIC_SUBSECTION_RE.match(title)
        if numeric:
            paragraph_id = numeric.group("id")
            slug_title = numeric.group("title").strip() or title
        elif include_unnumbered:
            unnamed_count += 1
            paragraph_id = f"unnumbered-{unnamed_count:02d}"
            slug_title = title
        else:
            continue

        paragraphs.append(
            Paragraph(
                id=paragraph_id,
                title=title,
                slug=f"{paragraph_id}_{slugify(slug_title)}",
                start=start,
                end=end,
                line=line_of(lines, start),
            )
        )

    return paragraphs


def paragraph_for_offset(paragraphs: list[Paragraph], offset: int) -> int | None:
    starts = [paragraph.start for paragraph in paragraphs]
    index = bisect.bisect_right(starts, offset) - 1
    if index >= 0 and paragraphs[index].start <= offset < paragraphs[index].end:
        return index
    return None


def normalize_kind(kind: str | None) -> str:
    if not kind:
        return "association"
    kind = kind.strip()
    return LABEL_MAP.get(kind.lower(), kind.lower())


def relation_key(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((a, b)))


def build_raw_tdl(title: str, concepts: list[str], relations: list[dict[str, Any]]) -> str:
    taken: dict[str, str] = {}
    for concept in concepts:
        unique_slug(concept, taken)
    for row in relations:
        unique_slug(row["index_a"], taken)
        unique_slug(row["index_b"], taken)

    lines = [f"-- {title}", ""]
    for concept in sorted(taken):
        lines.append(f"КЛАСС {taken[concept]}")
        lines.append(f"-- {concept}")
        lines.append("КОНЕЦ КЛАСС")
        lines.append("")

    for row in relations:
        a = taken[row["index_a"]]
        b = taken[row["index_b"]]
        kind = normalize_kind(row.get("predicted_relation_type"))
        lines.append(relation_line(kind, a, b))

    return "\n".join(lines) + "\n"


def render_svg(tdl_path: Path, svg_path: Path, ontol_v3_root: Path | None) -> str | None:
    if ontol_v3_root and ontol_v3_root.is_dir() and str(ontol_v3_root) not in sys.path:
        sys.path.insert(0, str(ontol_v3_root))
    try:
        from uml_dsl.tdl_run import tdl_to_svg
    except Exception as error:
        return f"ontol-v3 render is unavailable: {error}"

    try:
        svg = tdl_to_svg(tdl_path.read_text(encoding="utf-8"))
    except Exception as error:
        return str(error)

    svg_path.write_text(svg, encoding="utf-8")
    return None


def build_paragraphs(args: argparse.Namespace) -> list[dict[str, Any]]:
    document = load_document(args.tex, args.config_dir)
    text = document.root.text
    lines = line_index(text)
    engine = ActorDslEngine()

    paragraphs = load_paragraphs(engine, document, include_unnumbered=args.include_unnumbered)
    odmkeys = load_odmkeys(engine, document)
    paragraph_odmkeys: list[list[Any]] = [[] for _ in paragraphs]
    for occ in odmkeys:
        index = paragraph_for_offset(paragraphs, occ.start)
        if index is not None:
            paragraph_odmkeys[index].append(occ)

    rows = [
        json.loads(line)
        for line in Path(args.chunks).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    paragraph_concepts = [set(occ.index for occ in occs) for occs in paragraph_odmkeys]
    by_paragraph_relations: list[list[dict[str, Any]]] = [[] for _ in paragraphs]
    for row in rows:
        a = row["index_a"]
        b = row["index_b"]
        for index, concepts in enumerate(paragraph_concepts):
            if a in concepts and b in concepts:
                by_paragraph_relations[index].append(row)

    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    summary: list[dict[str, Any]] = []
    default_ontol_root = Path(__file__).resolve().parents[3] / "ontol-v3"
    ontol_root = Path(args.ontol_v3_root) if args.ontol_v3_root else default_ontol_root

    for paragraph, occs, relations in zip(paragraphs, paragraph_odmkeys, by_paragraph_relations):
        if not occs and not args.include_empty:
            continue

        folder = out_root / paragraph.slug
        folder.mkdir(parents=True, exist_ok=True)

        concepts = sorted(set(occ.index for occ in occs))
        relation_pairs = {relation_key(row["index_a"], row["index_b"]) for row in relations}
        pair_rows = [
            {
                "paragraph_id": paragraph.id,
                "concept_a": a,
                "concept_b": b,
                "has_relation": relation_key(a, b) in relation_pairs,
            }
            for a, b in combinations(concepts, 2)
        ]
        odmkey_rows = [
            {
                "paragraph_id": paragraph.id,
                "paragraph_title": paragraph.title,
                "index": occ.index,
                "surface": occ.name,
                "plain": to_plain_word(occ.index),
                "start": occ.start,
                "end": occ.end,
                "line": line_of(lines, occ.start),
            }
            for occ in occs
        ]
        relation_rows = [
            {
                "paragraph_id": paragraph.id,
                "concept_a": row["index_a"],
                "concept_b": row["index_b"],
                "predicted_relation_type": row.get("predicted_relation_type"),
                "ground_truth_type": row.get("ground_truth_type"),
                "status": row.get("status", "raw"),
                "reference_chunk": row.get("reference_chunk"),
            }
            for row in relations
        ]
        chunk_rows = [
            {
                "paragraph_id": paragraph.id,
                "concept_a": to_plain_word(row["index_a"]),
                "concept_b": to_plain_word(row["index_b"]),
                "relation_type": row.get("predicted_relation_type"),
                "reference_chunk": row.get("reference_chunk"),
                "index_a": row["index_a"],
                "index_b": row["index_b"],
                "source": "ontology-pipeline",
            }
            for row in relations
        ]

        jsonl_write(folder / "odmkeys.jsonl", odmkey_rows)
        jsonl_write(folder / "pairs_raw.jsonl", pair_rows)
        jsonl_write(folder / "relations_raw.jsonl", relation_rows)
        jsonl_write(folder / "chunks.jsonl", chunk_rows)

        tdl_path = folder / "raw.tdl"
        tdl_path.write_text(build_raw_tdl(paragraph.title, concepts, relations), encoding="utf-8")

        render_error = None
        if args.render:
            render_error = render_svg(tdl_path, folder / "raw.svg", ontol_root)
            error_path = folder / "raw_render_error.txt"
            if render_error:
                error_path.write_text(render_error + "\n", encoding="utf-8")
            elif error_path.exists():
                error_path.unlink()

        summary.append(
            {
                "paragraph_id": paragraph.id,
                "paragraph_title": paragraph.title,
                "folder": str(folder.relative_to(out_root)),
                "line": paragraph.line,
                "odmkey_occurrences": len(occs),
                "concepts": len(concepts),
                "pairs": len(pair_rows),
                "relations": len(relations),
                "rendered": args.render and render_error is None,
                "render_error": render_error,
            }
        )

    (out_root / "index.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build raw per-paragraph DiGr outputs for Ontol rendering")
    parser.add_argument("--tex", default="../data/all_lectures.tex")
    parser.add_argument("--config-dir", default="config/formats")
    parser.add_argument("--chunks", default="data/ontology_chunks.jsonl")
    parser.add_argument("--out-dir", default="data/paragraphs")
    parser.add_argument("--include-unnumbered", action="store_true")
    parser.add_argument("--include-empty", action="store_true")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--ontol-v3-root", default=None)
    args = parser.parse_args(argv)

    summary = build_paragraphs(args)
    print(f"paragraphs: {len(summary)}")
    print(f"odmkeys: {sum(item['odmkey_occurrences'] for item in summary)}")
    print(f"pairs: {sum(item['pairs'] for item in summary)}")
    print(f"relations: {sum(item['relations'] for item in summary)}")
    if args.render:
        rendered = sum(1 for item in summary if item["rendered"])
        failed = len(summary) - rendered
        print(f"rendered: {rendered}, failed: {failed}")
    print(f"-> {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
