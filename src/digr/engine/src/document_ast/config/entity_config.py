from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class EntityConfig:
    name: str
    contains: list[str]
    segmenter: dict[str, Any]
    symbols: bool | None = None
