from __future__ import annotations

from threading import Condition, Thread

from ..arch.base_actor_driver import BaseActorDriver
from ..arch.drivable import Drivable
from ..arch.step_limits import validate_step_limit


class ThreadedActorDriver(BaseActorDriver):
    def __init__(
            self,
            step_limit: int | None = 1,
            *,
            name: str = "actor-driver",
            daemon: bool = True,
    ) -> None:
        super().__init__()
        self._step_limit = validate_step_limit(step_limit)
        self._closing = False
        self._condition = Condition()
        self._thread = Thread(target=self._run, name=name, daemon=daemon)
        self._thread.start()

    def schedule(self, actor: Drivable) -> None:
        if self._schedule_actor(actor):
            with self._condition:
                self._condition.notify()

    def wait_until_idle(self, timeout: float | None = None) -> bool:
        with self._condition:
            return self._condition.wait_for(self.is_idle, timeout)

    def close(self) -> None:
        with self._condition:
            self._closing = True
            self._condition.notify_all()
        self._thread.join()

    def _run(self) -> None:
        while True:
            actor = self._pop_ready_actor()
            if actor is None:
                with self._condition:
                    if self._closing:
                        return
                    self._condition.wait()
                continue

            try:
                actor.step(self._step_limit)
            finally:
                self._complete_actor(actor)
                with self._condition:
                    self._condition.notify_all()
