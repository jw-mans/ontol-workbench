from __future__ import annotations

from pathlib import Path

from ..config.config_loader import ConfigLoader
from ..model.ast_document import AstDocument
from ..runtime.messages import ParseDocumentRequest
from ..runtime.pipeline_runtime import ParserRuntimeFactory


class ActorAstParser:
    def __init__(self, config_dir: str | Path, loader: ConfigLoader | None = None) -> None:
        self._config_dir = Path(config_dir)
        self._loader = loader or ConfigLoader()

    @classmethod
    def from_config_dir(cls, path: str | Path) -> "ActorAstParser":
        return cls(path)

    def parse(self, path: str | Path, format_name: str | None = None) -> AstDocument:
        source_path = Path(path)
        resolved_format = format_name or self._detect_format(source_path)
        config = self._load_config_for_format(resolved_format)
        runtime = ParserRuntimeFactory().create(config)
        runtime.coordinator.put(ParseDocumentRequest(path=str(source_path), format_name=resolved_format))
        runtime.driver.drain()

        if runtime.collector.result is None:
            raise RuntimeError("Parser finished without ParseCompleted result")
        return runtime.collector.result

    def _detect_format(self, path: Path) -> str:
        suffix = path.suffix.lower().lstrip(".")
        if not suffix:
            raise ValueError(f"Cannot detect format from path without extension: {path}")
        return suffix

    def _load_config_for_format(self, format_name: str):
        config_path = self._config_dir / f"{format_name}.yaml"
        if not config_path.exists():
            raise FileNotFoundError(
                f"Format config not found for '{format_name}': {config_path}"
            )
        return self._loader.load(config_path, expected_format_name=format_name)
