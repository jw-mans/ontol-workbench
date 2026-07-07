from __future__ import annotations

import argparse
import json
import sys

from document_ast import ActorAstParser
from dsl import ActorDslEngine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build AST for a document using actor pipeline")
    parser.add_argument("source", nargs="?", default="text.txt", help="Path to source document")
    parser.add_argument(
        "--config-dir",
        default="config/formats",
        help="Directory with per-format YAML configs (<format>.yaml)",
    )
    parser.add_argument(
        "--format",
        dest="format_name",
        default=None,
        help="Explicit format name. By default it is detected from file extension.",
    )
    return parser


def _stdin_prompt(prompt: str) -> str | None:
    print(prompt, end="", flush=True)
    raw = sys.stdin.buffer.readline()
    if raw == b"":
        return None
    return raw.rstrip(b"\r\n").decode("utf-8", errors="replace")


def _read_query_interactively() -> str | None:
    print("Введите DSL-запрос. Два пустых ввода подряд отправляют запрос. EXIT завершает работу.")
    print()

    lines: list[str] = []
    blank_streak = 0

    while True:
        line = _stdin_prompt("dsl> " if not lines else "... ")
        if line is None:
            if not lines:
                return None
            print()
            return "\n".join(lines).rstrip()

        if not lines and line.strip() == "EXIT":
            return None

        if line == "":
            blank_streak += 1
            lines.append(line)
            if blank_streak >= 2:
                while lines and lines[-1] == "":
                    lines.pop()
                query = "\n".join(lines).strip()
                return query or ""
            continue

        blank_streak = 0
        lines.append(line)


def _run_interactive_loop(source: str, config_dir: str, format_name: str | None) -> int:
    parser = ActorAstParser.from_config_dir(config_dir)
    document = parser.parse(source, format_name=format_name)
    engine = ActorDslEngine()

    print(f"Документ загружен: {document.source_path}")
    print(f"Формат: {document.format_name}")
    print(f"Корневая сущность: {document.root_entity}")
    print()

    while True:
        query = _read_query_interactively()
        if query is None:
            return 0
        if not query:
            print("Пустой запрос пропущен.")
            print()
            continue

        try:
            result = engine.execute(document, query)
        except Exception as error:
            print(f"ERROR: {error}")
            print()
            continue

        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        print()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if sys.stdin.isatty() and sys.stdout.isatty():
        return _run_interactive_loop(args.source, args.config_dir, args.format_name)

    parser = ActorAstParser.from_config_dir(args.config_dir)
    document = parser.parse(args.source, format_name=args.format_name)
    print(json.dumps(document.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
