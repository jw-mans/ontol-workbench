from __future__ import annotations

from uml_dsl.planarity import analyze
from uml_dsl.tdl_run import tdl_to_svg_analyzed

from tests.helpers import ASSOCIATION, GENERALIZATION, build, class_block, complete_graph_tdl


def test_planar_graph_gets_positions():
    tdl = (
        class_block("A")
        + class_block("B")
        + class_block("C")
        + f"{GENERALIZATION} B -> A\n"
        + f"{GENERALIZATION} C -> B\n"
    )

    result = analyze(build(tdl))

    assert result.is_planar is True
    assert set(result.positions) == {"A", "B", "C"}


def test_k5_non_planar_obstruction_is_reported():
    result = analyze(build(complete_graph_tdl("ABCDE")))

    assert result.is_planar is False
    assert result.kind == "K5"
    assert set("ABCDE") <= set(result.labels)
    assert result.warning() and "K5" in result.warning()


def test_k33_non_planar_obstruction_is_reported():
    classes = "".join(class_block(name) for name in "ABCDEF")
    edges = "".join(f"{ASSOCIATION} {left} -- {right}\n" for left in "ABC" for right in "DEF")

    result = analyze(build(classes + edges))

    assert result.is_planar is False
    assert result.kind == "K3,3"
    assert set("ABCDEF") <= set(result.labels)


def test_multiple_obstructions_are_returned_separately():
    result = analyze(build(complete_graph_tdl("ABCDE") + complete_graph_tdl("FGHIJ")))

    assert result.is_planar is False
    assert len(result.obstructions) == 2
    assert {obstruction.kind for obstruction in result.obstructions} == {"K5"}
    assert {frozenset(obstruction.labels) for obstruction in result.obstructions} == {
        frozenset("ABCDE"),
        frozenset("FGHIJ"),
    }


def test_analyzed_render_returns_planarity_payload_for_non_planar_graph(require_dot):
    svg, warnings, planarity = tdl_to_svg_analyzed(complete_graph_tdl("ABCDE"))

    assert svg.lstrip().startswith("<svg")
    assert warnings == []
    assert planarity is not None
    assert planarity["kind"] == "K5"
    assert planarity["count"] == 1
    assert planarity["subgraphs"][0]["kind"] == "K5"


def test_analyzed_render_uses_planar_layout_without_warning(require_dot):
    tdl = class_block("A") + class_block("B") + f"{GENERALIZATION} B -> A\n"

    svg, warnings, planarity = tdl_to_svg_analyzed(tdl)

    assert svg.lstrip().startswith("<svg")
    assert warnings == []
    assert planarity is None
    assert 'data-theme="light"' in svg
