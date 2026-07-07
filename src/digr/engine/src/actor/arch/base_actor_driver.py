from __future__ import annotations

from abc import ABC

from .actor_driver import ActorDriver
from .drivable import Drivable
from .internal.ready_actors import ReadyActors


class BaseActorDriver(ActorDriver, ABC):
    def __init__(self) -> None:
        self._ready_actors = ReadyActors()

    def attach(self, actor: Drivable) -> None:
        self._ready_actors.attach(actor)

    def schedule(self, actor: Drivable) -> None:
        self._schedule_actor(actor)

    def is_idle(self) -> bool:
        return self._ready_actors.is_idle()

    def queue_size(self) -> int:
        return self._ready_actors.queue_size()

    def _pop_ready_actor(self) -> Drivable | None:
        return self._ready_actors.pop()

    def _complete_actor(self, actor: Drivable) -> None:
        if self._ready_actors.complete(actor):
            self.schedule(actor)

    def _schedule_actor(self, actor: Drivable) -> bool:
        return self._ready_actors.schedule(actor)
