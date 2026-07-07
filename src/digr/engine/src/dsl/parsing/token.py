from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .token_kind import TokenKind


@dataclass(slots=True)
class DslToken:
    kind: TokenKind
    lexeme: str
    value: Any
    offset: int
    line: int
    column: int
