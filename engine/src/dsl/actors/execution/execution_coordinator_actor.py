from __future__ import annotations

from actor import Actor, ActorHandle
from document_ast.model.ast_node import AstNode

from ...execution.document_index import DocumentIndex
from ...execution.distance_calculator import DistanceCalculator
from ...execution.messages import (
    ContextWindowEvaluated,
    DslExecutionFailed,
    DslQueryExecuted,
    EvaluateContextWindowRequest,
    EvaluateFindCandidateRequest,
    ExecuteDslQueryRequest,
    ExecutionCoordinatorMessage,
    FindCandidateEvaluated,
)
from ...execution.predicate_evaluator import PredicateEvaluator
from ...execution.query_results import ContextWindowMatch, DslQueryExecutionResult, FindMatch, render_compact_node
from ...execution.query_validator import QueryValidator
from ...execution.states import DslExecutionCoordinatorState
from ...model.query_ast import DistanceReturn, PairLimit, Query


class DslExecutionCoordinatorActor(
    Actor[DslExecutionCoordinatorState, ExecutionCoordinatorMessage, ExecutionCoordinatorMessage],
):
    def __init__(
            self,
            index: DocumentIndex,
            workers: list[ActorHandle[object]],
            collector: ActorHandle[object],
            evaluator: PredicateEvaluator | None = None,
            validator: QueryValidator | None = None,
    ) -> None:
        super().__init__(DslExecutionCoordinatorState, DslExecutionCoordinatorState.IDLE)
        self._index = index
        self._workers = workers
        self._collector = collector
        self._evaluator = evaluator or PredicateEvaluator(index)
        self._distance_calculator = DistanceCalculator(index, self._evaluator)
        self._validator = validator or QueryValidator()
        self._pending_count = 0
        self._find_results: dict[int, FindMatch] = {}
        self._context_results: dict[int, ContextWindowMatch] = {}
        self._current_query: Query | None = None

    def on_idle_execute_dsl_query_request(self, message: ExecuteDslQueryRequest) -> DslExecutionCoordinatorState:
        try:
            self._validator.validate(message.query, self._index)
        except Exception as error:
            self._collector.tell(DslExecutionFailed(error))
            return DslExecutionCoordinatorState.COMPLETED

        query = message.query
        if query.kind == "FIND":
            return self._dispatch_find(query)
        if query.kind == "DISTANCE":
            return self._dispatch_distance(query)
        return self._dispatch_context(query)

    def on_evaluating_find_candidates_find_candidate_evaluated(
            self, message: FindCandidateEvaluated,
    ) -> DslExecutionCoordinatorState:
        if message.match is not None:
            self._find_results[message.candidate_index] = message.match

        self._pending_count -= 1
        if self._pending_count > 0:
            return DslExecutionCoordinatorState.EVALUATING_FIND_CANDIDATES

        query = self._current_query
        if query is None:
            raise RuntimeError("find query is not initialized")
        ordered = [self._find_results[index] for index in sorted(self._find_results)]
        self._collector.tell(DslQueryExecuted(result=DslQueryExecutionResult(
            query=query,
            source_path=self._index.document.source_path,
            matches=ordered,
        )))
        return DslExecutionCoordinatorState.COMPLETED

    def on_evaluating_context_windows_context_window_evaluated(
            self, message: ContextWindowEvaluated,
    ) -> DslExecutionCoordinatorState:
        if message.match is not None:
            self._context_results[message.window_index] = message.match

        self._pending_count -= 1
        if self._pending_count > 0:
            return DslExecutionCoordinatorState.EVALUATING_CONTEXT_WINDOWS

        query = self._current_query
        if query is None:
            raise RuntimeError("context query is not initialized")

        ordered = [self._context_results[index] for index in sorted(self._context_results)]
        deduplicated = self._minimal_windows(ordered)
        deduplicated = [self._with_context_distances(match, query) for match in deduplicated]

        self._collector.tell(DslQueryExecuted(result=DslQueryExecutionResult(
            query=query,
            source_path=self._index.document.source_path,
            matches=deduplicated,
        )))
        return DslExecutionCoordinatorState.COMPLETED

    def on_evaluating_find_candidates_dsl_execution_failed(
            self, message: DslExecutionFailed,
    ) -> DslExecutionCoordinatorState:
        self._collector.tell(message)
        return DslExecutionCoordinatorState.COMPLETED

    def on_evaluating_context_windows_dsl_execution_failed(
            self, message: DslExecutionFailed,
    ) -> DslExecutionCoordinatorState:
        self._collector.tell(message)
        return DslExecutionCoordinatorState.COMPLETED

    def on_completed(self, message: object) -> DslExecutionCoordinatorState:
        return DslExecutionCoordinatorState.COMPLETED

    def _dispatch_find(self, query: Query) -> DslExecutionCoordinatorState:
        candidates = self._index.nodes_of_entity(query.source.entity_name)
        self._current_query = query
        self._find_results = {}
        self._pending_count = len(candidates)

        if not candidates:
            self._collector.tell(DslQueryExecuted(result=DslQueryExecutionResult(
                query=query,
                source_path=self._index.document.source_path,
                matches=[],
            )))
            return DslExecutionCoordinatorState.COMPLETED

        for index, candidate in enumerate(candidates):
            worker = self._workers[index % len(self._workers)]
            worker.tell(EvaluateFindCandidateRequest(candidate_index=index, node=candidate, query=query))

        return DslExecutionCoordinatorState.EVALUATING_FIND_CANDIDATES

    def _dispatch_context(self, query: Query) -> DslExecutionCoordinatorState:
        base_nodes = self._index.nodes_of_entity(query.source.entity_name)
        self._current_query = query
        self._context_results = {}
        self._pending_count = len(base_nodes)

        if not base_nodes:
            self._collector.tell(DslQueryExecuted(result=DslQueryExecutionResult(
                query=query,
                source_path=self._index.document.source_path,
                matches=[],
            )))
            return DslExecutionCoordinatorState.COMPLETED

        max_window_length = self._resolve_max_window_length(query.window.operator, query.window.value)
        for index in range(len(base_nodes)):
            nodes = base_nodes[index:]
            if max_window_length is not None:
                nodes = nodes[:max_window_length]
            worker = self._workers[index % len(self._workers)]
            worker.tell(EvaluateContextWindowRequest(window_index=index, nodes=nodes, query=query))

        return DslExecutionCoordinatorState.EVALUATING_CONTEXT_WINDOWS

    def _dispatch_distance(self, query: Query) -> DslExecutionCoordinatorState:
        try:
            distance_return = self._distance_calculator.distance_return(query.returns)
            pairs = self._distance_calculator.calculate_pairs(
                query.source,
                query.target,
                query.within,
                query.limit or PairLimit(mode="nearest"),
                distance_return.entity_name,
            )
            self._collector.tell(DslQueryExecuted(result=DslQueryExecutionResult(
                query=query,
                source_path=self._index.document.source_path,
                matches=pairs,
            )))
        except Exception as error:
            self._collector.tell(DslExecutionFailed(error))
        return DslExecutionCoordinatorState.COMPLETED

    def _with_context_distances(self, match: ContextWindowMatch, query: Query) -> ContextWindowMatch:
        distance_returns = [item for item in query.returns or () if isinstance(item, DistanceReturn)]
        if not distance_returns:
            return match

        selector_nodes: list[tuple[str, AstNode]] = []
        for pattern_match in match.matches:
            for node in pattern_match.nodes:
                selector_nodes.append((pattern_match.name, node))

        distances = []
        for distance_return in distance_returns:
            for left_index, (left_name, left_node) in enumerate(selector_nodes):
                for right_name, right_node in selector_nodes[left_index + 1:]:
                    if left_node.start < right_node.start:
                        first_name, first_node = left_name, left_node
                        second_name, second_node = right_name, right_node
                    else:
                        first_name, first_node = right_name, right_node
                        second_name, second_node = left_name, left_node
                    if first_node.start < second_node.end and second_node.start < first_node.end:
                        continue
                    distances.append({
                        "left": {"pattern": first_name, "node": render_compact_node(first_node)},
                        "right": {"pattern": second_name, "node": render_compact_node(second_node)},
                        "distance": {
                            "unit": distance_return.entity_name,
                            "value": self._distance_calculator.count_between(
                                first_node,
                                second_node,
                                distance_return.entity_name,
                            ),
                        },
                    })

        match.distances.extend(distances)
        return match

    @staticmethod
    def _resolve_max_window_length(operator: str, value: int) -> int | None:
        if operator == "<":
            return max(value - 1, 0)
        if operator == "<=":
            return value
        if operator == "=":
            return value
        return None

    @staticmethod
    def _minimal_windows(matches: list[ContextWindowMatch]) -> list[ContextWindowMatch]:
        unique: list[ContextWindowMatch] = []
        seen_spans: set[tuple[int, int]] = set()
        for match in sorted(matches, key=lambda item: (item.end - item.start, item.start, item.end)):
            span = (match.start, match.end)
            if span in seen_spans:
                continue
            if any(
                existing.start >= match.start and existing.end <= match.end
                for existing in unique
            ):
                continue
            seen_spans.add(span)
            unique.append(match)

        unique.sort(key=lambda item: (item.start, item.end))
        return unique
