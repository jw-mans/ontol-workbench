from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AstNode:
    entity: str
    text: str
    start: int
    end: int
    children: list["AstNode"] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity": self.entity,
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "metadata": self.metadata,
            "children": [child.to_dict() for child in self.children],
        }
