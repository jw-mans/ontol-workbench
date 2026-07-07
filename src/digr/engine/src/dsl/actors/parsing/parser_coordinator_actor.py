from __future__ import annotations

from actor import Actor, ActorHandle

from ...parsing.messages import (
    CoordinatorMessage,
    DslParseFailed,
    DslQueryParsed,
    DslTokenized,
    ParseDslRequest,
    ParseTokenStreamRequest,
    TokenizeDslRequest,
)
from ...parsing.states import DslCoordinatorState


class DslParserCoordinatorActor(Actor[DslCoordinatorState, CoordinatorMessage, CoordinatorMessage]):
    def __init__(
            self,
            lexer: ActorHandle[object],
            parser: ActorHandle[object],
            collector: ActorHandle[object],
    ) -> None:
        super().__init__(DslCoordinatorState, DslCoordinatorState.IDLE)
        self._lexer = lexer
        self._parser = parser
        self._collector = collector

    def on_idle_parse_dsl_request(self, message: ParseDslRequest) -> DslCoordinatorState:
        self._lexer.tell(TokenizeDslRequest(source=message.source))
        return DslCoordinatorState.WAITING_FOR_TOKENS

    def on_waiting_for_tokens_dsl_tokenized(self, message: DslTokenized) -> DslCoordinatorState:
        self._parser.tell(ParseTokenStreamRequest(tokens=message.tokens))
        return DslCoordinatorState.WAITING_FOR_QUERY_AST

    def on_waiting_for_tokens_dsl_parse_failed(self, message: DslParseFailed) -> DslCoordinatorState:
        self._collector.tell(message)
        return DslCoordinatorState.COMPLETED

    def on_waiting_for_query_ast_dsl_query_parsed(self, message: DslQueryParsed) -> DslCoordinatorState:
        self._collector.tell(message)
        return DslCoordinatorState.COMPLETED

    def on_waiting_for_query_ast_dsl_parse_failed(self, message: DslParseFailed) -> DslCoordinatorState:
        self._collector.tell(message)
        return DslCoordinatorState.COMPLETED
