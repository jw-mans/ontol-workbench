from __future__ import annotations

from actor import ProceedableActorDriver

from ..model.query_ast import DslQuery
from ..parsing.messages import ParseDslRequest
from ..parsing.runtime import DslParserRuntimeFactory


class ActorDslParser:
    def __init__(self, runtime_factory: DslParserRuntimeFactory | None = None) -> None:
        self._runtime_factory = runtime_factory or DslParserRuntimeFactory()

    def parse(self, source: str) -> DslQuery:
        runtime = self._runtime_factory.create()
        runtime.coordinator.put(ParseDslRequest(source=source))
        self._drain(runtime.driver)

        if runtime.collector.error is not None:
            raise runtime.collector.error
        if runtime.collector.result is None:
            raise RuntimeError("DSL parser finished without result")
        return runtime.collector.result

    @staticmethod
    def _drain(driver: ProceedableActorDriver) -> None:
        while not driver.is_idle():
            driver.proceed()
