from __future__ import annotations

from dataclasses import dataclass

from actor import ManualActorDriver, ProceedableActorDriver

from ..actors.parsing.lexer_actor import DslLexerActor
from ..actors.parsing.parse_result_collector_actor import DslParseResultCollectorActor
from ..actors.parsing.parser_coordinator_actor import DslParserCoordinatorActor
from ..actors.parsing.query_parser_actor import DslQueryParserActor


@dataclass(slots=True)
class DslParserRuntime:
    driver: ProceedableActorDriver
    coordinator: DslParserCoordinatorActor
    collector: DslParseResultCollectorActor


class DslParserRuntimeFactory:
    def __init__(
            self,
            driver_factory: type[ProceedableActorDriver] | None = None,
    ) -> None:
        self._driver_factory = driver_factory or ManualActorDriver

    def create(self) -> DslParserRuntime:
        driver = self._driver_factory(step_limit=1)

        collector = DslParseResultCollectorActor()
        collector.bind(driver)

        lexer = DslLexerActor()
        lexer.bind(driver)

        parser = DslQueryParserActor()
        parser.bind(driver)

        coordinator = DslParserCoordinatorActor(
            lexer=lexer.as_handle(),
            parser=parser.as_handle(),
            collector=collector.as_handle(),
        )
        coordinator.bind(driver)

        coordinator_handle = coordinator.as_handle()
        lexer.set_reply_to(coordinator_handle)
        parser.set_reply_to(coordinator_handle)

        return DslParserRuntime(driver=driver, coordinator=coordinator, collector=collector)
