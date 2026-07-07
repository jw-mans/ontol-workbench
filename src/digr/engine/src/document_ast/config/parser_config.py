from __future__ import annotations

from dataclasses import dataclass

from .entity_config import EntityConfig
from .format_config import FormatConfig


@dataclass(slots=True)
class ParserConfig:
    format_config: FormatConfig
    entities: dict[str, EntityConfig]

    @property
    def format_name(self) -> str:
        return self.format_config.name

    def get_entity(self, entity_name: str) -> EntityConfig:
        try:
            return self.entities[entity_name]
        except KeyError as exc:
            raise KeyError(f"Unknown entity: {entity_name}") from exc
