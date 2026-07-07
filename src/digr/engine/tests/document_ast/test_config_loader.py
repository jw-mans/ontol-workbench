from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from document_ast import ConfigLoader


def write_config(path: Path, content: str) -> Path:
    path.write_text(dedent(content).strip() + "\n", encoding="utf-8")
    return path


def minimal_config(*, child: str | None = None) -> str:
    contains = f"        contains: {child}\n" if child else ""
    return f"""
    format:
      name: sample
      reader:
        kind: plain_text
      root_entity: page

    entities:
      page:
{contains}        segmenter:
          kind: passthrough
      sentence:
        segmenter:
          kind: match
          pattern: ".+"
    """


def test_config_loader_parses_current_txt_config(config_dir: Path) -> None:
    config = ConfigLoader().load(config_dir / "txt.yaml", expected_format_name="txt")

    assert config.format_name == "txt"
    assert config.format_config.root_entity == "page"
    assert config.format_config.symbols == {"exclude": []}
    assert config.get_entity("sentence").contains == ["clause"]


def test_config_loader_parses_symbol_exclusions(workspace_tmp: Path) -> None:
    path = write_config(
        workspace_tmp / "config.yaml",
        """
        format:
          name: sample
          reader:
            kind: plain_text
          root_entity: page
          symbols:
            exclude: [" ", "\\n"]
        entities:
          page:
            segmenter:
              kind: passthrough
        """,
    )

    config = ConfigLoader().load(path, expected_format_name="sample")

    assert config.format_config.symbols == {"exclude": [" ", "\n"]}


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("{}", "Config must contain 'format' mapping"),
        ("format: {}\n", "Config must contain 'entities' mapping"),
    ],
)
def test_config_loader_validates_root_sections(workspace_tmp: Path, content: str, message: str) -> None:
    path = write_config(workspace_tmp / "broken.yaml", content)

    with pytest.raises(ValueError, match=message):
        ConfigLoader().load(path)


def test_config_loader_rejects_format_name_mismatch(workspace_tmp: Path) -> None:
    path = write_config(workspace_tmp / "config.yaml", minimal_config(child="sentence"))

    with pytest.raises(ValueError, match="does not match expected format"):
        ConfigLoader().load(path, expected_format_name="other")


def test_config_loader_rejects_unknown_root_entity(workspace_tmp: Path) -> None:
    path = write_config(
        workspace_tmp / "config.yaml",
        """
        format:
          name: sample
          reader:
            kind: plain_text
          root_entity: chapter
        entities:
          page:
            segmenter:
              kind: passthrough
        """,
    )

    with pytest.raises(ValueError, match="unknown root_entity"):
        ConfigLoader().load(path)


def test_config_loader_rejects_unknown_child_entity(workspace_tmp: Path) -> None:
    path = write_config(workspace_tmp / "config.yaml", minimal_config(child="missing"))

    with pytest.raises(ValueError, match="unknown child"):
        ConfigLoader().load(path)


def test_config_loader_rejects_cycles(workspace_tmp: Path) -> None:
    path = write_config(
        workspace_tmp / "config.yaml",
        """
        format:
          name: sample
          reader:
            kind: plain_text
          root_entity: page
        entities:
          page:
            contains: sentence
            segmenter:
              kind: passthrough
          sentence:
            contains: page
            segmenter:
              kind: match
              pattern: ".+"
        """,
    )

    with pytest.raises(ValueError, match="contains a cycle"):
        ConfigLoader().load(path)


def test_config_loader_rejects_invalid_symbol_exclusions(workspace_tmp: Path) -> None:
    path = write_config(
        workspace_tmp / "config.yaml",
        """
        format:
          name: sample
          reader:
            kind: plain_text
          root_entity: page
          symbols:
            exclude: " "
        entities:
          page:
            segmenter:
              kind: passthrough
        """,
    )

    with pytest.raises(ValueError, match="symbols.exclude"):
        ConfigLoader().load(path)
