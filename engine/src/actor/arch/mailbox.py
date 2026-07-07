from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Generic, Iterable, TypeVar

QueueItem = TypeVar("QueueItem")


class Mailbox(Generic[QueueItem]):
    def __init__(self, items: Iterable[QueueItem] = ()) -> None:
        self._items: deque[QueueItem] = deque(items)
        self._lock = Lock()

    def put(self, item: QueueItem) -> None:
        with self._lock:
            self._items.append(item)

    def extend(self, items: Iterable[QueueItem]) -> None:
        with self._lock:
            self._items.extend(items)

    def get_nowait(self) -> QueueItem | None:
        with self._lock:
            if not self._items:
                return None
            return self._items.popleft()

    def empty(self) -> bool:
        with self._lock:
            return not self._items

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
