from __future__ import annotations

from actor import Actor, ActorHandle

from ...model.query_ast import Query
from ...parsing.messages import (
    ContinueHeadParsing,
    ContinueQueryClassification,
    ContinueTailParsing,
    DslParseFailed,
    DslQueryParsed,
    ParseTokenStreamRequest,
    QueryParserMessage,
)
from ...parsing.recursive_descent_parser import DslTokenStreamParser
from ...parsing.states import DslQueryParserState
from ...parsing.token_kind import TokenKind


class DslQueryParserActor(Actor[DslQueryParserState, QueryParserMessage, QueryParserMessage]):
    # два шага для всех kind: сначала заголовок, потом общий хвост

    def __init__(self, reply_to: ActorHandle[object] | None = None) -> None:
        super().__init__(DslQueryParserState, DslQueryParserState.READY)
        self._reply_to = reply_to
        self._parser: DslTokenStreamParser | None = None
        self._query: Query | None = None

    def set_reply_to(self, handle: ActorHandle[object]) -> None:
        self._reply_to = handle

    def on_ready_parse_token_stream_request(self, message: ParseTokenStreamRequest) -> DslQueryParserState:
        self._parser = DslTokenStreamParser(message.tokens)
        self._query = None
        self.put(ContinueQueryClassification())
        return DslQueryParserState.CLASSIFYING_QUERY

    def on_classifying_query_continue_query_classification(
            self, message: ContinueQueryClassification,
    ) -> DslQueryParserState:
        parser = self._require_parser()
        try:
            if parser.current.kind not in (TokenKind.CONTEXT, TokenKind.FIND, TokenKind.DISTANCE):
                raise parser._error("Query must start with CONTEXT, FIND, or DISTANCE")
            self.put(ContinueHeadParsing())
            return DslQueryParserState.PARSING_HEAD
        except Exception as error:
            return self._fail(error)

    def on_parsing_head_continue_head_parsing(
            self, message: ContinueHeadParsing,
    ) -> DslQueryParserState:
        parser = self._require_parser()
        try:
            self._query = parser.parse_query_head()
            self.put(ContinueTailParsing())
            return DslQueryParserState.PARSING_TAIL
        except Exception as error:
            return self._fail(error)

    def on_parsing_tail_continue_tail_parsing(
            self, message: ContinueTailParsing,
    ) -> DslQueryParserState:
        parser = self._require_parser()
        try:
            query = self._query
            if query is None:
                raise RuntimeError("query head was not parsed")
            parser.parse_query_tail(query)
            parser.consume_query_terminator()
            parser.expect(TokenKind.EOF, "Unexpected tokens after end of query")
            self._reply(DslQueryParsed(query=query))
            return DslQueryParserState.READY
        except Exception as error:
            return self._fail(error)

    def _require_parser(self) -> DslTokenStreamParser:
        if self._parser is None:
            raise RuntimeError("parser is not initialized")
        return self._parser

    def _reply(self, message: object) -> None:
        if self._reply_to is None:
            raise RuntimeError("reply_to handle is not configured")
        self._reply_to.tell(message)

    def _fail(self, error: Exception) -> DslQueryParserState:
        self._reply(DslParseFailed(error))
        return DslQueryParserState.READY
