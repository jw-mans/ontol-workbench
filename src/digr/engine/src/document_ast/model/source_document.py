from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SourceDocument:
    path: str
    format_name: str
    text: str
