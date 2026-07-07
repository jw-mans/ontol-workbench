from __future__ import annotations

from dataclasses import dataclass

from actor import ManualActorDriver, ProceedableActorDriver
from document_ast.model.ast_document import AstDocument

from ..actors.execution.execution_coordinator_actor import DslExecutionCoordinatorActor
from ..actors.execution.execution_result_collector_actor import DslExecutionResultCollectorActor
from ..actors.execution.execution_worker_actor import DslExecutionWorkerActor
from .document_index import DocumentIndex
from .predicate_evaluator import PredicateEvaluator


@dataclass(slots=True)
class DslExecutionRuntime:
    driver: ProceedableActorDriver
    coordinator: DslExecutionCoordinatorActor
    collector: DslExecutionResultCollectorActor


class DslExecutionRuntimeFactory:
    def __init__(
            self,
            worker_count: int = 4,
            driver_factory: type[ProceedableActorDriver] | None = None,
    ) -> None:
        self._worker_count = max(1, worker_count)
        self._driver_factory = driver_factory or ManualActorDriver

    def create(self, document: AstDocument) -> DslExecutionRuntime:
        driver = self._driver_factory(step_limit=1)
        index = DocumentIndex(document)
        evaluator = PredicateEvaluator(index)

        collector = DslExecutionResultCollectorActor()
        collector.bind(driver)

        workers = []
        for _ in range(self._worker_count):
            worker = DslExecutionWorkerActor(evaluator=evaluator, document_text=document.root.text)
            worker.bind(driver)
            workers.append(worker)

        coordinator = DslExecutionCoordinatorActor(
            index=index,
            workers=[worker.as_handle() for worker in workers],
            collector=collector.as_handle(),
            evaluator=evaluator,
        )
        coordinator.bind(driver)

        coordinator_handle = coordinator.as_handle()
        for worker in workers:
            worker.set_reply_to(coordinator_handle)

        return DslExecutionRuntime(driver=driver, coordinator=coordinator, collector=collector)
