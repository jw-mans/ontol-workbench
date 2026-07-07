from __future__ import annotations

from dataclasses import dataclass

from actor import ManualActorDriver, ProceedableActorDriver

from ..config.parser_config import ParserConfig
from .actors import ParseCoordinatorActor, ParseResultCollectorActor, SourceReaderActor, SubtreeBuilderWorkerActor


@dataclass(slots=True)
class ParserRuntime:
    driver: ProceedableActorDriver
    coordinator: ParseCoordinatorActor
    collector: ParseResultCollectorActor


class ParserRuntimeFactory:
    def __init__(
            self,
            worker_count: int = 4,
            driver_factory: type[ProceedableActorDriver] | None = None,
    ) -> None:
        self._worker_count = max(1, worker_count)
        self._driver_factory = driver_factory or ManualActorDriver

    def create(self, config: ParserConfig) -> ParserRuntime:
        driver = self._driver_factory(step_limit=1)

        collector = ParseResultCollectorActor()
        collector.bind(driver)

        reader = SourceReaderActor(config)
        reader.bind(driver)

        workers = []
        for _ in range(self._worker_count):
            worker = SubtreeBuilderWorkerActor(config)
            worker.bind(driver)
            workers.append(worker)

        coordinator = ParseCoordinatorActor(
            config=config,
            reader=reader.as_handle(),
            workers=[w.as_handle() for w in workers],
            collector=collector.as_handle(),
        )
        coordinator.bind(driver)

        coordinator_handle = coordinator.as_handle()
        reader.set_reply_to(coordinator_handle)
        for worker in workers:
            worker.set_reply_to(coordinator_handle)

        return ParserRuntime(driver=driver, coordinator=coordinator, collector=collector)
