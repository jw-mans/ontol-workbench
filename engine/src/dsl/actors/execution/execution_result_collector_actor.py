from __future__ import annotations

from actor import Actor

from ...execution.messages import DslExecutionFailed, DslQueryExecuted, ExecutionCollectorMessage
from ...execution.query_results import DslExecutionResult
from ...execution.states import DslExecutionCollectorState


class DslExecutionResultCollectorActor(
    Actor[DslExecutionCollectorState, ExecutionCollectorMessage, ExecutionCollectorMessage],
):
    def __init__(self) -> None:
        super().__init__(DslExecutionCollectorState, DslExecutionCollectorState.EMPTY)
        self.result: DslExecutionResult | None = None
        self.error: Exception | None = None

    def on_empty_dsl_query_executed(self, message: DslQueryExecuted) -> DslExecutionCollectorState:
        self.result = message.result
        self.error = None
        return DslExecutionCollectorState.HAS_RESULT

    def on_empty_dsl_execution_failed(self, message: DslExecutionFailed) -> DslExecutionCollectorState:
        self.result = None
        self.error = message.error
        return DslExecutionCollectorState.HAS_ERROR

    def on_has_result_dsl_query_executed(self, message: DslQueryExecuted) -> DslExecutionCollectorState:
        self.result = message.result
        self.error = None
        return DslExecutionCollectorState.HAS_RESULT

    def on_has_result_dsl_execution_failed(self, message: DslExecutionFailed) -> DslExecutionCollectorState:
        self.result = None
        self.error = message.error
        return DslExecutionCollectorState.HAS_ERROR

    def on_has_error_dsl_query_executed(self, message: DslQueryExecuted) -> DslExecutionCollectorState:
        self.result = message.result
        self.error = None
        return DslExecutionCollectorState.HAS_RESULT

    def on_has_error_dsl_execution_failed(self, message: DslExecutionFailed) -> DslExecutionCollectorState:
        self.result = None
        self.error = message.error
        return DslExecutionCollectorState.HAS_ERROR
