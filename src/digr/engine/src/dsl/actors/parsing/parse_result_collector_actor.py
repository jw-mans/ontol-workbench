from __future__ import annotations

from actor import Actor

from ...model.query_ast import DslQuery
from ...parsing.messages import CollectorMessage, DslParseFailed, DslQueryParsed
from ...parsing.states import DslCollectorState


class DslParseResultCollectorActor(Actor[DslCollectorState, CollectorMessage, CollectorMessage]):
    def __init__(self) -> None:
        super().__init__(DslCollectorState, DslCollectorState.EMPTY)
        self.result: DslQuery | None = None
        self.error: Exception | None = None

    def on_empty_dsl_query_parsed(self, message: DslQueryParsed) -> DslCollectorState:
        self.result = message.query
        self.error = None
        return DslCollectorState.HAS_RESULT

    def on_empty_dsl_parse_failed(self, message: DslParseFailed) -> DslCollectorState:
        self.result = None
        self.error = message.error
        return DslCollectorState.HAS_ERROR

    def on_has_result_dsl_query_parsed(self, message: DslQueryParsed) -> DslCollectorState:
        self.result = message.query
        self.error = None
        return DslCollectorState.HAS_RESULT

    def on_has_result_dsl_parse_failed(self, message: DslParseFailed) -> DslCollectorState:
        self.result = None
        self.error = message.error
        return DslCollectorState.HAS_ERROR

    def on_has_error_dsl_query_parsed(self, message: DslQueryParsed) -> DslCollectorState:
        self.result = message.query
        self.error = None
        return DslCollectorState.HAS_RESULT

    def on_has_error_dsl_parse_failed(self, message: DslParseFailed) -> DslCollectorState:
        self.result = None
        self.error = message.error
        return DslCollectorState.HAS_ERROR
