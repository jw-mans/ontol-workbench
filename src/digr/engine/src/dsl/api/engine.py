from __future__ import annotations

from document_ast.model.ast_document import AstDocument

from ..execution.query_results import DslExecutionResult
from .query_executor import ActorDslExecutor
from .query_parser import ActorDslParser


class ActorDslEngine:
    def __init__(
            self,
            parser: ActorDslParser | None = None,
            executor: ActorDslExecutor | None = None,
    ) -> None:
        self._parser = parser or ActorDslParser()
        self._executor = executor or ActorDslExecutor()

    def execute(self, document: AstDocument, query_source: str) -> DslExecutionResult:
        query = self._parser.parse(query_source)
        return self._executor.execute(document, query)
