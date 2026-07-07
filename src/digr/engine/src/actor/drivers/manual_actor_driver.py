from __future__ import annotations

from ..arch.base_actor_driver import BaseActorDriver
from ..arch.proceedable_actor_driver import ProceedableActorDriver
from ..arch.step_limits import validate_step_limit


class ManualActorDriver(BaseActorDriver, ProceedableActorDriver):
    def __init__(self, step_limit: int | None = 1) -> None:
        super().__init__()
        self._step_limit = validate_step_limit(step_limit)

    def proceed(self, step_limit: int | None = None) -> int:
        actor = self._pop_ready_actor()
        if actor is None:
            return 0

        processed = actor.step(self._step_limit if step_limit is None else validate_step_limit(step_limit))
        self._complete_actor(actor)
        return processed
