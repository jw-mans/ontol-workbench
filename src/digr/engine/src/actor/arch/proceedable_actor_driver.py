from __future__ import annotations

from abc import ABC, abstractmethod

from .actor_driver import ActorDriver


class ProceedableActorDriver(ActorDriver, ABC):
    @abstractmethod
    def proceed(self, step_limit: int | None = None) -> int:
        pass

    def drain(self, step_limit: int | None = None) -> int:
        processed = 0
        while True:
            current = self.proceed(step_limit)
            if current == 0:
                return processed
            processed += current
