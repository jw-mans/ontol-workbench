from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from document_ast import ActorAstParser
from dsl import ActorDslEngine


@pytest.fixture(scope="session")
def ga_tex_path(repo_root: Path) -> Path:
    path = repo_root / "GA_1_2025.tex"
    if not path.exists():
        pytest.skip("GA_1_2025.tex is required for tex DSL example checks")
    return path


@pytest.fixture(scope="session")
def ga_tex_document(ga_tex_path: Path, config_dir: Path):
    return ActorAstParser.from_config_dir(config_dir).parse(ga_tex_path, format_name="tex")


@pytest.fixture(scope="session")
def tex_engine() -> ActorDslEngine:
    return ActorDslEngine()


def execute(tex_engine: ActorDslEngine, ga_tex_document, query: str) -> dict[str, Any]:
    return tex_engine.execute(ga_tex_document, query.strip()).to_dict()


def assert_compact_distance_pair(item: dict[str, Any]) -> None:
    assert "children" not in item["left"]
    assert "children" not in item["right"]
    assert {"entity", "text", "start", "end", "metadata"} <= set(item["left"])
    assert {"entity", "text", "start", "end", "metadata"} <= set(item["right"])


@pytest.mark.parametrize(
    ("kind", "expected_count"),
    [
        ("theorem", 42),
        ("proof", 65),
        ("example", 106),
        ("lemma", 7),
    ],
)
def test_ga_tex_semantic_kind_counts(tex_engine, ga_tex_document, kind: str, expected_count: int) -> None:
    payload = execute(
        tex_engine,
        ga_tex_document,
        f'FIND semantic_block WHERE metadata.kind = "{kind}" RETURN count',
    )

    assert payload["count"] == expected_count


def test_docs_find_definition_entities(tex_engine, ga_tex_document) -> None:
    payload = execute(
        tex_engine,
        ga_tex_document,
        """
        FIND definition
        RETURN text, nodes, count
        """,
    )

    assert payload["count"] == 325
    assert "\\odmkey" in payload["items"][0]["text"]
    assert payload["items"][0]["nodes"]["entity"] == "definition"
    assert payload["items"][0]["nodes"]["metadata"] == {
        "name": "теории формальных грамматик",
        "index": "Теория!формальных!грамматик",
    }


def test_docs_find_definition_by_name(tex_engine, ga_tex_document) -> None:
    payload = execute(
        tex_engine,
        ga_tex_document,
        """
        FIND definition
        WHERE metadata.name = "алфавитом"
        RETURN text, nodes, count
        """,
    )

    assert payload["count"] == 1
    assert payload["items"][0]["text"] == "\\odmkey{алфавитом}{Алфавит}"
    assert payload["items"][0]["nodes"]["metadata"] == {
        "name": "алфавитом",
        "index": "Алфавит",
    }


@pytest.mark.parametrize(
    ("query", "expected_count", "expected_stats", "expected_unit", "expected_entities"),
    [
        (
            """
            DISTANCE semantic_block[metadata.kind = "theorem"]
            TO semantic_block[metadata.kind = "proof"]
            LIMIT_PAIRS all_nearest
            RETURN pairs, stats, distance(semantic_block), count
            """,
            35,
            {"count": 35, "mean": 0.0, "variance": 0.0, "min": 0, "max": 0},
            "semantic_block",
            ["semantic_block", "semantic_block"],
        ),
        (
            """
            DISTANCE semantic_block[metadata.kind = "theorem"]
            TO semantic_block[metadata.kind = "example"]
            LIMIT_PAIRS 3
            RETURN pairs, stats, distance(semantic_block), count
            """,
            3,
            {"count": 3, "mean": 2 / 3, "variance": 2 / 9, "min": 0, "max": 1},
            "semantic_block",
            ["semantic_block", "semantic_block"],
        ),
        (
            """
            DISTANCE definition
            TO semantic_block[metadata.kind = "theorem"]
            LIMIT_PAIRS 3
            RETURN pairs, stats, distance(semantic_block), count
            """,
            3,
            {"count": 3, "mean": 0.0, "variance": 0.0, "min": 0, "max": 0},
            "semantic_block",
            ["definition", "semantic_block"],
        ),
        (
            """
            DISTANCE semantic_block[metadata.kind = "theorem"]
            TO semantic_block[metadata.kind = "proof"]
            WITHIN content_scope[=1]
            LIMIT_PAIRS all_nearest
            RETURN pairs, stats, distance(semantic_block), count
            """,
            35,
            {"count": 35, "mean": 0.0, "variance": 0.0, "min": 0, "max": 0},
            "semantic_block",
            ["semantic_block", "semantic_block"],
        ),
        (
            """
            DISTANCE definition[metadata.name = "степень"]
            TO semantic_block[metadata.kind = "theorem"]
            LIMIT_PAIRS all_nearest
            RETURN pairs, stats, distance(symbol), count
            """,
            1,
            {"count": 1, "mean": 344.0, "variance": 0.0, "min": 344, "max": 344},
            "symbol",
            ["definition", "semantic_block"],
        ),
    ],
)
def test_docs_distance_examples(
        tex_engine,
        ga_tex_document,
        query: str,
        expected_count: int,
        expected_stats: dict[str, float | int],
        expected_unit: str,
        expected_entities: list[str],
) -> None:
    payload = execute(tex_engine, ga_tex_document, query)

    assert payload["type"] == "dsl_query_execution_result"
    assert payload["kind"] == "distance"
    assert payload["count"] == expected_count
    assert payload["stats"] == pytest.approx(expected_stats)
    assert payload["items"][0]["distance"]["unit"] == expected_unit
    assert [payload["items"][0]["left"]["entity"], payload["items"][0]["right"]["entity"]] == expected_entities
    assert_compact_distance_pair(payload["items"][0])


@pytest.mark.parametrize(
    ("query", "expected_count", "expected_unit", "expected_value", "expected_names"),
    [
        (
            """
            CONTEXT semantic_block[<=8]
            FOR th: semantic_block[metadata.kind = "theorem"],
                pr: semantic_block[metadata.kind = "proof"]
            RETURN matches, distance(semantic_block), count
            """,
            53,
            "semantic_block",
            0,
            ["th", "pr"],
        ),
        (
            """
            CONTEXT semantic_block[<=8]
            FOR th: semantic_block[metadata.kind = "theorem"],
                ex: semantic_block[metadata.kind = "example"]
            RETURN matches, distance(semantic_block), count
            """,
            41,
            "semantic_block",
            5,
            ["th", "ex"],
        ),
        (
            """
            CONTEXT semantic_block[<=4]
            FOR term: definition,
                th: semantic_block[metadata.kind = "theorem"]
            RETURN matches, distance(semantic_block), count
            """,
            23,
            "semantic_block",
            0,
            ["term", "th"],
        ),
        (
            """
            CONTEXT semantic_block[<=4]
            FOR term: definition[metadata.name = "степень"],
                th: semantic_block[metadata.kind = "theorem"]
            RETURN matches, distance(symbol), count
            """,
            1,
            "symbol",
            344,
            ["term", "th"],
        ),
    ],
)
def test_docs_context_distance_examples(
        tex_engine,
        ga_tex_document,
        query: str,
        expected_count: int,
        expected_unit: str,
        expected_value: int,
        expected_names: list[str],
) -> None:
    payload = execute(tex_engine, ga_tex_document, query)
    first = payload["items"][0]
    distance = first["distances"][0]

    assert payload["type"] == "dsl_query_execution_result"
    assert payload["kind"] == "context"
    assert payload["count"] == expected_count
    assert [match["name"] for match in first["matches"]] == expected_names
    assert distance["distance"] == {"unit": expected_unit, "value": expected_value}
    assert "children" not in first["matches"][0]["nodes"][0]
    assert "children" not in first["matches"][1]["nodes"][0]
    assert "children" not in distance["left"]["node"]
    assert "children" not in distance["right"]["node"]


@pytest.mark.parametrize(
    ("query", "expected_count"),
    [
        (
            """
            FIND semantic_block
            WHERE metadata.kind = "theorem"
              AND inside(content_scope[metadata.kind = "frame"])
            RETURN count
            """,
            42,
        ),
        (
            """
            FIND semantic_block
            WHERE metadata.kind = "proof"
              AND follows(semantic_block[metadata.kind = "theorem"])
            RETURN count
            """,
            34,
        ),
        (
            """
            FIND semantic_block
            WHERE metadata.kind = "theorem"
              AND precedes(semantic_block[metadata.kind = "proof"])
            RETURN count
            """,
            34,
        ),
        (
            """
            FIND semantic_block
            WHERE contains(/Эрли/)
            RETURN count
            """,
            10,
        ),
    ],
)
def test_additional_ga_tex_find_queries(tex_engine, ga_tex_document, query: str, expected_count: int) -> None:
    payload = execute(tex_engine, ga_tex_document, query)

    assert payload["count"] == expected_count


def test_additional_ga_tex_lemma_proof_distance_and_context(tex_engine, ga_tex_document) -> None:
    distance_payload = execute(
        tex_engine,
        ga_tex_document,
        """
        DISTANCE semantic_block[metadata.kind = "lemma"]
        TO semantic_block[metadata.kind = "proof"]
        LIMIT_PAIRS all_nearest
        RETURN pairs, stats, distance(semantic_block), count
        """,
    )
    context_payload = execute(
        tex_engine,
        ga_tex_document,
        """
        CONTEXT semantic_block[<=2]
        FOR lm: semantic_block[metadata.kind = "lemma"],
            pr: semantic_block[metadata.kind = "proof"]
        RETURN matches, distance(semantic_block), count
        """,
    )

    assert distance_payload["count"] == 6
    assert distance_payload["stats"] == {"count": 6, "mean": 0.0, "variance": 0.0, "min": 0, "max": 0}
    assert distance_payload["items"][0]["distance"] == {"unit": "semantic_block", "value": 0}
    assert context_payload["count"] == 6
    assert context_payload["items"][0]["distances"][0]["distance"] == {"unit": "semantic_block", "value": 0}
