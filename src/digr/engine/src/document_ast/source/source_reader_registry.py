from __future__ import annotations

from pathlib import Path
from typing import Any

from ..model.source_document import SourceDocument
from .plain_text_reader import PlainTextReader
from .source_reader import SourceReader


class SourceReaderRegistry:
    def __init__(self) -> None:
        self._readers: dict[str, SourceReader] = {
            "plain_text": PlainTextReader(),
        }

    def read(self, path: str | Path, format_name: str, reader_config: dict[str, Any]) -> SourceDocument:
        kind = reader_config.get("kind")
        if not isinstance(kind, str) or not kind:
            raise ValueError(f"Format '{format_name}' reader must define non-empty 'kind'")
        try:
            reader = self._readers[kind]
        except KeyError as exc:
            raise KeyError(
                f"Reader kind '{kind}' is not registered. "
                f"Add a SourceReader implementation for this format."
            ) from exc
        return reader.read(Path(path), format_name, reader_config)
