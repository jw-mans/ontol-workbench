from __future__ import annotations

import pytest

from dsl import (
    ActorDslParser,
    DistanceReturn,
    DslLexer,
    DslSyntaxError,
    DslTokenStreamParser,
    SpanSpec,
    TokenKind,
)


def test_dsl_lexer_tokenizes_keywords_literals_and_regex() -> None:
    source = 'FIND sentence WHERE text ~= /телефон/i RETURN text, count'

    tokens = DslLexer().tokenize(source)

    assert [token.kind for token in tokens[:8]] == [
        TokenKind.FIND,
        TokenKind.IDENTIFIER,
        TokenKind.WHERE,
        TokenKind.IDENTIFIER,
        TokenKind.MATCH,
        TokenKind.REGEX,
        TokenKind.RETURN,
        TokenKind.IDENTIFIER,
    ]
    assert tokens[5].value == {"pattern": "телефон", "flags": "i"}


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ('FIND sentence WHERE text = "bad\\q"', "Unsupported escape sequence"),
        ("FIND sentence WHERE text ~= /bad/x", "Unsupported regex flag"),
        ("FIND sentence @", "Unexpected character"),
    ],
)
def test_dsl_lexer_reports_syntax_errors(source: str, message: str) -> None:
    with pytest.raises(DslSyntaxError, match=message):
        DslLexer().tokenize(source)


def test_dsl_parser_builds_context_query_with_aliases_and_returns() -> None:
    source = """
    CONTEXT sentence[<=4]
    FOR door: "дверь", quiet: /тишина/i, hit: word[text = "дверь"]
    WITHIN paragraph[=1]
    WHERE NOT text = "x"
    RETURN text, matches, count;
    """

    query = DslTokenStreamParser(DslLexer().tokenize(source)).parse_query()
    payload = query.to_dict()

    assert payload["type"] == "query"
    assert payload["kind"] == "CONTEXT"
    assert payload["source"]["entity_name"] == "sentence"
    assert [pattern["alias"] for pattern in payload["patterns"]] == ["door", "quiet", "hit"]
    assert payload["within"][0]["entity_name"] == "paragraph"
    assert payload["returns"] == ["text", "matches", "count"]


def test_dsl_parser_builds_find_query_with_within_before_where() -> None:
    # Единая грамматика фиксирует порядок хвоста WITHIN* WHERE? LIMIT_PAIRS? RETURN?
    # для всех трёх видов запроса — в исходной грамматике FIND требовал обратный
    # порядок (WHERE перед WITHIN), см. отчёт, п. "Нормализация порядка хвоста".
    query = DslTokenStreamParser(
        DslLexer().tokenize('FIND sentence WITHIN paragraph[<=2] WHERE text ~= /тишина/i RETURN text')
    ).parse_query()

    assert query.kind == "FIND"
    assert query.source.entity_name == "sentence"
    assert query.within[0].entity_name == "paragraph"
    assert query.returns == ["text"]


def test_dsl_parser_builds_distance_query() -> None:
    source = """
    DISTANCE semantic_block[metadata.kind = "theorem"]
    TO semantic_block[metadata.kind = "example"]
    WITHIN content_scope[=1]
    LIMIT_PAIRS all_nearest
    RETURN pairs, stats, distance(word), count
    """

    query = DslTokenStreamParser(DslLexer().tokenize(source)).parse_query()

    assert query.kind == "DISTANCE"
    assert query.source.entity_name == "semantic_block"
    assert query.target.entity_name == "semantic_block"
    assert query.within[0].entity_name == "content_scope"
    assert query.limit.mode == "all_nearest"
    assert isinstance(query.returns[2], DistanceReturn)
    assert query.returns[2].entity_name == "word"


def test_dsl_parser_builds_distance_query_with_integer_limit() -> None:
    query = ActorDslParser().parse(
        "DISTANCE sentence[text ~= /телефон/i] TO sentence[text ~= /тишина/i] LIMIT_PAIRS 3 RETURN distance(word)"
    )

    assert query.kind == "DISTANCE"
    assert query.limit.mode == "k"
    assert query.limit.value == 3


def test_dsl_parser_treats_bracketed_argument_as_span_spec() -> None:
    source = "FIND sentence WHERE has_child(word[<=1])"

    query = DslTokenStreamParser(DslLexer().tokenize(source)).parse_query()

    assert isinstance(query.where.arguments[0], SpanSpec)
    assert query.where.arguments[0].entity_name == "word"


def test_dsl_parser_accepts_limit_pairs_syntax_for_any_kind() -> None:
    # Общая грамматика хвоста разрешает LIMIT_PAIRS синтаксически для любого kind;
    # уместность по смыслу (только DISTANCE) проверяет QueryValidator, а не парсер —
    # см. test_query_validator_rejects_limit_pairs_outside_distance.
    query = DslTokenStreamParser(
        DslLexer().tokenize("FIND sentence LIMIT_PAIRS all RETURN text")
    ).parse_query()

    assert query.kind == "FIND"
    assert query.limit.mode == "all"


def test_actor_dsl_parser_surfaces_syntax_errors() -> None:
    with pytest.raises(DslSyntaxError, match="Expected comparison operator"):
        ActorDslParser().parse("FIND sentence WHERE text")
