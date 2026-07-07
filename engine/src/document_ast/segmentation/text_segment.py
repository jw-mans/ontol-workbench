from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TextSegment:
    text: str
    start: int
    end: int
    metadata: dict[str, Any] = field(default_factory=dict)
