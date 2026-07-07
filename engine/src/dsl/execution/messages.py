from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from document_ast.model.ast_node import AstNode

from ..model.query_ast import Query
from .query_results import ContextWindowMatch, DslExecutionResult, FindMatch


@dataclass(slots=True)
class ExecuteDslQueryRequest:
    query: Query


@dataclass(slots=True)
class EvaluateFindCandidateRequest:
    candidate_index: int
    node: AstNode
    query: Query


@dataclass(slots=True)
class FindCandidateEvaluated:
    candidate_index: int
    match: FindMatch | None


@dataclass(slots=True)
class EvaluateContextWindowRequest:
    window_index: int
    nodes: list[AstNode]
    query: Query


@dataclass(slots=True)
class ContextWindowEvaluated:
    window_index: int
    match: ContextWindowMatch | None


@dataclass(slots=True)
class DslQueryExecuted:
    result: DslExecutionResult


@dataclass(slots=True)
class DslExecutionFailed:
    error: Exception


ExecutionCoordinatorMessage = Union[
    ExecuteDslQueryRequest,
    FindCandidateEvaluated,
    ContextWindowEvaluated,
    DslExecutionFailed,
]

ExecutionWorkerMessage = Union[
    EvaluateFindCandidateRequest,
    EvaluateContextWindowRequest,
]

ExecutionCollectorMessage = Union[
    DslQueryExecuted,
    DslExecutionFailed,
]
