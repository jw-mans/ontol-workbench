from __future__ import annotations

from collections import deque
from threading import Lock

from ..drivable import Drivable


class ReadyActors:
    def __init__(self) -> None:
        self._lock = Lock()
        self._scheduled: set[int] = set()
        self._ready: deque[Drivable] = deque()
        self._inflight = 0

    def attach(self, actor: Drivable) -> None:
        del actor

    def schedule(self, actor: Drivable) -> bool:
        with self._lock:
            actor_id = id(actor)
            if actor_id in self._scheduled:
                return False
            self._scheduled.add(actor_id)
            self._ready.append(actor)
            return True

    def pop(self) -> Drivable | None:
        with self._lock:
            if not self._ready:
                return None
            actor = self._ready.popleft()
            self._scheduled.discard(id(actor))
            self._inflight += 1
            return actor

    def complete(self, actor: Drivable) -> bool:
        needs_reschedule = actor.pending > 0
        with self._lock:
            self._inflight -= 1
        return needs_reschedule

    def is_idle(self) -> bool:
        with self._lock:
            return not self._ready and self._inflight == 0

    def queue_size(self) -> int:
        with self._lock:
            return len(self._ready) + self._inflight
