from __future__ import annotations

import pytest

from document_ast.model.ast_node import AstNode
from dsl.actors.execution.execution_coordinator_actor import DslExecutionCoordinatorActor
from dsl.execution.document_index import DocumentIndex
from dsl.execution.predicate_evaluator import PredicateEvaluator
from dsl.execution.query_results import (
    ContextWindowMatch,
    DslQueryExecutionResult,
    FindMatch,
    PatternMatchResult,
)
from dsl.execution.query_validator import QueryValidator
from dsl.model.query_ast import (
    BinaryExpression,
    ComparisonExpression,
    CountConstraint,
    FieldRef,
    FunctionExpression,
    Pattern,
    Query,
    RegexLiteral,
    Selector,
    SpanSpec,
)


def find_node(index: DocumentIndex, entity: str, needle: str) -> AstNode:
    return next(node for node in index.nodes_of_entity(entity) if needle in node.text)


def test_document_index_navigates_tree(sample_document) -> None:
    index = DocumentIndex(sample_document)
    sentences = index.nodes_of_entity("sentence")

    assert "sentence" in index.entities()
    assert len(sentences) > 5
    assert index.previous_node(sentences[1].start, "sentence") == sentences[0]
    assert index.next_node(sentences[0].end, "sentence") == sentences[1]

    word = find_node(index, "word", "телефон")
    ancestors = index.ancestors(word)
    assert [node.entity for node in ancestors[:5]] == ["clause", "sentence", "paragraph", "page", "document"]

    containers = index.container_nodes_for_span(sentences[0].start, sentences[0].end, strict=True)
    assert containers[0].entity == "paragraph"
    assert {node.entity for node in containers[1:3]} == {"page", "document"}


def test_query_validator_accepts_valid_query_and_rejects_unknown_entities(document_index) -> None:
    validator = QueryValidator()
    valid = Query(
        kind="FIND",
        source=Selector("sentence"),
        where=FunctionExpression("has_descendant", [Selector("word")]),
        within=[],
        returns=["text"],
    )
    validator.validate(valid, document_index)

    invalid = Query(
        kind="CONTEXT",
        source=Selector("sentence"),
        window=CountConstraint("<=", 2),
        patterns=[Pattern(source=Selector("ghost"))],
        within=[],
        returns=["text"],
    )

    with pytest.raises(ValueError, match="ghost"):
        validator.validate(invalid, document_index)


def test_query_validator_rejects_limit_pairs_outside_distance(document_index) -> None:
    from dsl.model.query_ast import PairLimit

    query = Query(kind="FIND", source=Selector("sentence"), limit=PairLimit(mode="all"), returns=["text"])

    with pytest.raises(ValueError, match="LIMIT_PAIRS"):
        QueryValidator().validate(query, document_index)


def test_query_validator_rejects_return_distance_for_find(document_index) -> None:
    from dsl.model.query_ast import DistanceReturn

    query = Query(kind="FIND", source=Selector("sentence"), returns=[DistanceReturn(entity_name="word")])

    with pytest.raises(ValueError, match="RETURN distance"):
        QueryValidator().validate(query, document_index)


def test_predicate_evaluator_supports_core_functions(document_index) -> None:
    evaluator = PredicateEvaluator(document_index)
    phone_sentence = find_node(document_index, "sentence", "телефон наконец")
    silence_sentence = find_node(document_index, "sentence", "Только тишина")
    next_sentence = find_node(document_index, "sentence", "И эта тишина сейчас")
    paragraph = find_node(document_index, "paragraph", "Однако мысли всё время")
    phone_word = find_node(document_index, "word", "телефон")

    phone_selector = Selector(
        "word",
        ComparisonExpression(FieldRef(["text"]), "~=", RegexLiteral("телефон", "i")),
    )

    assert evaluator.evaluate(phone_sentence, FunctionExpression("has_descendant", [phone_selector])) is True
    assert evaluator.evaluate(phone_sentence, FunctionExpression("has_child", [phone_selector])) is False
    assert evaluator.evaluate(phone_sentence, FunctionExpression("contains", ["телефон"])) is True
    assert evaluator.evaluate(phone_sentence, FunctionExpression("contains", [RegexLiteral("телефон", "i")])) is True
    assert evaluator.evaluate(phone_sentence, FunctionExpression("contains", [phone_selector])) is True
    assert evaluator.evaluate(phone_sentence, FunctionExpression("contains", [FieldRef(["text"])])) is True
    assert evaluator.evaluate(phone_word, FunctionExpression("has_ancestor", [Selector("paragraph")])) is True
    assert evaluator.evaluate(
        next_sentence,
        FunctionExpression(
            "follows",
            [Selector("sentence", ComparisonExpression(FieldRef(["text"]), "~=", RegexLiteral("Только тишина", "")))],
        ),
    ) is True
    assert evaluator.evaluate(
        silence_sentence,
        FunctionExpression(
            "precedes",
            [Selector("sentence", ComparisonExpression(FieldRef(["text"]), "~=", RegexLiteral("И эта тишина", "")))],
        ),
    ) is True
    assert evaluator.evaluate(
        paragraph,
        FunctionExpression(
            "intersects",
            [Selector("sentence", ComparisonExpression(FieldRef(["text"]), "~=", RegexLiteral("Только тишина", "")))],
        ),
    ) is True
    assert evaluator.evaluate(
        next_sentence,
        FunctionExpression(
            "inside",
            [Selector("paragraph", ComparisonExpression(FieldRef(["text"]), "~=", RegexLiteral("к одной детали", "")))],
        ),
    ) is True


def test_predicate_evaluator_matches_patterns_and_counts_containers(document_index) -> None:
    evaluator = PredicateEvaluator(document_index)
    paragraph = find_node(document_index, "paragraph", "Однако мысли всё время")
    query = Query(
        kind="CONTEXT",
        source=Selector("sentence"),
        window=CountConstraint("<=", 4),
        patterns=[
            Pattern(source="дверь"),
            Pattern(source=RegexLiteral("тишина", "i"), alias="quiet"),
            Pattern(source=Selector("word", ComparisonExpression(FieldRef(["text"]), "=", "дверь"))),
        ],
        within=[],
        returns=["matches"],
    )

    matches = evaluator.match_patterns_in_window(query, paragraph.text, paragraph.start, paragraph.end)

    assert matches is not None
    assert [(match.name, match.source_type) for match in matches] == [
        ("pattern_1", "string"),
        ("quiet", "regex"),
        ("pattern_3", "selector"),
    ]

    sentences = document_index.nodes_of_entity("sentence")
    assert evaluator.count_distinct_containers(sentences[:2], "paragraph") == 1
    assert evaluator.count_distinct_containers(
        [find_node(document_index, "sentence", "Утро началось"), find_node(document_index, "sentence", "В девять часов")],
        "paragraph",
    ) == 2
    assert evaluator.compare_count(2, CountConstraint(">=", 2)) is True


def test_predicate_evaluator_reports_error_branches(document_index) -> None:
    evaluator = PredicateEvaluator(document_index)
    sentence = find_node(document_index, "sentence", "телефон наконец")

    with pytest.raises(ValueError, match="Unsupported boolean operator"):
        evaluator.evaluate(
            sentence,
            BinaryExpression(
                operator="XOR",
                left=ComparisonExpression(FieldRef(["start"]), ">=", 0),
                right=ComparisonExpression(FieldRef(["end"]), ">", 0),
            ),
        )

    with pytest.raises(NotImplementedError, match="SpanSpec arguments are not supported"):
        evaluator.evaluate(
            sentence,
            FunctionExpression("contains", [SpanSpec("sentence", CountConstraint("<=", 1))]),
        )

    with pytest.raises(ValueError, match="Unknown metadata field"):
        evaluator.evaluate(
            sentence,
            ComparisonExpression(FieldRef(["metadata", "missing"]), "=", "value"),
        )


def test_query_ast_and_execution_results_serialize(document_index) -> None:
    sentence = find_node(document_index, "sentence", "телефон наконец")
    find_query = Query(kind="FIND", source=Selector("sentence"), returns=None)
    find_result = DslQueryExecutionResult(query=find_query, source_path="text.txt", matches=[FindMatch(sentence)])
    find_payload = find_result.to_dict()

    assert find_payload["type"] == "dsl_query_execution_result"
    assert find_payload["kind"] == "find"
    assert find_payload["count"] == 1
    assert find_payload["returns"] == ["nodes", "count"]
    assert find_payload["items"][0]["nodes"]["entity"] == "sentence"

    context_query = Query(
        kind="CONTEXT",
        source=Selector("sentence"),
        window=CountConstraint("<=", 2),
        patterns=[Pattern(source="телефон")],
        within=[],
        returns=None,
    )
    window = ContextWindowMatch(
        base_entity="sentence",
        nodes=[sentence],
        text=sentence.text,
        start=sentence.start,
        end=sentence.end,
        matches=[PatternMatchResult(name="pattern_1", source_type="string", matched_text="телефон")],
    )
    context_payload = DslQueryExecutionResult(
        query=context_query,
        source_path="text.txt",
        matches=[window],
    ).to_dict()

    assert context_query.to_dict()["type"] == "query"
    assert context_query.to_dict()["kind"] == "CONTEXT"
    assert context_payload["kind"] == "context"
    assert context_payload["returns"] == ["window", "count"]
    assert context_payload["items"][0]["window"]["base_entity"] == "sentence"


def test_execution_coordinator_static_helpers_minimize_windows() -> None:
    a = ContextWindowMatch("sentence", [], "a", 0, 10, [])
    b = ContextWindowMatch("sentence", [], "b", 2, 5, [])
    c = ContextWindowMatch("sentence", [], "c", 12, 20, [])
    d = ContextWindowMatch("sentence", [], "d", 2, 5, [])

    assert DslExecutionCoordinatorActor._resolve_max_window_length("<", 4) == 3
    assert DslExecutionCoordinatorActor._resolve_max_window_length("<=", 4) == 4
    assert DslExecutionCoordinatorActor._resolve_max_window_length(">", 4) is None
    assert DslExecutionCoordinatorActor._minimal_windows([a, b, c, d]) == [b, c]
