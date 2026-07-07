from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from ..model.query_ast import Query
from .token import DslToken


@dataclass(slots=True)
class ParseDslRequest:
    source: str


@dataclass(slots=True)
class TokenizeDslRequest:
    source: str


@dataclass(slots=True)
class DslTokenized:
    tokens: list[DslToken]


@dataclass(slots=True)
class ParseTokenStreamRequest:
    tokens: list[DslToken]


@dataclass(slots=True)
class ContinueQueryClassification:
    pass


@dataclass(slots=True)
class ContinueHeadParsing:
    pass


@dataclass(slots=True)
class ContinueTailParsing:
    pass


@dataclass(slots=True)
class DslQueryParsed:
    query: Query


@dataclass(slots=True)
class DslParseFailed:
    error: Exception


CoordinatorMessage = Union[
    ParseDslRequest,
    DslTokenized,
    DslQueryParsed,
    DslParseFailed,
]

LexerMessage = Union[TokenizeDslRequest]

QueryParserMessage = Union[
    ParseTokenStreamRequest,
    ContinueQueryClassification,
    ContinueHeadParsing,
    ContinueTailParsing,
]

CollectorMessage = Union[DslQueryParsed, DslParseFailed]
