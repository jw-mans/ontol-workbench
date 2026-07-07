from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

Message = TypeVar("Message")


@runtime_checkable
class Output(Protocol[Message]):
    def put(self, message: Message) -> None: ...
