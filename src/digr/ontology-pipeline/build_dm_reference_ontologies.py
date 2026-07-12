#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

from pypdf import PdfReader


SCRIPT_DIR = Path(__file__).resolve().parent
DIGR_ROOT = SCRIPT_DIR.parent
ONTOLOGY_TITLE_PREFIX = "Онтология"

IMAGE_PARAGRAPH_OVERRIDES = {
    "ODM3_1.png": "3.1_4",
    "ODM3_2.png": "3.5",
    "ODM4_34.png": "4.3_4",
    "ODM5_1_2.png": "5.2",
    "ODM5_2.png": "5.3",
    "ODM5_3.png": "5.4",
    "ODM5_4.png": "5.5_7",
    "ODM_9_1_2.png": "9.1_2",
    "ODM_10_3.png": "10.2_3",
    "ODM_10_6.png": "10.4_6",
}


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_commented_line(text: str, offset: int) -> bool:
    line_start = text.rfind("\n", 0, offset) + 1
    return text[line_start:offset].lstrip().startswith("%")


def included_images(block: str) -> list[str]:
    images: list[str] = []
    for match in re.finditer(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]*)\}", block):
        if not is_commented_line(block, match.start()):
            images.append(match.group(1))
    return images


def current_section_title(text: str, offset: int, command: str) -> str | None:
    matches = list(re.finditer(rf"\\{command}\{{([^}}]*)\}}", text[:offset]))
    return matches[-1].group(1).strip() if matches else None


def infer_paragraph_id(subsection: str | None, images: list[str]) -> str | None:
    for image in images:
        override = IMAGE_PARAGRAPH_OVERRIDES.get(Path(image).name)
        if override:
            return override

    if subsection:
        match = re.search(r"(?P<chapter>\d+)\.(?P<paragraph>\d+)", subsection)
        if match:
            return f"{match.group('chapter')}.{match.group('paragraph')}"

    for image in images:
        stem = Path(image).stem
        match = re.match(r"ODM_?(?P<chapter>\d+)_(?P<paragraph>\d+)", stem, re.IGNORECASE)
        if not match:
            continue
        chapter = match.group("chapter")
        paragraph = match.group("paragraph")
        if len(paragraph) > 1:
            paragraph = "_".join(paragraph)
        return f"{chapter}.{paragraph}"
    return None


def paragraph_dir_name(paragraph_id: str) -> str:
    return "paragraph_" + paragraph_id.replace(".", "_")


def chapter_dir_name(chapter: str) -> str:
    return f"chapter_{int(chapter):02d}"


def paragraph_chapter(paragraph_id: str) -> str:
    return paragraph_id.split(".", 1)[0]


def paragraph_dir(out_dir: Path, paragraph_id: str) -> Path:
    return out_dir / chapter_dir_name(paragraph_chapter(paragraph_id)) / paragraph_dir_name(paragraph_id)


def clean_generated_reference_dirs(out_dir: Path) -> None:
    for path in out_dir.glob("chapter_*"):
        if path.is_dir():
            shutil.rmtree(path)


def parse_ontology_frames(tex_path: Path) -> list[dict[str, Any]]:
    text = tex_path.read_text(encoding="utf-8")
    frames: list[dict[str, Any]] = []
    for match in re.finditer(r"\\frametitle\{([^}]*)\}", text):
        if is_commented_line(text, match.start()):
            continue

        title = match.group(1).strip()
        if ONTOLOGY_TITLE_PREFIX not in title:
            continue

        frame_start = max(text.rfind("\\begin{frame}", 0, match.start()), 0)
        frame_end = text.find("\\end{frame}", match.end())
        if frame_end == -1:
            frame_end = min(len(text), match.end() + 2000)
        block = text[frame_start:frame_end]
        images = included_images(block)
        subsection = current_section_title(text, match.start(), "subsection")
        section = current_section_title(text, match.start(), "section")
        paragraph_id = infer_paragraph_id(subsection, images)
        chapter = paragraph_id.split(".", 1)[0] if paragraph_id else None
        frames.append(
            {
                "title": title,
                "section": section,
                "subsection": subsection,
                "paragraph_id": paragraph_id,
                "chapter": chapter,
                "tex_line": text.count("\n", 0, match.start()) + 1,
                "images": images,
                "pdf_page": None,
                "rendered_images": [],
            }
        )
    return frames


def ontology_pdf_pages(pdf_path: Path) -> list[dict[str, Any]]:
    reader = PdfReader(str(pdf_path))
    pages: list[dict[str, Any]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        lines = [line.strip() for line in (page.extract_text() or "").splitlines() if line.strip()]
        if lines and lines[0].startswith(ONTOLOGY_TITLE_PREFIX):
            pages.append({"page": page_number, "title": lines[0]})
    return pages


def assign_pdf_pages(frames: list[dict[str, Any]], pages: list[dict[str, Any]]) -> None:
    cursor = 0
    for frame in frames:
        for index in range(cursor, len(pages)):
            if pages[index]["title"] == frame["title"]:
                frame["pdf_page"] = pages[index]["page"]
                cursor = index + 1
                break


def render_pdf_page(pdf_path: Path, page_number: int, out_path: Path, dpi: int) -> None:
    import fitz

    doc = fitz.open(str(pdf_path))
    try:
        page = doc.load_page(page_number - 1)
        zoom = dpi / 72
        pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        pixmap.save(str(out_path))
    finally:
        doc.close()


def reference_relation_key(item: dict[str, Any]) -> tuple[str, ...]:
    return (
        str(item.get("paragraph", "")),
        str(item.get("diagram", "")),
        str(item.get("type", "")),
        str(item.get("name1", "")),
        str(item.get("name2", "")),
        json.dumps(item.get("predicate", ""), ensure_ascii=False, sort_keys=True),
        json.dumps(item.get("predicateInv", ""), ensure_ascii=False, sort_keys=True),
    )


def load_reference_relations(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"Expected list in {path}")
    unique: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in rows:
        paragraph_id = row.get("paragraph")
        if not paragraph_id:
            raise ValueError(f"Reference relation has no paragraph: {row}")
        item = dict(row)
        item.setdefault("source", "manual")
        unique[reference_relation_key(item)] = item
    return [unique[key] for key in sorted(unique)]


def write_reference_relations(
    relations_path: Path,
    out_dir: Path,
    paragraph_ids: set[str],
) -> dict[str, int]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in load_reference_relations(relations_path):
        grouped[str(row["paragraph"])].append(row)
        paragraph_ids.add(str(row["paragraph"]))

    counts: dict[str, int] = {}
    for paragraph_id in sorted(paragraph_ids):
        target_dir = paragraph_dir(out_dir, paragraph_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        rows = sorted(
            grouped.get(paragraph_id, []),
            key=lambda item: (
                str(item.get("diagram", "")),
                str(item.get("name1", "")),
                str(item.get("name2", "")),
                str(item.get("type", "")),
            ),
        )
        write_json(target_dir / "relations.json", rows)
        counts[paragraph_id] = len(rows)
    return counts


def write_reference_images(
    frames: list[dict[str, Any]],
    pdf_path: Path,
    out_dir: Path,
    dpi: int,
    *,
    render_pages: bool,
) -> dict[str, int]:
    image_counts: dict[str, int] = defaultdict(int)
    for frame in frames:
        paragraph_id = frame.get("paragraph_id")
        chapter = frame.get("chapter")
        if not paragraph_id or not chapter:
            continue

        target_dir = paragraph_dir(out_dir, paragraph_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        rendered_images = []

        for image in frame["images"] or ["ontology"]:
            if frame["pdf_page"] is None:
                continue
            page_tag = f"{frame['pdf_page']:03d}"
            existing = sorted(target_dir.glob(f"ontology_page_{page_tag}_*.png"))
            if existing:
                rendered_images.append(existing[0].name)
                continue
            out_name = f"ontology_page_{page_tag}_{re.sub(r'[^A-Za-z0-9_]+', '_', Path(image).stem)}.png"
            out_path = target_dir / out_name
            if render_pages:
                render_pdf_page(pdf_path, frame["pdf_page"], out_path, dpi)
            rendered_images.append(out_name)

        frame["rendered_images"] = rendered_images
        if rendered_images:
            image_counts[paragraph_id] += len(rendered_images)

    return dict(image_counts)


def build_references(args: argparse.Namespace) -> dict[str, Any]:
    tex_path = Path(args.tex)
    pdf_path = Path(args.pdf)
    relations_path = Path(args.reference_relations)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    clean_generated_reference_dirs(out_dir)

    frames = parse_ontology_frames(tex_path)
    pages = ontology_pdf_pages(pdf_path)
    assign_pdf_pages(frames, pages)

    image_counts = write_reference_images(
        frames,
        pdf_path,
        out_dir,
        args.dpi,
        render_pages=not args.no_render_pages,
    )
    paragraph_ids = {
        str(frame["paragraph_id"])
        for frame in frames
        if frame.get("paragraph_id")
    }
    relation_counts = write_reference_relations(relations_path, out_dir, paragraph_ids)

    summary = {
        "tex": str(tex_path),
        "pdf": str(pdf_path),
        "reference_relations": str(relations_path),
        "ontology_frames_total": len(frames),
        "ontology_frames_with_pdf_page": sum(1 for frame in frames if frame.get("pdf_page")),
        "paragraphs_with_reference_images": len([key for key, value in image_counts.items() if value]),
        "paragraphs_with_reference_relations": len([key for key, value in relation_counts.items() if value]),
        "frames_without_pdf_page": [
            frame
            for frame in frames
            if frame.get("paragraph_id") and not frame.get("pdf_page")
        ],
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build DM reference ontology folders from tex/PDF and manual relation data")
    parser.add_argument("--tex", default=str(DIGR_ROOT / "data" / "all_lectures.tex"))
    parser.add_argument("--pdf", default=str(DIGR_ROOT / "data" / "DM2024.pdf"))
    parser.add_argument("--reference-relations", default=str(SCRIPT_DIR / "data" / "dm_reference_ontologies" / "reference_relations.json"))
    parser.add_argument("--out-dir", default=str(SCRIPT_DIR / "data" / "dm_reference_ontologies"))
    parser.add_argument("--dpi", type=int, default=160)
    parser.add_argument("--no-render-pages", action="store_true")
    args = parser.parse_args(argv)

    summary = build_references(args)
    print(json.dumps(
        {
            "ontology_frames_total": summary["ontology_frames_total"],
            "ontology_frames_with_pdf_page": summary["ontology_frames_with_pdf_page"],
            "paragraphs_with_reference_images": summary["paragraphs_with_reference_images"],
            "paragraphs_with_reference_relations": summary["paragraphs_with_reference_relations"],
            "frames_without_pdf_page": len(summary["frames_without_pdf_page"]),
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
