"""
Graphviz pipeline: ClassDiagram -> DOT -> SVG -> enrich data-* attributes.
"""
from __future__ import annotations

import html
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Dict, List, Tuple

from .diagram import ClassDiagram, ClassPosition

PX_PER_INCH = 72
MARGIN = 40
DEFAULT_DOT_PATH = r"C:\Program Files\Graphviz\bin\dot.exe"

from .enums import AggregationKind

def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)

def _q(value: str) -> str:
    """Quote value for DOT ids/strings."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

def _center(pos: ClassPosition) -> tuple[float, float]:
    return pos.x + pos.width / 2, pos.y + pos.height / 2


def _edge_point(from_pos: ClassPosition, to_pos: ClassPosition) -> tuple[float, float]:
    fx, fy = _center(from_pos)
    tx, ty = _center(to_pos)

    dx = tx - fx
    dy = ty - fy

    if abs(dx) > abs(dy):
        if dx > 0:
            return from_pos.x + from_pos.width, fy
        return from_pos.x, fy

    if dy > 0:
        return fx, from_pos.y + from_pos.height

    return fx, from_pos.y

def _dedupe_points(
    points: list[tuple[float, float]],
    eps: float = 0.5,
) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []

    for x, y in points:
        if not result:
            result.append((x, y))
            continue

        px, py = result[-1]
        if abs(px - x) > eps or abs(py - y) > eps:
            result.append((x, y))

    return result


def _box_boundary_towards(
    pos: ClassPosition,
    target: tuple[float, float],
) -> tuple[float, float]:
    cx, cy = _center(pos)
    tx, ty = target

    dx = tx - cx
    dy = ty - cy

    if dx == 0 and dy == 0:
        return cx, cy

    half_w = pos.width / 2
    half_h = pos.height / 2

    if abs(dx) * half_h > abs(dy) * half_w:
        x = pos.x + pos.width if dx > 0 else pos.x
        scale = half_w / abs(dx)
        y = cy + dy * scale
    else:
        y = pos.y + pos.height if dy > 0 else pos.y
        scale = half_h / abs(dy)
        x = cx + dx * scale

    x = max(pos.x, min(pos.x + pos.width, x))
    y = max(pos.y, min(pos.y + pos.height, y))

    return x, y


def _edge_route(
    from_pos: ClassPosition,
    to_pos: ClassPosition,
    route: list[tuple[float, float]] | None = None,
) -> list[tuple[float, float]]:
    if route and len(route) >= 2:
        points = _dedupe_points(route)

        if len(points) >= 2:
            points[0] = _box_boundary_towards(from_pos, points[1])
            points[-1] = _box_boundary_towards(to_pos, points[-2])
            return _dedupe_points(points)

    return [
        _edge_point(from_pos, to_pos),
        _edge_point(to_pos, from_pos),
    ]

def _points_attr(points: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def _path_attr(d: str) -> str:
    return html.escape(d, quote=True)


def _transform_attr(transform: str) -> str:
    return html.escape(transform, quote=True)


def _dot_command() -> str:
    return shutil.which("dot") or DEFAULT_DOT_PATH

def _multiplicity_label_pos(
    point: tuple[float, float],
    other: tuple[float, float],
    text: str,
    distance: float = 12.0,
    side_offset: float = 6.0,
) -> tuple[float, float]:
    dx = other[0] - point[0]
    dy = other[1] - point[1]

    length = max((dx * dx + dy * dy) ** 0.5, 1.0)
    ux = dx / length
    uy = dy / length

    nx = -uy
    ny = ux

    text_w = len(text) * 7.0

    label_x = point[0] + ux * distance + nx * side_offset
    label_y = point[1] + uy * distance + ny * side_offset

    if nx < 0:
        label_x -= text_w

    return label_x, label_y


def _edge_label_pos(points: list[tuple[float, float]]) -> tuple[float, float]:
    mid_idx = len(points) // 2
    if len(points) >= 2:
        x = (points[mid_idx - 1][0] + points[mid_idx][0]) / 2
        y = (points[mid_idx - 1][1] + points[mid_idx][1]) / 2
    else:
        x, y = points[0]

    if len(points) >= 2:
        prev_x, prev_y = points[mid_idx - 1]
        next_x, next_y = points[mid_idx]
        dx = next_x - prev_x
        dy = next_y - prev_y
        if abs(dx) < abs(dy):
            return x + 10, y - 4

    return x + 6, y - 6

def render_association_svg(
    assoc,
    positions: dict[str, ClassPosition],
    route: list[tuple[float, float]] | None = None,
) -> str:
    if not assoc.is_binary():
        return ""

    e1, e2 = assoc.ends

    end1_name = e1.participant.name
    end2_name = e2.participant.name

    p1 = positions.get(end1_name)
    p2 = positions.get(end2_name)

    if p1 is None or p2 is None:
        return ""

    points = _edge_route(p1, p2, route)

    marker_start = ""
    marker_end = ""
    if e1.aggregation == AggregationKind.COMPOSITION:
        marker_start = ' marker-start="url(#diamond-filled)"'
    elif e1.aggregation == AggregationKind.AGGREGATION:
        marker_start = ' marker-start="url(#diamond-empty)"'
    elif e2.aggregation == AggregationKind.COMPOSITION:
        marker_end = ' marker-end="url(#diamond-filled-end)"'
    elif e2.aggregation == AggregationKind.AGGREGATION:
        marker_end = ' marker-end="url(#diamond-empty-end)"'

    mult1 = str(e1.multiplicity) if e1.multiplicity else ""
    mult2 = str(e2.multiplicity) if e2.multiplicity else ""

    show_src_mult = e1.aggregation == AggregationKind.NONE
    show_tgt_mult = e2.aggregation == AggregationKind.NONE

    src_mult_x, src_mult_y = _multiplicity_label_pos(points[0], points[1], mult1)
    tgt_mult_x, tgt_mult_y = _multiplicity_label_pos(points[-1], points[-2], mult2)

    return f"""
<g class="uml-edge"
   data-type="association"
   data-name="{_esc(assoc.name or '')}"
   data-derived="{str(assoc.is_derived).lower()}"
   data-end1-class="{_esc(end1_name)}"
   data-end1-multiplicity="{_esc(mult1)}"
   data-end1-role="{_esc(e1.role or '')}"
   data-end1-navigable="{str(e1.navigable).lower() if e1.navigable is not None else ''}"
   data-end1-aggregation="{_esc(e1.aggregation.value)}"
   data-end2-class="{_esc(end2_name)}"
   data-end2-multiplicity="{_esc(mult2)}"
   data-end2-role="{_esc(e2.role or '')}"
   data-end2-navigable="{str(e2.navigable).lower() if e2.navigable is not None else ''}"
   data-end2-aggregation="{_esc(e2.aggregation.value)}">
  <polyline points="{_points_attr(points)}"
            fill="none"
            stroke="black"
            stroke-width="1.5"{marker_start}{marker_end}/>
  {_render_label(mult1 if show_src_mult else "", src_mult_x, src_mult_y, "uml-multiplicity", background=True)}
  {_render_label(mult2 if show_tgt_mult else "", tgt_mult_x, tgt_mult_y, "uml-multiplicity", background=True)}
</g>
"""

def _render_label(
    text: str,
    x: float,
    y: float,
    cls: str = "",
    background: bool = False,
) -> str:
    if not text:
        return ""
    class_attr = f' class="{cls}"' if cls else ""
    label = (
        f'<text{class_attr} x="{x:.1f}" y="{y:.1f}" '
        f'font-family="Arial" font-size="12" fill="black">{_esc(text)}</text>'
    )
    if not background:
        return label

    width = max(len(text) * 7.0 + 4, 10)
    return (
        f'<g{class_attr}>'
        f'<rect x="{x - 2:.1f}" y="{y - 12:.1f}" width="{width:.1f}" height="15" '
        f'fill="white" opacity="0.85" stroke="none"/>'
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="Arial" font-size="12" fill="black">{_esc(text)}</text>'
        f'</g>'
    )

def render_generalization_svg(
    gen,
    positions: dict[str, ClassPosition],
    route: list[tuple[float, float]] | None = None,
) -> str:
    src = gen.specific.name
    tgt = gen.general.name

    p1 = positions.get(src)
    p2 = positions.get(tgt)

    if p1 is None or p2 is None:
        return ""

    points = _edge_route(p1, p2, route)

    return f"""
<g class="uml-edge"
   data-type="generalization"
   data-src="{_esc(src)}"
   data-tgt="{_esc(tgt)}"
   data-substitutable="{str(gen.is_substitutable).lower()}">
  <polyline points="{_points_attr(points)}"
            fill="none"
            stroke="black"
            stroke-width="1.5"
            marker-end="url(#triangle-empty)"/>
</g>
"""

def render_dependency_svg(
    dep,
    positions: dict[str, ClassPosition],
    route: list[tuple[float, float]] | None = None,
) -> str:
    src = dep.client.name
    tgt = dep.supplier.name

    p1 = positions.get(src)
    p2 = positions.get(tgt)

    if p1 is None or p2 is None:
        return ""

    points = _edge_route(p1, p2, route)

    stereo = dep.stereotype.value if dep.stereotype else ""
    label = f"«{stereo}»" if stereo else ""

    mid_idx = len(points) // 2
    mid_x = (points[mid_idx - 1][0] + points[mid_idx][0]) / 2
    mid_y = (points[mid_idx - 1][1] + points[mid_idx][1]) / 2

    return f"""
<g class="uml-edge"
   data-type="dependency"
   data-src="{_esc(src)}"
   data-tgt="{_esc(tgt)}"
   data-stereotype="{_esc(stereo)}">
  <polyline points="{_points_attr(points)}"
            fill="none"
            stroke="black"
            stroke-width="1.5"
            stroke-dasharray="6,4"
            marker-end="url(#arrow-open)"/>
  {_render_label(label, mid_x + 6, mid_y - 6, "uml-edge-label")}
</g>
"""

def render_realization_svg(
    real,
    positions: dict[str, ClassPosition],
    route: list[tuple[float, float]] | None = None,
) -> str:
    src = real.implementer.name
    tgt = real.interface_.name

    p1 = positions.get(src)
    p2 = positions.get(tgt)

    if p1 is None or p2 is None:
        return ""

    points = _edge_route(p1, p2, route)

    return f"""
<g class="uml-edge"
   data-type="realization"
   data-src="{_esc(src)}"
   data-tgt="{_esc(tgt)}">
  <polyline points="{_points_attr(points)}"
            fill="none"
            stroke="black"
            stroke-width="1.5"
            stroke-dasharray="6,4"
            marker-end="url(#triangle-empty)"/>
</g>
"""

def _node_label(cls) -> str:
    """Build Graphviz record label for UML class."""
    title = cls.name
    if getattr(cls, "is_abstract", False):
        title = f"<I>{html.escape(title)}</I>"
    else:
        title = html.escape(title)

    if getattr(cls, "stereotype", None):
        st = html.escape(cls.stereotype.value)
        title = f"&laquo;{st}&raquo;<BR/>{title}"

    attrs = "<BR ALIGN=\"LEFT\"/>".join(
        html.escape(a.to_text()) for a in getattr(cls, "attributes", [])
    ) or " "
    ops = "<BR ALIGN=\"LEFT\"/>".join(
        html.escape(o.to_text()) for o in getattr(cls, "operations", [])
    ) or " "
    return f"<{title}<BR/>{attrs}<BR/>{ops}>"


def diagram_to_layout_dot(diagram: ClassDiagram):
    node_map = {}
    name_to_node = {}

    lines = [
        "digraph UML {",
        "  graph [rankdir=TB, splines=ortho, nodesep=0.8, ranksep=0.9, pad=0.3];",
        "  node [shape=box, fixedsize=true, label=\"\", style=invis];",
        "  edge [style=invis];",
    ]

    for idx, (name, cls) in enumerate(diagram.classifiers.items()):
        node_id = f"C{idx}"
        node_map[node_id] = name
        name_to_node[name] = node_id

        width_px, height_px = cls.get_box_size()

        lines.append(
            f'  {node_id} [width="{width_px / PX_PER_INCH:.3f}", '
            f'height="{height_px / PX_PER_INCH:.3f}"];'
        )

    for assoc in diagram.associations:
        if not assoc.is_binary():
            continue

        src = assoc.ends[0].participant.name
        tgt = assoc.ends[1].participant.name

        if src in name_to_node and tgt in name_to_node:
            lines.append(f"  {name_to_node[src]} -> {name_to_node[tgt]};")

    for gen in diagram.generalizations:
        src = gen.specific.name
        tgt = gen.general.name

        if src in name_to_node and tgt in name_to_node:
            lines.append(f"  {name_to_node[src]} -> {name_to_node[tgt]};")

    for dep in diagram.dependencies:
        src = dep.client.name
        tgt = dep.supplier.name

        if src in name_to_node and tgt in name_to_node:
            lines.append(f"  {name_to_node[src]} -> {name_to_node[tgt]};")

    for real in diagram.realizations:
        src = real.implementer.name
        tgt = real.interface_.name

        if src in name_to_node and tgt in name_to_node:
            lines.append(f"  {name_to_node[src]} -> {name_to_node[tgt]};")

    lines.append("}")
    return "\n".join(lines), node_map


def _run_dot_to_plain(dot_text: str) -> str:
    try:
        result = subprocess.run(
            [_dot_command(), "-Tplain"],
            input=dot_text.encode("utf-8"),
            capture_output=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Graphviz 'dot' не найден. Установите Graphviz и добавьте dot в PATH."
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"Ошибка Graphviz dot: {stderr}") from exc

    return result.stdout.decode("utf-8", errors="replace")


def _run_dot_to_svg(dot_text: str) -> str:
    try:
        result = subprocess.run(
            [_dot_command(), "-Tsvg"],
            input=dot_text.encode("utf-8"),
            capture_output=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Graphviz 'dot' РЅРµ РЅР°Р№РґРµРЅ. РЈСЃС‚Р°РЅРѕРІРёС‚Рµ Graphviz Рё РґРѕР±Р°РІСЊС‚Рµ dot РІ PATH."
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"РћС€РёР±РєР° Graphviz dot: {stderr}") from exc

    return result.stdout.decode("utf-8", errors="replace")


def _make_edges_visible(dot_text: str) -> str:
    return dot_text.replace(
        "  edge [style=invis];",
        "  edge [color=black, penwidth=1.5, arrowhead=none];",
    )


def _extract_graphviz_svg_paths(svg_text: str) -> tuple[list[str], str, float, float]:
    root = ET.fromstring(svg_text)
    ns = "{http://www.w3.org/2000/svg}"
    graph = next(
        (
            group
            for group in root.findall(f"{ns}g")
            if group.get("class") == "graph"
        ),
        None,
    )

    if graph is None:
        return [], "", 0.0, 0.0

    transform = graph.get("transform", "")
    view_box = [float(value) for value in root.get("viewBox", "0 0 0 0").split()]
    paths: list[str] = []

    for edge in graph.findall(f"{ns}g"):
        if edge.get("class") != "edge":
            continue

        path = edge.find(f"{ns}path")
        if path is not None and path.get("d"):
            paths.append(path.get("d", ""))

    return paths, transform, view_box[2], view_box[3]


def _shift_layout_to_svg_viewbox(
    plain_text: str,
    diagram: ClassDiagram,
    node_map: dict[str, str],
    transform: str,
) -> tuple[
    dict[str, ClassPosition],
    list[tuple[str, str, list[tuple[float, float]]]],
]:
    positions, routes = parse_plain_layout(plain_text, diagram, node_map)
    graph_height = next(
        (
            float(line.split()[3]) * PX_PER_INCH
            for line in plain_text.splitlines()
            if line.startswith("graph ")
        ),
        0.0,
    )

    match = re.search(r"translate\(([-\d.]+)\s+([-\d.]+)\)", transform)
    tx, ty = (float(match.group(1)), float(match.group(2))) if match else (0.0, graph_height)
    dx = tx - MARGIN
    dy = ty - (MARGIN + graph_height)

    shifted_positions = {
        name: ClassPosition(
            classifier_name=name,
            x=pos.x + dx,
            y=pos.y + dy,
            width=pos.width,
            height=pos.height,
        )
        for name, pos in positions.items()
    }
    shifted_routes = [
        (src, tgt, [(x + dx, y + dy) for x, y in points])
        for src, tgt, points in routes
    ]

    return shifted_positions, shifted_routes


def _replace_polyline_with_path(svg: str, path_d: str, transform: str) -> str:
    def replace(match: re.Match[str]) -> str:
        attrs = re.sub(r'\s+points="[^"]*"', "", match.group(1))
        transform_attr = f' transform="{_transform_attr(transform)}"' if transform else ""
        return f'<path d="{_path_attr(path_d)}"{transform_attr}{attrs}/>'

    return re.sub(r"<polyline([^>]*)/>", replace, svg, count=1, flags=re.S)

def parse_plain_layout(
    plain_text: str,
    diagram: ClassDiagram,
    node_map: dict[str, str],
):
    positions: dict[str, ClassPosition] = {}
    edge_routes: list[tuple[str, str, list[tuple[float, float]]]] = []

    graph_height_px = 0.0

    for line in plain_text.splitlines():
        parts = line.split()

        if not parts:
            continue

        if parts[0] == "graph":
            graph_height_px = float(parts[3]) * PX_PER_INCH

        elif parts[0] == "node":
            node_id = parts[1]
            class_name = node_map[node_id]
            cls = diagram.classifiers[class_name]

            center_x_px = float(parts[2]) * PX_PER_INCH
            center_y_px = float(parts[3]) * PX_PER_INCH

            width_px, height_px = cls.get_box_size()

            x = MARGIN + center_x_px - width_px / 2
            y = MARGIN + graph_height_px - center_y_px - height_px / 2

            positions[class_name] = ClassPosition(
                classifier_name=class_name,
                x=x,
                y=y,
                width=width_px,
                height=height_px,
            )

        elif parts[0] == "edge":
            src_name = node_map[parts[1]]
            tgt_name = node_map[parts[2]]

            point_count = int(parts[3])
            raw_points = parts[4 : 4 + point_count * 2]

            points = []

            for i in range(0, len(raw_points), 2):
                x = MARGIN + float(raw_points[i]) * PX_PER_INCH
                y = MARGIN + graph_height_px - float(raw_points[i + 1]) * PX_PER_INCH
                points.append((x, y))

            edge_routes.append((src_name, tgt_name, points))

    return positions, edge_routes

def diagram_to_graphviz_svg(diagram: ClassDiagram) -> str:
    dot_text, node_map = diagram_to_layout_dot(diagram)
    visible_dot_text = _make_edges_visible(dot_text)
    graphviz_svg = _run_dot_to_svg(visible_dot_text)
    graphviz_paths, graphviz_transform, graphviz_width, graphviz_height = (
        _extract_graphviz_svg_paths(graphviz_svg)
    )
    plain_text = _run_dot_to_plain(visible_dot_text)

    positions, edge_routes = _shift_layout_to_svg_viewbox(
        plain_text,
        diagram,
        node_map,
        graphviz_transform,
    )

    edge_route_map: dict[tuple[str, str], list[list[tuple[float, float]]]] = {}

    for src, tgt, points in edge_routes:
        edge_route_map.setdefault((src, tgt), []).append(points)

    diagram.positions = positions

    width = graphviz_width or max((p.x + p.width for p in positions.values()), default=0) + MARGIN
    height = graphviz_height or max((p.y + p.height for p in positions.values()), default=0) + MARGIN

    SVG_DEFS = """
    <defs>
      <marker id="diamond-empty" markerWidth="10" markerHeight="10" refX="1" refY="5" orient="auto" markerUnits="strokeWidth">
        <path d="M 1 5 L 5 1 L 9 5 L 5 9 Z" fill="white" stroke="black" stroke-width="1"/>
      </marker>

      <marker id="diamond-filled" markerWidth="10" markerHeight="10" refX="1" refY="5" orient="auto" markerUnits="strokeWidth">
        <path d="M 1 5 L 5 1 L 9 5 L 5 9 Z" fill="black" stroke="black" stroke-width="1"/>
      </marker>

      <marker id="diamond-empty-end" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="strokeWidth">
        <path d="M 1 5 L 5 1 L 9 5 L 5 9 Z" fill="white" stroke="black" stroke-width="1"/>
      </marker>

      <marker id="diamond-filled-end" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="strokeWidth">
        <path d="M 1 5 L 5 1 L 9 5 L 5 9 Z" fill="black" stroke="black" stroke-width="1"/>
      </marker>

      <marker id="arrow-open" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto" markerUnits="strokeWidth">
        <path d="M 2 2 L 10 6 L 2 10" fill="none" stroke="black" stroke-width="1.5"/>
      </marker>

      <marker id="triangle-empty" markerWidth="16" markerHeight="16" refX="14" refY="8" orient="auto" markerUnits="strokeWidth">
        <path d="M 14 8 L 2 2 L 2 14 Z" fill="white" stroke="black" stroke-width="1.5"/>
      </marker>
    </defs>
    """

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}">',
        SVG_DEFS,
    ]
    edge_parts: list[str] = []

    for assoc in diagram.associations:
        if assoc.is_binary():
            src = assoc.ends[0].participant.name
            tgt = assoc.ends[1].participant.name
            routes = edge_route_map.get((src, tgt), [])
            route = routes.pop(0) if routes else None
        else:
            route = None

        edge_parts.append(render_association_svg(assoc, positions, route))

    for gen in diagram.generalizations:
        src = gen.specific.name
        tgt = gen.general.name
        routes = edge_route_map.get((src, tgt), [])
        route = routes.pop(0) if routes else None

        edge_parts.append(render_generalization_svg(gen, positions, route))

    for dep in diagram.dependencies:
        src = dep.client.name
        tgt = dep.supplier.name
        routes = edge_route_map.get((src, tgt), [])
        route = routes.pop(0) if routes else None

        edge_parts.append(render_dependency_svg(dep, positions, route))

    for real in diagram.realizations:
        src = real.implementer.name
        tgt = real.interface_.name
        routes = edge_route_map.get((src, tgt), [])
        route = routes.pop(0) if routes else None

        edge_parts.append(render_realization_svg(real, positions, route))

    if len(graphviz_paths) == len(edge_parts):
        edge_parts = [
            _replace_polyline_with_path(edge_svg, path_d, graphviz_transform)
            for edge_svg, path_d in zip(edge_parts, graphviz_paths)
        ]

    parts.extend(edge_parts)

    for name, cls in diagram.classifiers.items():
        pos = positions[name]
        parts.append(cls.to_svg(pos.x, pos.y, class_id=name))

    parts.append("</svg>")

    return "\n".join(parts)
