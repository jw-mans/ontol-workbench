from __future__ import annotations

from typing import Generic, TypeVar

from ..output.output import Output

Message = TypeVar("Message")


class ActorHandle(Generic[Message]):
    def __init__(self, output: Output[Message]) -> None:
        self._output = output

    @property
    def output(self) -> Output[Message]:
        return self._output

    def put(self, message: Message) -> None:
        self._output.put(message)

    def tell(self, message: Message) -> None:
        self.put(message)
