from __future__ import annotations

from pathlib import Path
from typing import Any

from ..model.source_document import SourceDocument
from .source_reader import SourceReader


class PlainTextReader(SourceReader):
    def read(self, path: Path, format_name: str, reader_config: dict[str, Any]) -> SourceDocument:
        encoding = reader_config.get("encoding", "utf-8")
        text = path.read_text(encoding=encoding)
        return SourceDocument(path=str(path), format_name=format_name, text=text)
