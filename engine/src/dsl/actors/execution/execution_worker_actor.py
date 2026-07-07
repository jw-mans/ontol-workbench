from __future__ import annotations

from actor import Actor, ActorHandle
from document_ast.model.ast_node import AstNode

from ...execution.messages import (
    DslExecutionFailed,
    ContextWindowEvaluated,
    EvaluateContextWindowRequest,
    EvaluateFindCandidateRequest,
    ExecutionWorkerMessage,
    FindCandidateEvaluated,
)
from ...execution.predicate_evaluator import PredicateEvaluator
from ...execution.query_results import ContextWindowMatch, FindMatch
from ...execution.states import DslExecutionWorkerState


class DslExecutionWorkerActor(Actor[DslExecutionWorkerState, ExecutionWorkerMessage, ExecutionWorkerMessage]):
    def __init__(
            self,
            evaluator: PredicateEvaluator,
            document_text: str,
            reply_to: ActorHandle[object] | None = None,
    ) -> None:
        super().__init__(DslExecutionWorkerState, DslExecutionWorkerState.READY)
        self._evaluator = evaluator
        self._document_text = document_text
        self._reply_to = reply_to

    def set_reply_to(self, handle: ActorHandle[object]) -> None:
        self._reply_to = handle

    def on_ready_evaluate_find_candidate_request(
            self, message: EvaluateFindCandidateRequest,
    ) -> DslExecutionWorkerState:
        if self._reply_to is None:
            raise RuntimeError("reply_to handle is not configured")
        try:
            query = message.query
            node = message.node
            matched = (
                self._within_constraints_satisfied([node], query)
                and (query.where is None or self._evaluator.evaluate(node, query.where))
            )
            self._reply_to.tell(FindCandidateEvaluated(
                candidate_index=message.candidate_index,
                match=FindMatch(node=node) if matched else None,
            ))
        except Exception as error:
            self._reply_to.tell(DslExecutionFailed(error))
        return DslExecutionWorkerState.READY

    def on_ready_evaluate_context_window_request(
            self, message: EvaluateContextWindowRequest,
    ) -> DslExecutionWorkerState:
        if self._reply_to is None:
            raise RuntimeError("reply_to handle is not configured")
        try:
            match = self._evaluate_context_window(message.nodes, message.query)
            self._reply_to.tell(ContextWindowEvaluated(window_index=message.window_index, match=match))
        except Exception as error:
            self._reply_to.tell(DslExecutionFailed(error))
        return DslExecutionWorkerState.READY

    def _evaluate_context_window(
            self,
            candidates: list[AstNode],
            query,
    ) -> ContextWindowMatch | None:
        for size in range(1, len(candidates) + 1):
            if not self._evaluator.compare_count(size, query.window):
                continue

            nodes = candidates[:size]
            start = nodes[0].start
            end = nodes[-1].end

            if not self._within_constraints_satisfied(nodes, query):
                continue

            text = self._document_text[start:end]
            matches = self._evaluator.match_patterns_in_window(query, text, start, end)
            if matches is None:
                continue

            window_node = AstNode(
                entity="window",
                text=text,
                start=start,
                end=end,
                children=list(nodes),
                metadata={"base_entity": query.source.entity_name},
            )
            if query.where is not None and not self._evaluator.evaluate(window_node, query.where):
                continue

            return ContextWindowMatch(
                base_entity=query.source.entity_name,
                nodes=list(nodes),
                text=text,
                start=start,
                end=end,
                matches=matches,
            )

        return None

    def _within_constraints_satisfied(self, nodes: list[AstNode], query) -> bool:
        for constraint in query.within:
            container_count = self._evaluator.count_distinct_containers(nodes, constraint.entity_name)
            if not self._evaluator.compare_count(container_count, constraint.constraint):
                return False
        return True
