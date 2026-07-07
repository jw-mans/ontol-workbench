from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from document_ast import ActorAstParser, ConfigLoader
from document_ast.model.source_document import SourceDocument
from document_ast.runtime.ast_builder import AstBuilder
from document_ast.source.plain_text_reader import PlainTextReader
from document_ast.source.source_reader_registry import SourceReaderRegistry


def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)


def test_plain_text_reader_reads_utf8(workspace_tmp: Path) -> None:
    source = workspace_tmp / "sample.txt"
    source.write_text("Привет", encoding="utf-8")

    document = PlainTextReader().read(source, "txt", {"encoding": "utf-8"})

    assert document.path == str(source)
    assert document.format_name == "txt"
    assert document.text == "Привет"


def test_source_reader_registry_validates_kind(workspace_tmp: Path) -> None:
    source = workspace_tmp / "sample.txt"
    source.write_text("text", encoding="utf-8")
    registry = SourceReaderRegistry()

    with pytest.raises(ValueError, match="non-empty 'kind'"):
        registry.read(source, "txt", {})

    with pytest.raises(KeyError, match="is not registered"):
        registry.read(source, "txt", {"kind": "custom"})


def test_ast_builder_builds_expected_hierarchy(txt_config) -> None:
    document = SourceDocument(path="memory.txt", format_name="txt", text="One. Two!")
    built = AstBuilder(txt_config).build(document)

    assert built.root.entity == "document"
    assert built.root_entity == "page"
    assert len(built.root.children) == 1

    sentences = [node for node in walk(built.root) if node.entity == "sentence"]
    words = [node for node in walk(built.root) if node.entity == "word"]
    symbols = [node for node in walk(built.root) if node.entity == "symbol"]
    assert [node.text for node in sentences] == ["One.", "Two!"]
    assert [node.text for node in words] == ["One", "Two"]
    assert [node.text for node in symbols] == ["O", "n", "e", "T", "w", "o"]
    assert [(node.start, node.end) for node in symbols[:3]] == [(0, 1), (1, 2), (2, 3)]


def test_ast_builder_respects_symbol_exclusions(workspace_tmp: Path) -> None:
    config_path = workspace_tmp / "sample.yaml"
    config_path.write_text(
        dedent(
            """
            format:
              name: sample
              reader:
                kind: plain_text
              root_entity: page
              symbols:
                exclude: [" "]
            entities:
              page:
                segmenter:
                  kind: passthrough
            """
        ).strip() + "\n",
        encoding="utf-8",
    )
    config = ConfigLoader().load(config_path, expected_format_name="sample")
    document = SourceDocument(path="memory.txt", format_name="sample", text="A B")

    built = AstBuilder(config).build(document)
    symbols = [node for node in walk(built.root) if node.entity == "symbol"]

    assert [node.text for node in symbols] == ["A", "B"]
    assert [(node.start, node.end) for node in symbols] == [(0, 1), (2, 3)]


def test_ast_builder_rejects_mismatched_document_format(txt_config) -> None:
    document = SourceDocument(path="memory.txt", format_name="md", text="Text")

    with pytest.raises(ValueError, match="Runtime config is for format 'txt'"):
        AstBuilder(txt_config).build(document)


def test_actor_ast_parser_autodetects_format(sample_text_path: Path, config_dir: Path) -> None:
    document = ActorAstParser.from_config_dir(config_dir).parse(sample_text_path)

    assert document.format_name == "txt"
    assert document.root_entity == "page"
    assert document.root.metadata["format"] == "txt"


def test_actor_ast_parser_requires_extension_for_auto_detection(workspace_tmp: Path, config_dir: Path) -> None:
    source = workspace_tmp / "sample"
    source.write_text("Plain text", encoding="utf-8")
    parser = ActorAstParser.from_config_dir(config_dir)

    with pytest.raises(ValueError, match="Cannot detect format from path without extension"):
        parser.parse(source)


def test_actor_ast_parser_raises_for_missing_format_config(sample_text_path: Path, config_dir: Path) -> None:
    parser = ActorAstParser.from_config_dir(config_dir)

    with pytest.raises(FileNotFoundError, match="Format config not found"):
        parser.parse(sample_text_path, format_name="missing")
