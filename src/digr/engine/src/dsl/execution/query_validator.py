from __future__ import annotations

from ..model.query_ast import (
    BinaryExpression,
    ComparisonExpression,
    DistanceReturn,
    Expression,
    FieldRef,
    FunctionExpression,
    NotExpression,
    Pattern,
    Query,
    Selector,
    SpanSpec,
)
from .document_index import DocumentIndex


class QueryValidator:
    # грамматика разрешает поля хвоста всем kind одинаково, уместность - здесь

    def validate(self, query: Query, index: DocumentIndex) -> None:
        known_entities = index.entities() | {"symbol"}
        missing_entities = sorted(self._collect_entities(query) - known_entities)
        if missing_entities:
            raise ValueError(
                "Query references unknown AST entities: "
                + ", ".join(missing_entities)
            )
        self._validate_kind_specific_fields(query)

    def _validate_kind_specific_fields(self, query: Query) -> None:
        distance_returns = [item for item in query.returns or () if isinstance(item, DistanceReturn)]

        if query.kind == "DISTANCE":
            if query.target is None:
                raise ValueError("DISTANCE query requires a TO selector")
            if len(distance_returns) != 1:
                raise ValueError("DISTANCE query requires exactly one RETURN distance(entity) item")
            return

        if query.limit is not None:
            raise ValueError(f"LIMIT_PAIRS is only meaningful for DISTANCE, not {query.kind}")

        if query.kind == "CONTEXT":
            if not query.patterns:
                raise ValueError("CONTEXT query must have at least one FOR pattern")
            if query.window is None:
                raise ValueError("CONTEXT query must specify a window length constraint")
            return

        # FIND
        if distance_returns:
            raise ValueError("RETURN distance(entity) is only meaningful for CONTEXT and DISTANCE, not FIND")

    def _collect_entities(self, query: Query) -> set[str]:
        items: set[str] = {query.source.entity_name}
        if query.source.predicate is not None:
            items.update(self._collect_expression_entities(query.source.predicate))
        if query.target is not None:
            items.update(self._collect_selector_entities(query.target))
        for pattern in query.patterns or ():
            items.update(self._collect_pattern_entities(pattern))
        for within in query.within:
            items.add(within.entity_name)
        if query.where is not None:
            items.update(self._collect_expression_entities(query.where))
        for item in query.returns or ():
            if isinstance(item, DistanceReturn):
                items.add(item.entity_name)
        return items

    def _collect_pattern_entities(self, pattern: Pattern) -> set[str]:
        source = pattern.source
        if isinstance(source, Selector):
            return self._collect_selector_entities(source)
        return set()

    def _collect_selector_entities(self, selector: Selector) -> set[str]:
        items = {selector.entity_name}
        if selector.predicate is not None:
            items.update(self._collect_expression_entities(selector.predicate))
        return items

    def _collect_expression_entities(self, expression: Expression) -> set[str]:
        if isinstance(expression, ComparisonExpression):
            return set()
        if isinstance(expression, NotExpression):
            return self._collect_expression_entities(expression.operand)
        if isinstance(expression, BinaryExpression):
            return self._collect_expression_entities(expression.left) | self._collect_expression_entities(expression.right)
        if isinstance(expression, FunctionExpression):
            items: set[str] = set()
            for argument in expression.arguments:
                if isinstance(argument, Selector):
                    items.update(self._collect_selector_entities(argument))
                elif isinstance(argument, SpanSpec):
                    items.add(argument.entity_name)
                elif isinstance(argument, FieldRef):
                    continue
            return items
        return set()
