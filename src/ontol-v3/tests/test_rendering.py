from __future__ import annotations

import subprocess
import sys

from uml_dsl.graphviz_render import available_svg_themes
from uml_dsl.svg_parser import parse_svg_to_diagram
from uml_dsl.tdl_run import tdl_to_svg

from tests.helpers import (
    AGGREGATION,
    ASSOCIATION,
    DEPENDENCY,
    GENERALIZATION,
    NAME,
    REALIZATION,
    class_block,
)


def relation_rich_tdl() -> str:
    return (
        class_block("A")
        + class_block("B")
        + class_block("C")
        + class_block("I")
        + f"{ASSOCIATION} A [1] : owner -- B [0..*] : items {NAME} \"owns\"\n"
        + f"{AGGREGATION} A -- C\n"
        + f"{DEPENDENCY} B -> C use\n"
        + f"{GENERALIZATION} B -> A\n"
        + f"{REALIZATION} C -> I\n"
    )


def test_available_themes_are_light_and_yellow_only():
    assert available_svg_themes() == ["light", "yellow"]


def test_render_embeds_theme_edges_markers_and_multiplicities(require_dot):
    svg = tdl_to_svg(relation_rich_tdl(), theme="yellow")

    assert svg.lstrip().startswith("<svg")
    assert 'class="uml-diagram"' in svg
    assert 'data-theme="yellow"' in svg
    assert 'id="uml-theme-yellow"' in svg
    assert 'data-type="association"' in svg
    assert 'data-name="owns"' in svg
    assert 'data-end1-multiplicity="1"' in svg
    assert 'data-end2-multiplicity="0..*"' in svg
    assert 'marker-end="url(#triangle-empty)"' in svg
    assert 'marker-end="url(#arrow-filled)"' in svg
    assert 'marker-start="url(#diamond-empty)"' in svg
    assert '<path class="uml-edge-line"' in svg
    assert '>1</text>' in svg
    assert '>0..*</text>' in svg


def test_unknown_theme_falls_back_to_light(require_dot):
    svg = tdl_to_svg(class_block("A"), theme="../dark")

    assert 'data-theme="light"' in svg
    assert 'id="uml-theme-light"' in svg


def test_rendered_svg_can_be_parsed_back_to_diagram(require_dot):
    svg = tdl_to_svg(relation_rich_tdl())
    result = parse_svg_to_diagram(svg)

    assert result.success, result.errors
    assert result.diagram is not None
    assert {"A", "B", "C", "I"} <= set(result.diagram.classifiers)
    assert len(result.diagram.associations) == 2
    assert len(result.diagram.dependencies) == 1
    assert len(result.diagram.generalizations) == 1
    assert len(result.diagram.realizations) == 1
    assert set(result.diagram.positions) == {"A", "B", "C", "I"}
    result.diagram.validate_all()


def test_svg_parser_rejects_svg_without_v3_data_attributes():
    result = parse_svg_to_diagram('<svg xmlns="http://www.w3.org/2000/svg"></svg>')

    assert result.success is False
    assert result.errors


def test_cli_writes_svg_file(tmp_path, require_dot):
    source = tmp_path / "diagram.tdl"
    target = tmp_path / "diagram.svg"
    source.write_text(class_block("A") + class_block("B") + f"{ASSOCIATION} A -- B\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "uml_dsl.tdl_run", str(source), str(target)],
        cwd=source.parent,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert target.exists()
    assert target.read_text(encoding="utf-8").lstrip().startswith("<svg")
