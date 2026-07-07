from __future__ import annotations

from pathlib import Path

from document_ast import ActorAstParser


def test_ast_parser_builds_document_from_sample_file(sample_text_path: Path, config_dir: Path) -> None:
    document = ActorAstParser.from_config_dir(config_dir).parse(sample_text_path, format_name="txt")

    assert document.source_path.endswith("text.txt")
    assert document.root_entity == "page"
    assert document.root.children[0].entity == "page"


def test_end_to_end_follows_query(sample_document, dsl_engine) -> None:
    payload = dsl_engine.execute(
        sample_document,
        """
        FIND sentence
        WHERE follows(sentence[text ~= /Только тишина/])
        RETURN text
        """.strip(),
    ).to_dict()

    assert payload["count"] == 1
    assert payload["items"][0]["text"] == "И эта тишина сейчас казалась ему почти осязаемой."
