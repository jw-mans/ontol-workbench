from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar

from .drivable import Drivable

DrivableImpl = TypeVar("DrivableImpl", bound=Drivable)


class ActorDriver(ABC):
    def bind(self, actor: DrivableImpl) -> DrivableImpl:
        bind = getattr(actor, "bind", None)
        if callable(bind):
            bind(self)
            return actor
        self.attach(actor)
        return actor

    @abstractmethod
    def attach(self, actor: Drivable) -> None:
        pass

    @abstractmethod
    def schedule(self, actor: Drivable) -> None:
        pass

    @abstractmethod
    def is_idle(self) -> bool:
        pass

    @abstractmethod
    def queue_size(self) -> int:
        pass

    def close(self) -> None:
        pass
