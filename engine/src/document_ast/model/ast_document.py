from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .ast_node import AstNode


@dataclass(slots=True)
class AstDocument:
    source_path: str
    format_name: str
    root_entity: str
    root: AstNode

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "format": self.format_name,
            "root_entity": self.root_entity,
            "root": self.root.to_dict(),
        }
