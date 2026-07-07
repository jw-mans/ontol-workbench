from __future__ import annotations

from bisect import bisect_left

from document_ast.model.ast_node import AstNode

from ..model.query_ast import CountConstraint, DistanceReturn, PairLimit, Selector, WithinConstraint
from .document_index import DocumentIndex
from .predicate_evaluator import PredicateEvaluator
from .query_results import DistancePairMatch


class DistanceCalculator:
    def __init__(self, index: DocumentIndex, evaluator: PredicateEvaluator) -> None:
        self._index = index
        self._evaluator = evaluator
        self._range_cache: dict[str, tuple[list[int], list[AstNode]]] = {}

    def distance_return(self, returns: list[object] | None) -> DistanceReturn:
        distance_returns = [item for item in (returns or ()) if isinstance(item, DistanceReturn)]
        if len(distance_returns) != 1:
            raise ValueError("Distance queries require exactly one RETURN distance(entity) item")
        return distance_returns[0]

    def calculate_pairs(
            self,
            left_selector: Selector,
            right_selector: Selector,
            within: list[WithinConstraint],
            limit: PairLimit,
            unit_entity: str,
    ) -> list[DistancePairMatch]:
        left_nodes = self._select_document_nodes(left_selector)
        right_nodes = self._select_document_nodes(right_selector)

        pairs: list[DistancePairMatch] = []
        seen: set[tuple[int, int]] = set()
        for left in left_nodes:
            for right in right_nodes:
                if id(left) == id(right) or self._spans_intersect(left, right):
                    continue
                first, second = self._ordered_pair(left, right)
                pair_key = (id(first), id(second))
                if pair_key in seen:
                    continue
                seen.add(pair_key)
                if not self.within_constraints_satisfied(first, second, within):
                    continue
                distance = self.count_between(first, second, unit_entity)
                pairs.append(DistancePairMatch(left=first, right=second, distance=distance, unit=unit_entity))

        pairs.sort(key=lambda item: (item.distance, item.left.start, item.right.start, item.left.entity, item.right.entity))
        return self._apply_limit(pairs, limit)

    def count_between(self, first: AstNode, second: AstNode, unit_entity: str) -> int:
        start = min(first.end, second.end)
        end = max(first.start, second.start)
        if start > end:
            return 0
        starts, nodes = self._nodes_by_start(unit_entity)
        left = bisect_left(starts, start)
        right = bisect_left(starts, end)
        return sum(1 for node in nodes[left:right] if node.end <= end)

    def within_constraints_satisfied(
            self,
            first: AstNode,
            second: AstNode,
            within: list[WithinConstraint],
    ) -> bool:
        for constraint in within:
            count = self._distinct_container_count(first, second, constraint.entity_name)
            if not self._compare_count(count, constraint.constraint):
                return False
        return True

    def _select_document_nodes(self, selector: Selector) -> list[AstNode]:
        return [
            node for node in self._index.nodes_of_entity(selector.entity_name)
            if self._evaluator.matches_selector(node, selector)
        ]

    def _nodes_by_start(self, entity_name: str) -> tuple[list[int], list[AstNode]]:
        cached = self._range_cache.get(entity_name)
        if cached is not None:
            return cached
        nodes = self._index.nodes_of_entity(entity_name)
        starts = [node.start for node in nodes]
        cached = (starts, nodes)
        self._range_cache[entity_name] = cached
        return cached

    def _distinct_container_count(self, first: AstNode, second: AstNode, entity_name: str) -> int:
        seen: set[int] = set()
        for node in (first, second):
            for ancestor in self._index.ancestors(node):
                if ancestor.entity == entity_name:
                    seen.add(id(ancestor))
        return len(seen)

    def _compare_count(self, actual: int, constraint: CountConstraint) -> bool:
        return self._evaluator.compare_count(actual, constraint)

    @staticmethod
    def _ordered_pair(left: AstNode, right: AstNode) -> tuple[AstNode, AstNode]:
        if (left.start, left.end, left.entity) <= (right.start, right.end, right.entity):
            return left, right
        return right, left

    @staticmethod
    def _spans_intersect(left: AstNode, right: AstNode) -> bool:
        return left.start < right.end and right.start < left.end

    @staticmethod
    def _apply_limit(pairs: list[DistancePairMatch], limit: PairLimit) -> list[DistancePairMatch]:
        if limit.mode == "all":
            return pairs
        if limit.mode == "all_nearest":
            if not pairs:
                return []
            nearest = pairs[0].distance
            return [pair for pair in pairs if pair.distance == nearest]
        if limit.mode == "k":
            return pairs[:limit.value]
        return pairs[:1]
