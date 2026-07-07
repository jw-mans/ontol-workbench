from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from ..model.source_document import SourceDocument


class SourceReader(ABC):
    @abstractmethod
    def read(self, path: Path, format_name: str, reader_config: dict[str, Any]) -> SourceDocument:
        pass
