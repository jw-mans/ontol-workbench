from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class FormatConfig:
    name: str
    reader: dict[str, Any]
    root_entity: str
    symbols: dict[str, Any] = field(default_factory=dict)
