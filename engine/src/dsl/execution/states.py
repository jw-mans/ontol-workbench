from __future__ import annotations

from enum import Enum, auto


class DslExecutionCoordinatorState(Enum):
    IDLE = auto()
    EVALUATING_FIND_CANDIDATES = auto()
    EVALUATING_CONTEXT_WINDOWS = auto()
    COMPLETED = auto()


class DslExecutionWorkerState(Enum):
    READY = auto()


class DslExecutionCollectorState(Enum):
    EMPTY = auto()
    HAS_RESULT = auto()
    HAS_ERROR = auto()
