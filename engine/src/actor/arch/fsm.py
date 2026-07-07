from __future__ import annotations

import re
from abc import ABC
from enum import Enum
from typing import Generic, TypeVar, cast

from .inbox_like import InboxLike

State = TypeVar("State", bound=Enum)
QueueItem = TypeVar("QueueItem")
Message = TypeVar("Message")


def _snake_case(name: str) -> str:
    name = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return name.replace("__", "_").lower()


class Fsm(Generic[State, QueueItem, Message], ABC):
    def __init__(
            self,
            state_type: type[State],
            initial_state: State,
            inbox: InboxLike[QueueItem],
    ) -> None:
        if not isinstance(initial_state, state_type):
            raise TypeError(
                f"initial_state must be an instance of {state_type.__name__}, "
                f"got {type(initial_state).__name__}"
            )

        self._state_type = state_type
        self.state: State = initial_state
        self._inbox = inbox

    @property
    def state_type(self) -> type[State]:
        return self._state_type

    @property
    def states(self) -> tuple[State, ...]:
        return tuple(self._state_type)

    @property
    def inbox(self) -> InboxLike[QueueItem]:
        return self._inbox

    def step(self, limit: int | None = None) -> int:
        if limit is not None and limit < 0:
            raise ValueError(f"limit must be >= 0, got {limit}")

        processed = 0
        while limit is None or processed < limit:
            item = self._inbox.get_nowait()
            if item is None:
                break

            message = self.extract_message(item)
            new_state = self.handle(message)
            self._validate_state(new_state)
            self.state = new_state
            processed += 1

        return processed

    def extract_message(self, item: QueueItem) -> Message:
        if hasattr(item, "message"):
            return cast(Message, getattr(item, "message"))
        return cast(Message, item)

    def handle(self, message: Message) -> State:
        for method_name in self._iter_handler_names(self.state, message):
            handler = getattr(self, method_name, None)
            if handler is not None:
                return cast(State, handler(message))
        return self.on_unhandled_message(message)

    def on_unhandled_message(self, message: Message) -> State:
        tried = ", ".join(self._iter_handler_names(self.state, message))
        raise NotImplementedError(
            f"No handler for state {self.state!r} and message "
            f"{type(message).__name__}. Tried: {tried}"
        )

    def _get_handler_name(self, state: State) -> str:
        return f"on_{state.name.lower()}"

    def _iter_handler_names(self, state: State, message: Message) -> list[str]:
        state_name = self._get_handler_name(state)
        message_types = [cls for cls in type(message).__mro__ if cls is not object]
        message_names = [_snake_case(cls.__name__) for cls in message_types]

        return [
            *(f"{state_name}_{message_name}" for message_name in message_names),
            state_name,
            *(f"on_{message_name}" for message_name in message_names),
            "on_any",
        ]

    def _validate_state(self, value: object) -> None:
        if not isinstance(value, self._state_type):
            raise TypeError(
                f"Handler must return {self._state_type.__name__}, "
                f"got {type(value).__name__}: {value!r}"
            )
