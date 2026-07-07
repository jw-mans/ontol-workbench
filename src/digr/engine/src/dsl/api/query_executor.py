from __future__ import annotations

from actor import ProceedableActorDriver
from document_ast.model.ast_document import AstDocument

from ..execution.messages import ExecuteDslQueryRequest
from ..execution.query_results import DslExecutionResult
from ..execution.runtime import DslExecutionRuntimeFactory
from ..model.query_ast import DslQuery


class ActorDslExecutor:
    def __init__(self, runtime_factory: DslExecutionRuntimeFactory | None = None) -> None:
        self._runtime_factory = runtime_factory or DslExecutionRuntimeFactory()

    def execute(self, document: AstDocument, query: DslQuery) -> DslExecutionResult:
        runtime = self._runtime_factory.create(document)
        runtime.coordinator.put(ExecuteDslQueryRequest(query=query))
        self._drain(runtime.driver)

        if runtime.collector.error is not None:
            raise runtime.collector.error
        if runtime.collector.result is None:
            raise RuntimeError("DSL executor finished without result")
        return runtime.collector.result

    @staticmethod
    def _drain(driver: ProceedableActorDriver) -> None:
        while not driver.is_idle():
            driver.proceed()
