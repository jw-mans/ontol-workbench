from __future__ import annotations

import pytest

from dsl import ActorDslExecutor, ActorDslParser


def test_actor_dsl_parser_and_executor_find_phone(sample_document) -> None:
    query = ActorDslParser().parse(
        """
        FIND sentence
        WHERE has_descendant(word[text ~= /телефон/i])
        RETURN text, count
        """.strip()
    )

    payload = ActorDslExecutor().execute(sample_document, query).to_dict()

    assert payload["type"] == "dsl_query_execution_result"
    assert payload["kind"] == "find"
    assert payload["count"] == 2
    assert [item["text"] for item in payload["items"]] == [
        "В девять часов телефон наконец завибрировал.",
        "Телефон снова завибрировал.",
    ]


def test_actor_dsl_engine_enforces_within_for_find(dsl_engine, sample_document) -> None:
    # "word" не является предком "sentence" в иерархии document_ast
    # (document -> page -> paragraph -> sentence -> clause -> word), поэтому
    # ни одно предложение не может лежать "внутри ровно одного word".
    payload = dsl_engine.execute(
        sample_document,
        """
        FIND sentence
        WITHIN word[=1]
        WHERE has_descendant(word[text ~= /телефон/i])
        RETURN text, count
        """.strip(),
    ).to_dict()

    assert payload["count"] == 0


def test_actor_dsl_engine_find_within_paragraph_keeps_matching_candidates(dsl_engine, sample_document) -> None:
    payload = dsl_engine.execute(
        sample_document,
        """
        FIND sentence
        WITHIN paragraph[=1]
        WHERE has_descendant(word[text ~= /телефон/i])
        RETURN text, count
        """.strip(),
    ).to_dict()

    assert payload["count"] == 2


def test_actor_dsl_engine_executes_context_query(dsl_engine, sample_document) -> None:
    payload = dsl_engine.execute(
        sample_document,
        """
        CONTEXT sentence[<=4]
        FOR "дверь", "тишина"
        WITHIN paragraph[=1]
        RETURN text, matches, count
        """.strip(),
    ).to_dict()

    assert payload["type"] == "dsl_query_execution_result"
    assert payload["kind"] == "context"
    assert payload["count"] == 1
    assert "Только тишина." in payload["items"][0]["text"]
    assert [match["matched_text"] for match in payload["items"][0]["matches"]] == ["дверь", "тишина"]


def test_actor_dsl_engine_executes_distance_query(dsl_engine, sample_document) -> None:
    payload = dsl_engine.execute(
        sample_document,
        """
        DISTANCE sentence[text ~= /Только тишина/]
        TO sentence[text ~= /И эта тишина/]
        WITHIN paragraph[=1]
        LIMIT_PAIRS all_nearest
        RETURN pairs, stats, distance(word), count
        """.strip(),
    ).to_dict()

    assert payload["type"] == "dsl_query_execution_result"
    assert payload["kind"] == "distance"
    assert payload["count"] == 1
    assert payload["items"][0]["distance"] == {"unit": "word", "value": 0}
    assert "children" not in payload["items"][0]["left"]
    assert "children" not in payload["items"][0]["right"]
    assert payload["stats"]["mean"] == 0
    assert payload["stats"]["variance"] == 0


def test_actor_dsl_engine_executes_symbol_distance_query(dsl_engine, sample_document) -> None:
    payload = dsl_engine.execute(
        sample_document,
        """
        DISTANCE sentence[text ~= /Только тишина/]
        TO sentence[text ~= /И эта тишина/]
        WITHIN paragraph[=1]
        LIMIT_PAIRS all_nearest
        RETURN pairs, stats, distance(symbol), count
        """.strip(),
    ).to_dict()

    assert payload["count"] == 1
    assert payload["items"][0]["distance"] == {"unit": "symbol", "value": 0}


def test_actor_dsl_engine_adds_distances_to_context_windows(dsl_engine, sample_document) -> None:
    payload = dsl_engine.execute(
        sample_document,
        """
        CONTEXT sentence[<=2]
        FOR left: sentence[text ~= /Только тишина/], right: sentence[text ~= /И эта тишина/]
        WITHIN paragraph[=1]
        RETURN matches, distance(word), count
        """.strip(),
    ).to_dict()

    assert payload["count"] == 1
    assert payload["items"][0]["distances"][0]["distance"] == {"unit": "word", "value": 0}
    assert "children" not in payload["items"][0]["matches"][0]["nodes"][0]
    assert "children" not in payload["items"][0]["matches"][1]["nodes"][0]
    assert "children" not in payload["items"][0]["distances"][0]["left"]["node"]
    assert "children" not in payload["items"][0]["distances"][0]["right"]["node"]


def test_actor_dsl_engine_adds_symbol_distances_to_context_windows(dsl_engine, sample_document) -> None:
    payload = dsl_engine.execute(
        sample_document,
        """
        CONTEXT sentence[<=2]
        FOR left: sentence[text ~= /Только тишина/], right: sentence[text ~= /И эта тишина/]
        WITHIN paragraph[=1]
        RETURN matches, distance(symbol), count
        """.strip(),
    ).to_dict()

    assert payload["count"] == 1
    assert payload["items"][0]["distances"][0]["distance"] == {"unit": "symbol", "value": 0}


def test_actor_dsl_engine_rejects_unknown_entities(sample_document, dsl_engine) -> None:
    with pytest.raises(ValueError, match="ghost"):
        dsl_engine.execute(sample_document, "FIND ghost RETURN text")
