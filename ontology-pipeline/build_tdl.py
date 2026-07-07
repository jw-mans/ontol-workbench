#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (_ROOT / "engine" / "src", _ROOT / "relation-classifier"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from build_chunks_dataset import concept_regex, load_document  # noqa: E402
from build_primary_ontology import LABEL_MAP, load_odmkeys  # noqa: E402
from dsl import ActorDslEngine  # noqa: E402

SECTION_TITLE_RE = re.compile(r"\\section\{([^}]*)\}")

RESERVED_WORDS = {
    "класс", "интерфейс", "тип_данных", "шаблон", "параметры", "подстановка",
    "класс_ассоциации", "перечисление", "конец", "абстрактный", "атрибуты",
    "операции", "обобщение", "ассоциация", "композиция", "агрегация",
    "зависимость", "реализация", "размещение", "выровнять", "распределить",
    "сгруппировать", "привязать", "зафиксировать", "повернуть", "по",
    "левому", "правому", "верху", "низу", "горизонтали", "вертикали", "шаг",
    "как", "левее", "правее", "выше", "ниже", "в",
}


def load_sections(engine: ActorDslEngine, document) -> list[tuple[str, int, int]]:
    result = engine.execute(document, "FIND section RETURN nodes").to_dict()
    text = document.root.text
    sections = []
    for item in result["items"]:
        node = item["nodes"]
        start, end = node["start"], node["end"]
        m = SECTION_TITLE_RE.search(text[start:start + 200])
        title = m.group(1) if m else f"section_{start}"
        sections.append((title, start, end))
    return sections


def odmkey_sections(odmkeys, sections: list[tuple[str, int, int]]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for occ in odmkeys:
        for i, (_, start, end) in enumerate(sections):
            if start <= occ.start < end:
                mapping.setdefault(occ.index, i)
                break
    return mapping


def section_of(name: str, known: dict[str, int], sections: list[tuple[str, int, int]], text: str, cache: dict[str, int | None]) -> int | None:
    if name in known:
        return known[name]
    if name in cache:
        return cache[name]
    r = re.compile(concept_regex(name), re.IGNORECASE)
    idx = next((i for i, (_, start, end) in enumerate(sections) if r.search(text[start:end])), None)
    cache[name] = idx
    return idx


def slugify(name: str) -> str:
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", name)
    slug = "".join(w[:1].upper() + w[1:] for w in words) or "X"
    if slug[0].isdigit():
        slug = "N" + slug
    if slug.lower() in RESERVED_WORDS:
        slug += "_"
    return slug


def unique_slug(name: str, taken: dict[str, str]) -> str:
    if name in taken:
        return taken[name]
    base = slugify(name)
    slug = base
    n = 2
    while slug in taken.values():
        slug = f"{base}{n}"
        n += 1
    taken[name] = slug
    return slug


def relation_line(kind: str, a: str, b: str) -> str:
    if kind == "generalization":
        return f"ОБОБЩЕНИЕ {a} -> {b}"
    if kind == "aggregation":
        return f"АГРЕГАЦИЯ {a} -- {b}"
    if kind == "composition":
        return f"КОМПОЗИЦИЯ {a} -- {b}"
    if kind == "association":
        return f"АССОЦИАЦИЯ {a} -- {b}"
    if kind == "dependency":
        return f"ЗАВИСИМОСТЬ {a} -> {b}"
    return f"ЗАВИСИМОСТЬ {a} -> {b} {kind}"


def build_section_tdl(title: str, pairs: list[tuple[str, str, str]]) -> str:
    taken: dict[str, str] = {}
    for name1, name2, _ in pairs:
        unique_slug(name1, taken)
        unique_slug(name2, taken)

    lines = [f"-- {title}", ""]
    for name, slug in taken.items():
        lines.append(f"КЛАСС {slug}")
        lines.append(f"-- {name}")
        lines.append("КОНЕЦ КЛАСС")
        lines.append("")
    for name1, name2, kind in pairs:
        lines.append(relation_line(kind, taken[name1], taken[name2]))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tex", default="../data/all_lectures.tex")
    parser.add_argument("--config-dir", default="config/formats")
    parser.add_argument("--final", default="data/ontology_final.json")
    parser.add_argument("--out-dir", default="data/tdl")
    args = parser.parse_args(argv)

    document = load_document(args.tex, args.config_dir)
    text = document.root.text
    engine = ActorDslEngine()
    sections = load_sections(engine, document)
    odmkeys = load_odmkeys(engine, document)
    known = odmkey_sections(odmkeys, sections)

    final = json.loads(Path(args.final).read_text(encoding="utf-8"))
    by_section: list[list[tuple[str, str, str]]] = [[] for _ in sections]
    cache: dict[str, int | None] = {}
    unassigned = 0
    for item in final:
        kind = LABEL_MAP.get(item["type"].lower(), item["type"].lower())
        idx = section_of(item["name1"], known, sections, text, cache)
        if idx is None:
            idx = section_of(item["name2"], known, sections, text, cache)
        if idx is None:
            unassigned += 1
            continue
        by_section[idx].append((item["name1"], item["name2"], kind))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, ((title, _, _), pairs) in enumerate(zip(sections, by_section), start=1):
        if not pairs:
            continue
        tdl = build_section_tdl(title, pairs)
        path = out_dir / f"{i:02d}_{slugify(title).lower()}.tdl"
        path.write_text(tdl, encoding="utf-8")
        print(f"{path}: {len(pairs)} связей")
    print(f"без секции: {unassigned}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
