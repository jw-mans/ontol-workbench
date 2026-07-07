#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (_ROOT / "engine" / "src", _ROOT / "relation-classifier"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from build_chunks_dataset import to_plain_word  # noqa: E402


def convert(record: dict) -> dict:
    relation_type = record.get("ground_truth_type") or record["predicted_relation_type"]
    return {
        "concept_a": to_plain_word(record["index_a"]),
        "concept_b": to_plain_word(record["index_b"]),
        "relation_type": relation_type,
        "predicted_relation_type": record["predicted_relation_type"],
        "predicted_relation_confidence": None,
        "reference_chunk": record["reference_chunk"],
        "index_a": record["index_a"],
        "index_b": record["index_b"],
        "source": "ontology-pipeline",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", default="data/ontology_chunks.jsonl")
    parser.add_argument("--out", default="data/ontology_chunks_qdrant.jsonl")
    args = parser.parse_args(argv)

    records = [json.loads(ln) for ln in Path(args.chunks).read_text(encoding="utf-8").splitlines() if ln.strip()]
    rows = [convert(r) for r in records]
    Path(args.out).write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8",
    )
    print(f"{len(rows)} строк -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
