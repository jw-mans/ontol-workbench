from __future__ import annotations

from pathlib import Path

import pytest

from uml_dsl.svg_parser import parse_svg_to_diagram
from uml_dsl.tdl_run import tdl_to_svg


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def _example_ids(paths: list[Path]) -> list[str]:
    return [path.relative_to(EXAMPLES).as_posix() for path in paths]


VALID_EXAMPLES = sorted((EXAMPLES / "tdl" / "basic").glob("*.tdl")) + sorted(
    (EXAMPLES / "app" / "render_tdl").glob("*.tdl")
)
ERROR_EXAMPLES = sorted((EXAMPLES / "tdl" / "errors").glob("*.tdl"))


@pytest.mark.parametrize("path", VALID_EXAMPLES, ids=_example_ids(VALID_EXAMPLES))
def test_valid_tdl_examples_render_and_roundtrip(path: Path, require_dot):
    svg = tdl_to_svg(path.read_text(encoding="utf-8"))
    result = parse_svg_to_diagram(svg)

    assert svg.lstrip().startswith("<svg")
    assert result.success, result.errors
    assert result.diagram is not None
    assert result.diagram.classifiers


@pytest.mark.parametrize("path", ERROR_EXAMPLES, ids=_example_ids(ERROR_EXAMPLES))
def test_error_tdl_examples_fail_validation(path: Path, require_dot):
    with pytest.raises((ValueError, RuntimeError)):
        tdl_to_svg(path.read_text(encoding="utf-8"))
