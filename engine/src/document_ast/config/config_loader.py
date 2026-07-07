from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .entity_config import EntityConfig
from .format_config import FormatConfig
from .parser_config import ParserConfig


class ConfigLoader:
    def load(self, path: str | Path, expected_format_name: str | None = None) -> ParserConfig:
        payload = self._load_yaml(path)
        self._validate_root(payload)

        format_config = self._parse_format(payload["format"])
        entities = {
            name: self._parse_entity(name, data)
            for name, data in payload["entities"].items()
        }

        self._validate_relationships(format_config, entities, expected_format_name)
        return ParserConfig(format_config=format_config, entities=entities)

    def _load_yaml(self, path: str | Path) -> dict[str, Any]:
        with Path(path).open("r", encoding="utf-8") as stream:
            payload = yaml.safe_load(stream) or {}
        if not isinstance(payload, dict):
            raise TypeError("Config root must be a mapping")
        return payload

    def _validate_root(self, payload: dict[str, Any]) -> None:
        if "format" not in payload or not isinstance(payload["format"], dict):
            raise ValueError("Config must contain 'format' mapping")
        if "entities" not in payload or not isinstance(payload["entities"], dict):
            raise ValueError("Config must contain 'entities' mapping")

    def _parse_format(self, data: Any) -> FormatConfig:
        if not isinstance(data, dict):
            raise TypeError("Format section must be a mapping")
        name = data.get("name")
        reader = data.get("reader")
        root_entity = data.get("root_entity")
        if not isinstance(name, str) or not name:
            raise ValueError("Format section must define non-empty 'name'")
        if not isinstance(reader, dict):
            raise ValueError(f"Format '{name}' must define 'reader' mapping")
        if not isinstance(root_entity, str) or not root_entity:
            raise ValueError(f"Format '{name}' must define non-empty 'root_entity'")
        symbols = data.get("symbols", {})
        if not isinstance(symbols, dict):
            raise ValueError(f"Format '{name}' symbols must be a mapping")
        exclude = symbols.get("exclude", [])
        if not isinstance(exclude, list) or any(not isinstance(item, str) for item in exclude):
            raise ValueError(f"Format '{name}' symbols.exclude must be a list of strings")
        return FormatConfig(name=name, reader=reader, root_entity=root_entity, symbols={"exclude": list(exclude)})

    def _parse_entity(self, name: str, data: Any) -> EntityConfig:
        if not isinstance(data, dict):
            raise TypeError(f"Entity '{name}' must be a mapping")
        contains_raw = data.get("contains")
        if contains_raw is None:
            contains: list[str] = []
        elif isinstance(contains_raw, str) and contains_raw:
            contains = [contains_raw]
        elif (
                isinstance(contains_raw, list)
                and all(isinstance(item, str) and item for item in contains_raw)
        ):
            contains = list(contains_raw)
        else:
            raise ValueError(f"Entity '{name}' has invalid 'contains'")
        segmenter = data.get("segmenter")
        if not isinstance(segmenter, dict):
            raise ValueError(f"Entity '{name}' must define 'segmenter' mapping")
        if "kind" not in segmenter or not isinstance(segmenter["kind"], str):
            raise ValueError(f"Entity '{name}' segmenter must define string 'kind'")
        symbols = data.get("symbols")
        if symbols is not None and not isinstance(symbols, bool):
            raise ValueError(f"Entity '{name}' symbols must be a boolean")
        return EntityConfig(name=name, contains=contains, segmenter=segmenter, symbols=symbols)

    def _validate_relationships(
            self,
            format_config: FormatConfig,
            entities: dict[str, EntityConfig],
            expected_format_name: str | None,
    ) -> None:
        if expected_format_name is not None and format_config.name != expected_format_name:
            raise ValueError(
                f"Config format name '{format_config.name}' does not match expected "
                f"format '{expected_format_name}'"
            )

        if format_config.root_entity not in entities:
            raise ValueError(
                f"Format '{format_config.name}' references unknown root_entity "
                f"'{format_config.root_entity}'"
            )

        for entity in entities.values():
            for child in entity.contains:
                if child not in entities:
                    raise ValueError(
                        f"Entity '{entity.name}' references unknown child '{child}'"
                    )

        self._validate_no_cycles(entities)

    def _validate_no_cycles(self, entities: dict[str, EntityConfig]) -> None:
        visited: set[str] = set()
        active: set[str] = set()

        def walk(name: str) -> None:
            if name in active:
                raise ValueError(f"Entity hierarchy contains a cycle at '{name}'")
            if name in visited:
                return

            active.add(name)
            for child in entities[name].contains:
                walk(child)
            active.remove(name)
            visited.add(name)

        for name in entities:
            walk(name)
