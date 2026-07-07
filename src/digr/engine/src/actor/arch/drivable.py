from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Drivable(Protocol):
    def step(self, limit: int | None = None) -> int: ...

    @property
    def pending(self) -> int: ...
