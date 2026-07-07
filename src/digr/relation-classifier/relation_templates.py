from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Optional

import yaml

from document_ast import ActorAstParser
from dsl import ActorDslEngine

from build_chunks_dataset import concept_regex

LABEL_PRIORITY = [
    "composition",
    "aggregation",
    "dependency",
    "output",
    "input",
    "instance",
    "association",
    "manifest",
    "generalization",
]

DEFAULT_LABEL = "generalization"


def load_templates(path: str) -> dict[str, list[str]]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {label: list(phrases) for label, phrases in data.items()}


class TemplateRelationClassifier:
    def __init__(self, templates_path: str, config_dir: str, engine: Optional[ActorDslEngine] = None) -> None:
        self._templates = load_templates(templates_path)
        self._parser = ActorAstParser.from_config_dir(config_dir)
        self._engine = engine or ActorDslEngine()

    def predict(self, concept_a: str, concept_b: str, reference_chunk: str) -> str:
        if not reference_chunk.strip():
            return DEFAULT_LABEL
        document = self._build_document(reference_chunk)
        ra = concept_regex(concept_a)
        rb = concept_regex(concept_b)

        votes: dict[str, int] = {}
        for label in LABEL_PRIORITY:
            count = sum(
                1 for phrase in self._templates.get(label, ())
                if self._matches(document, ra, rb, phrase)
            )
            if count:
                votes[label] = count

        if not votes:
            return DEFAULT_LABEL
        return max(votes, key=lambda label: (votes[label], -LABEL_PRIORITY.index(label)))

    def _matches(self, document, ra: str, rb: str, phrase: str) -> bool:
        query = (
            f'CONTEXT sentence[<=20] '
            f'FOR a: /{ra}/i, b: /{rb}/i, tmpl: /{phrase}/i '
            f'RETURN count'
        )
        try:
            result = self._engine.execute(document, query).to_dict()
        except Exception:
            return False
        return result["count"] > 0

    def _build_document(self, text: str):
        cleaned = re.sub(r"\s+", " ", text).strip()
        fd, path_str = tempfile.mkstemp(suffix=".txt")
        path = Path(path_str)
        try:
            with open(fd, "w", encoding="utf-8") as f:
                f.write(cleaned)
            return self._parser.parse(path, format_name="txt")
        finally:
            path.unlink(missing_ok=True)
