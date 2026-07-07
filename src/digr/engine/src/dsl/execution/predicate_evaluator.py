from __future__ import annotations

import re
from typing import Any

from document_ast.model.ast_node import AstNode

from ..model.query_ast import (
    BinaryExpression,
    ComparisonExpression,
    CountConstraint,
    DslValue,
    Expression,
    FieldRef,
    FunctionExpression,
    NotExpression,
    Pattern,
    Query,
    RegexLiteral,
    Selector,
    SpanSpec,
)
from .document_index import DocumentIndex
from .query_results import PatternMatchResult


class PredicateEvaluator:
    def __init__(self, index: DocumentIndex) -> None:
        self._index = index

    def evaluate(self, node: AstNode, expression: Expression) -> bool:
        if isinstance(expression, ComparisonExpression):
            return self._evaluate_comparison(node, expression)
        if isinstance(expression, NotExpression):
            return not self.evaluate(node, expression.operand)
        if isinstance(expression, BinaryExpression):
            left_value = self.evaluate(node, expression.left)
            if expression.operator == "AND":
                return left_value and self.evaluate(node, expression.right)
            if expression.operator == "OR":
                return left_value or self.evaluate(node, expression.right)
            raise ValueError(f"Unsupported boolean operator: {expression.operator}")
        if isinstance(expression, FunctionExpression):
            return self._evaluate_function(node, expression)
        raise TypeError(f"Unsupported expression type: {type(expression).__name__}")

    def matches_selector(self, node: AstNode, selector: Selector) -> bool:
        if node.entity != selector.entity_name:
            return False
        if selector.predicate is None:
            return True
        return self.evaluate(node, selector.predicate)

    def select_nodes_within_span(self, selector: Selector, start: int, end: int) -> list[AstNode]:
        return [
            node for node in self._index.nodes_within_span(start, end, selector.entity_name)
            if self.matches_selector(node, selector)
        ]

    def match_patterns_in_window(
            self,
            query: Query,
            text: str,
            start: int,
            end: int,
    ) -> list[PatternMatchResult] | None:
        results: list[PatternMatchResult] = []
        for index, pattern in enumerate(query.patterns or (), start=1):
            name = pattern.alias or f"pattern_{index}"
            source = pattern.source
            if isinstance(source, str):
                if source not in text:
                    return None
                results.append(PatternMatchResult(name=name, source_type="string", matched_text=source))
                continue
            if isinstance(source, RegexLiteral):
                match = self._regex_search(text, source)
                if match is None:
                    return None
                results.append(PatternMatchResult(name=name, source_type="regex", matched_text=match.group(0)))
                continue

            nodes = self.select_nodes_within_span(source, start, end)
            if not nodes:
                return None
            results.append(PatternMatchResult(name=name, source_type="selector", nodes=nodes))
        return results

    def count_distinct_containers(self, nodes: list[AstNode], entity_name: str) -> int:
        seen: set[int] = set()
        for node in nodes:
            for ancestor in self._index.ancestors(node):
                if ancestor.entity == entity_name:
                    seen.add(id(ancestor))
        return len(seen)

    def compare_count(self, actual: int, constraint: CountConstraint) -> bool:
        return self._compare_scalar(actual, constraint.operator, constraint.value)

    def _evaluate_comparison(self, node: AstNode, expression: ComparisonExpression) -> bool:
        left = self._resolve_field(node, expression.left)
        right = expression.right
        if expression.operator in {"~=", "!~="}:
            matched = self._match_value(left, right)
            return matched if expression.operator == "~=" else not matched
        return self._compare_scalar(left, expression.operator, self._normalize_value(right))

    def _evaluate_function(self, node: AstNode, expression: FunctionExpression) -> bool:
        name = expression.name
        if name == "has_child":
            selector = self._selector_argument(expression, 0, name)
            return any(self.matches_selector(child, selector) for child in node.children)
        if name == "has_descendant":
            selector = self._selector_argument(expression, 0, name)
            return any(self.matches_selector(candidate, selector) for candidate in self._index.descendants(node))
        if name == "has_ancestor":
            selector = self._selector_argument(expression, 0, name)
            return any(self.matches_selector(candidate, selector) for candidate in self._index.ancestors(node))
        if name == "contains":
            return self._evaluate_contains(node, expression)
        if name == "follows":
            selector = self._selector_argument(expression, 0, name)
            previous = self._index.previous_node(node.start, selector.entity_name)
            return previous is not None and self.matches_selector(previous, selector)
        if name == "precedes":
            selector = self._selector_argument(expression, 0, name)
            next_node = self._index.next_node(node.end, selector.entity_name)
            return next_node is not None and self.matches_selector(next_node, selector)
        if name == "intersects":
            selector = self._selector_argument(expression, 0, name)
            for candidate in self._index.nodes_of_entity(selector.entity_name):
                if self.matches_selector(candidate, selector) and self._spans_intersect(node, candidate):
                    return True
            return False
        if name == "inside":
            selector = self._selector_argument(expression, 0, name)
            for candidate in self._index.container_nodes_for_span(node.start, node.end, selector.entity_name, strict=True):
                if self.matches_selector(candidate, selector):
                    return True
            return False
        raise ValueError(f"Unsupported DSL function: {name}")

    def _evaluate_contains(self, node: AstNode, expression: FunctionExpression) -> bool:
        if len(expression.arguments) != 1:
            raise ValueError("contains() expects exactly one argument")
        argument = expression.arguments[0]
        if isinstance(argument, Selector):
            return any(
                self.matches_selector(candidate, argument)
                for candidate in self._index.nodes_within_span(node.start, node.end, argument.entity_name)
            )
        if isinstance(argument, SpanSpec):
            raise NotImplementedError("SpanSpec arguments are not supported by contains() yet")
        if isinstance(argument, FieldRef):
            argument = self._resolve_field(node, argument)
        if isinstance(argument, RegexLiteral):
            return self._regex_search(node.text, argument) is not None
        return str(argument) in node.text

    def _resolve_field(self, node: AstNode, field_ref: FieldRef) -> Any:
        current: Any = node
        for part in field_ref.parts:
            if isinstance(current, AstNode):
                if part == "entity":
                    current = current.entity
                elif part == "text":
                    current = current.text
                elif part == "start":
                    current = current.start
                elif part == "end":
                    current = current.end
                elif part == "metadata":
                    current = current.metadata
                elif part == "children":
                    current = current.children
                else:
                    raise ValueError(f"Unsupported field reference: {field_ref.path}")
                continue

            if isinstance(current, dict):
                if part not in current:
                    raise ValueError(f"Unknown metadata field: {field_ref.path}")
                current = current[part]
                continue

            raise ValueError(f"Cannot access '{part}' in field reference {field_ref.path}")

        return current

    def _selector_argument(self, expression: FunctionExpression, index: int, function_name: str) -> Selector:
        if len(expression.arguments) <= index:
            raise ValueError(f"{function_name}() expects argument {index + 1}")
        argument = expression.arguments[index]
        if not isinstance(argument, Selector):
            raise ValueError(f"{function_name}() expects selector argument")
        return argument

    def _match_value(self, left: Any, right: DslValue) -> bool:
        if isinstance(right, RegexLiteral):
            return self._regex_search(str(left), right) is not None
        return str(right) in str(left)

    def _normalize_value(self, value: DslValue) -> Any:
        if isinstance(value, RegexLiteral):
            return value.pattern
        return value

    def _compare_scalar(self, left: Any, operator: str, right: Any) -> bool:
        if operator == "=":
            return left == right
        if operator == "!=":
            return left != right
        if operator == "<":
            return left < right
        if operator == "<=":
            return left <= right
        if operator == ">":
            return left > right
        if operator == ">=":
            return left >= right
        raise ValueError(f"Unsupported comparison operator: {operator}")

    def _regex_search(self, text: str, regex: RegexLiteral):
        flags = 0
        if "i" in regex.flags:
            flags |= re.IGNORECASE
        if "m" in regex.flags:
            flags |= re.MULTILINE
        if "s" in regex.flags:
            flags |= re.DOTALL
        return re.search(regex.pattern, text, flags)

    @staticmethod
    def _spans_intersect(left: AstNode, right: AstNode) -> bool:
        return left.start < right.end and right.start < left.end
