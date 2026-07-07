from __future__ import annotations

import json

import main as main_module


def test_build_parser_uses_expected_defaults() -> None:
    parser = main_module.build_parser()
    args = parser.parse_args([])

    assert args.source == "text.txt"
    assert args.config_dir == "config/formats"
    assert args.format_name is None


def test_read_query_interactively_supports_exit(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "_stdin_prompt", lambda prompt: "EXIT")

    assert main_module._read_query_interactively() is None


def test_read_query_interactively_collects_multiline_query(monkeypatch) -> None:
    values = iter(["FIND sentence", "WHERE text = \"x\"", "", ""])
    monkeypatch.setattr(main_module, "_stdin_prompt", lambda prompt: next(values))

    assert main_module._read_query_interactively() == 'FIND sentence\nWHERE text = "x"'


def test_main_noninteractive_outputs_json(sample_text_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(main_module.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(main_module.sys.stdout, "isatty", lambda: False)

    exit_code = main_module.main([str(sample_text_path), "--format", "txt"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["format"] == "txt"
    assert payload["root_entity"] == "page"
