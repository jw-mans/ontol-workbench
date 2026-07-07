from __future__ import annotations

from enum import Enum, auto


class CoordinatorState(Enum):
    IDLE = auto()
    WAITING_FOR_DOCUMENT = auto()
    BUILDING_SUBTREES = auto()
    COMPLETED = auto()


class WorkerState(Enum):
    IDLE = auto()
