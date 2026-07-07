from __future__ import annotations

from enum import Enum, auto

import pytest

from actor import Actor, ManualActorDriver
from actor.arch.fsm import Fsm
from actor.arch.internal.ready_actors import ReadyActors
from actor.arch.mailbox import Mailbox
from actor.arch.step_limits import validate_step_limit


class IdleState(Enum):
    IDLE = auto()


class RecordingActor(Actor[IdleState, int, int]):
    def __init__(self) -> None:
        super().__init__(IdleState, IdleState.IDLE)
        self.events: list[int] = []

    def on_idle_int(self, message: int) -> IdleState:
        self.events.append(message)
        if message == 1:
            self.put(2)
        return IdleState.IDLE


class BadStateFsm(Fsm[IdleState, int, int]):
    def __init__(self) -> None:
        super().__init__(IdleState, IdleState.IDLE, Mailbox([1]))

    def on_idle_int(self, message: int):  # type: ignore[override]
        del message
        return "bad-state"


class EmptyFsm(Fsm[IdleState, object, object]):
    def __init__(self) -> None:
        super().__init__(IdleState, IdleState.IDLE, Mailbox([object()]))


class StubDrivable:
    def __init__(self, pending: int = 0) -> None:
        self._pending = pending

    @property
    def pending(self) -> int:
        return self._pending

    def step(self, limit: int | None = None) -> int:
        del limit
        processed = self._pending
        self._pending = 0
        return processed


def test_validate_step_limit_accepts_positive_values() -> None:
    assert validate_step_limit(None) is None
    assert validate_step_limit(3) == 3


@pytest.mark.parametrize("value", [0, -1])
def test_validate_step_limit_rejects_non_positive_values(value: int) -> None:
    with pytest.raises(ValueError, match="step_limit must be > 0"):
        validate_step_limit(value)


def test_mailbox_preserves_fifo_order() -> None:
    mailbox = Mailbox([1])
    mailbox.put(2)
    mailbox.extend([3, 4])

    assert len(mailbox) == 4
    assert mailbox.get_nowait() == 1
    assert mailbox.get_nowait() == 2
    assert mailbox.get_nowait() == 3
    assert mailbox.get_nowait() == 4
    assert mailbox.get_nowait() is None
    assert mailbox.empty() is True


def test_ready_actors_deduplicates_and_reschedules_pending_actor() -> None:
    ready = ReadyActors()
    actor = StubDrivable(pending=2)

    assert ready.schedule(actor) is True
    assert ready.schedule(actor) is False
    assert ready.queue_size() == 1

    popped = ready.pop()
    assert popped is actor
    assert ready.queue_size() == 1
    assert ready.complete(actor) is True
    assert ready.is_idle() is True


def test_manual_actor_driver_drains_actor_and_handle_roundtrip() -> None:
    driver = ManualActorDriver(step_limit=1)
    actor = RecordingActor().bind(driver)

    actor.as_handle().tell(1)

    assert driver.drain() == 2
    assert actor.events == [1, 2]
    assert driver.is_idle() is True


def test_fsm_rejects_negative_step_limit() -> None:
    actor = RecordingActor()
    actor.put(1)

    with pytest.raises(ValueError, match="limit must be >= 0"):
        actor.step(-1)


def test_fsm_raises_on_unhandled_message() -> None:
    fsm = EmptyFsm()

    with pytest.raises(NotImplementedError, match="No handler for state"):
        fsm.step()


def test_fsm_rejects_invalid_state_return_type() -> None:
    fsm = BadStateFsm()

    with pytest.raises(TypeError, match="Handler must return IdleState"):
        fsm.step()
