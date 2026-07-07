from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

QueueItem = TypeVar("QueueItem")


@runtime_checkable
class InboxLike(Protocol[QueueItem]):
    def get_nowait(self) -> QueueItem | None: ...
