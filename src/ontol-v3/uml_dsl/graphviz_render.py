"""
Graphviz pipeline: ClassDiagram -> DOT -> SVG -> enrich data-* attributes.
"""
from __future__ import annotations

import html
import math
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from .diagram import ClassDiagram, ClassPosition

PX_PER_INCH = 72
MARGIN = 40
DEFAULT_DOT_PATH = r"C:\Program Files\Graphviz\bin\dot.exe"
DEFAULT_SVG_THEME = "light"
SVG_STYLE_DIR = Path(__file__).resolve().parent / "styles"
EDGE_COLOR = "#181818"
EDGE_STROKE_WIDTH = 1.0
EDGE_DASH_ARRAY = "7,7"
EDGE_LABEL_FONT = "sans-serif"
EDGE_LABEL_FONT_SIZE = 13
MULTIPLICITY_ENDPOINT_OFFSET = 16.0
MULTIPLICITY_LINE_GAP = 2.5
MULTIPLICITY_HORIZONTAL_GAP = 8.0
MULTIPLICITY_HORIZONTAL_BASELINE = 16.0
MULTIPLICITY_BASELINE_SHIFT = 4.5

from .enums import AggregationKind

def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)

def _q(value: str) -> str:
    """Quote value for DOT ids/strings."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _normalize_svg_theme(theme: str | None) -> str:
    candidate = (theme or DEFAULT_SVG_THEME).strip().lower()
    if candidate == "default":
        return DEFAULT_SVG_THEME
    if not re.fullmatch(r"[a-z0-9_-]+", candidate):
        return DEFAULT_SVG_THEME
    return candidate


def available_svg_themes() -> list[str]:
    if not SVG_STYLE_DIR.exists():
        return [DEFAULT_SVG_THEME]

    themes = [
        path.stem
        for path in SVG_STYLE_DIR.glob("*.css")
        if re.fullmatch(r"[a-z0-9_-]+", path.stem)
    ]
    themes = [DEFAULT_SVG_THEME] + sorted(
        theme for theme in themes if theme != DEFAULT_SVG_THEME
    )
    return themes or [DEFAULT_SVG_THEME]


def _load_svg_style(theme: str | None) -> tuple[str, str]:
    resolved_theme = _normalize_svg_theme(theme)
    style_path = SVG_STYLE_DIR / f"{resolved_theme}.css"

    if not style_path.exists():
        resolved_theme = DEFAULT_SVG_THEME
        style_path = SVG_STYLE_DIR / f"{resolved_theme}.css"

    if not style_path.exists():
        return resolved_theme, ""

    css = style_path.read_text(encoding="utf-8").replace("]]>", "]]\\>")
    return resolved_theme, (
        f'<style id="uml-theme-{_esc(resolved_theme)}" type="text/css"><![CDATA[\n'
        f"{css}\n"
        f"]]></style>"
    )

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


PathSegment = tuple[str, tuple[tuple[float, float], ...]]


def _parse_transform_values(raw: str) -> list[float]:
    return [
        float(value)
        for value in re.split(r"[\s,]+", raw.strip())
        if value
    ]


def _apply_svg_transform(
    point: tuple[float, float],
    transform: str,
) -> tuple[float, float]:
    x, y = point

    for name, raw_values in re.findall(r"(\w+)\(([^)]*)\)", transform):
        values = _parse_transform_values(raw_values)

        if name == "translate":
            x += values[0] if values else 0.0
            y += values[1] if len(values) > 1 else 0.0
        elif name == "scale":
            sx = values[0] if values else 1.0
            sy = values[1] if len(values) > 1 else sx
            x *= sx
            y *= sy
        elif name == "rotate":
            angle = math.radians(values[0] if values else 0.0)
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            x, y = x * cos_a - y * sin_a, x * sin_a + y * cos_a

    return x, y


def _tokenize_path(path_d: str) -> list[str]:
    return re.findall(
        r"[MmLlHhVvCcZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?",
        path_d,
    )


def _parse_path(path_d: str) -> tuple[tuple[float, float], list[PathSegment]]:
    tokens = _tokenize_path(path_d)
    idx = 0
    command = ""
    current = (0.0, 0.0)
    start = (0.0, 0.0)
    subpath_start = (0.0, 0.0)
    segments: list[PathSegment] = []

    def has_number() -> bool:
        return idx < len(tokens) and not re.fullmatch(r"[A-Za-z]", tokens[idx])

    def number() -> float:
        nonlocal idx
        value = float(tokens[idx])
        idx += 1
        return value

    def point(relative: bool = False) -> tuple[float, float]:
        x = number()
        y = number()
        if relative:
            return current[0] + x, current[1] + y
        return x, y

    while idx < len(tokens):
        if re.fullmatch(r"[A-Za-z]", tokens[idx]):
            command = tokens[idx]
            idx += 1

        relative = command.islower()
        upper = command.upper()

        if upper == "M":
            current = point(relative)
            if not segments:
                start = current
            subpath_start = current
            command = "l" if relative else "L"

            while has_number():
                next_point = point(relative)
                segments.append(("L", (current, next_point)))
                current = next_point

        elif upper == "L":
            while has_number():
                next_point = point(relative)
                segments.append(("L", (current, next_point)))
                current = next_point

        elif upper == "H":
            while has_number():
                x = number()
                next_point = (current[0] + x, current[1]) if relative else (x, current[1])
                segments.append(("L", (current, next_point)))
                current = next_point

        elif upper == "V":
            while has_number():
                y = number()
                next_point = (current[0], current[1] + y) if relative else (current[0], y)
                segments.append(("L", (current, next_point)))
                current = next_point

        elif upper == "C":
            while has_number():
                p1 = point(relative)
                p2 = point(relative)
                p3 = point(relative)
                segments.append(("C", (current, p1, p2, p3)))
                current = p3

        elif upper == "Z":
            segments.append(("L", (current, subpath_start)))
            current = subpath_start
            command = ""

        else:
            break

    return start, segments


def _transform_path_d(path_d: str, transform: str) -> str:
    start, segments = _parse_path(path_d)
    start = _apply_svg_transform(start, transform)
    parts = [f"M{start[0]:.1f},{start[1]:.1f}"]

    for command, points in segments:
        transformed = [_apply_svg_transform(point, transform) for point in points]

        if command == "L":
            _, end = transformed
            parts.append(f"L{end[0]:.1f},{end[1]:.1f}")
        elif command == "C":
            _, p1, p2, end = transformed
            parts.append(
                f"C{p1[0]:.1f},{p1[1]:.1f} "
                f"{p2[0]:.1f},{p2[1]:.1f} "
                f"{end[0]:.1f},{end[1]:.1f}"
            )

    return " ".join(parts)


def _cubic_point(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    t: float,
) -> tuple[float, float]:
    mt = 1.0 - t
    x = (
        mt * mt * mt * p0[0]
        + 3 * mt * mt * t * p1[0]
        + 3 * mt * t * t * p2[0]
        + t * t * t * p3[0]
    )
    y = (
        mt * mt * mt * p0[1]
        + 3 * mt * mt * t * p1[1]
        + 3 * mt * t * t * p2[1]
        + t * t * t * p3[1]
    )
    return x, y


def _flatten_path(
    path_d: str,
    curve_steps: int = 24,
) -> list[tuple[float, float]]:
    start, segments = _parse_path(path_d)
    points = [start]

    for command, segment_points in segments:
        if command == "L":
            points.append(segment_points[-1])
        elif command == "C":
            p0, p1, p2, p3 = segment_points
            for step in range(1, curve_steps + 1):
                points.append(_cubic_point(p0, p1, p2, p3, step / curve_steps))

    return _dedupe_points(points, eps=0.1)


def _point_on_path(
    path_d: str,
    at_start: bool,
    offset: float,
) -> tuple[tuple[float, float], tuple[float, float]]:
    points = _flatten_path(path_d)

    if len(points) < 2:
        point = points[0] if points else (0.0, 0.0)
        return point, (1.0, 0.0)

    walk_points = points if at_start else list(reversed(points))
    remaining = offset

    for idx in range(1, len(walk_points)):
        x1, y1 = walk_points[idx - 1]
        x2, y2 = walk_points[idx]
        dx = x2 - x1
        dy = y2 - y1
        length = (dx * dx + dy * dy) ** 0.5

        if length <= 0.1:
            continue

        if remaining <= length:
            ratio = remaining / length
            point = (x1 + dx * ratio, y1 + dy * ratio)
            tangent = (dx / length, dy / length)
            return point, tangent

        remaining -= length

    x1, y1 = walk_points[-2]
    x2, y2 = walk_points[-1]
    return walk_points[-1], _unit_vector((x1, y1), (x2, y2))


def _path_length(path_d: str) -> float:
    return _polyline_length(_flatten_path(path_d))


def _label_text_width(text: str) -> float:
    if not text:
        return 0.0

    if len(text) == 1:
        return 7.0

    return max(len(text) * 5.0, 7.0)


def _min_path_x_in_y_band(
    points: list[tuple[float, float]],
    top: float,
    bottom: float,
    fallback: float,
) -> float:
    values: list[float] = []

    for idx, (x, y) in enumerate(points):
        if top <= y <= bottom:
            values.append(x)

        if idx == 0:
            continue

        prev_x, prev_y = points[idx - 1]
        if max(prev_y, y) < top or min(prev_y, y) > bottom:
            continue

        if abs(y - prev_y) < 0.1:
            values.extend((prev_x, x))
            continue

        for boundary_y in (top, bottom):
            if min(prev_y, y) <= boundary_y <= max(prev_y, y):
                ratio = (boundary_y - prev_y) / (y - prev_y)
                values.append(prev_x + (x - prev_x) * ratio)

    return min(values) if values else fallback


def _multiplicity_label_pos_on_path(
    path_d: str,
    at_start: bool,
    text: str,
    along_offset: float = MULTIPLICITY_ENDPOINT_OFFSET,
) -> tuple[float, float]:
    path_points = _flatten_path(path_d)
    local_along_offset = min(
        along_offset,
        max(10.0, _polyline_length(path_points) * 0.35),
    )
    point, tangent = _point_on_path(path_d, at_start, local_along_offset)
    tx, ty = tangent
    text_w = _label_text_width(text)
    endpoint = path_points[0 if at_start else -1]

    if abs(tx) > abs(ty) * 4.0:
        if tx >= 0:
            x = endpoint[0] + MULTIPLICITY_HORIZONTAL_GAP
        else:
            x = endpoint[0] - text_w - MULTIPLICITY_HORIZONTAL_GAP

        return x, endpoint[1] + MULTIPLICITY_HORIZONTAL_BASELINE

    baseline_y = point[1] + MULTIPLICITY_BASELINE_SHIFT
    edge_x = _min_path_x_in_y_band(
        path_points,
        baseline_y - EDGE_LABEL_FONT_SIZE,
        baseline_y + 2.0,
        min(point[0], endpoint[0]),
    )

    return (
        edge_x - text_w - MULTIPLICITY_LINE_GAP,
        baseline_y,
    )

def _unit_vector(
    point: tuple[float, float],
    other: tuple[float, float],
) -> tuple[float, float]:
    dx = other[0] - point[0]
    dy = other[1] - point[1]

    length = max((dx * dx + dy * dy) ** 0.5, 1.0)
    return dx / length, dy / length


def _multiplicity_side(
    point: tuple[float, float],
    other: tuple[float, float],
) -> tuple[float, float]:
    dx = other[0] - point[0]
    dy = other[1] - point[1]

    if abs(dx) >= abs(dy):
        return 0.0, -1.0

    return -1.0, 0.0


def _polyline_length(points: list[tuple[float, float]]) -> float:
    if len(points) < 2:
        return 0.0

    length = 0.0
    for idx in range(1, len(points)):
        dx = points[idx][0] - points[idx - 1][0]
        dy = points[idx][1] - points[idx - 1][1]
        length += (dx * dx + dy * dy) ** 0.5

    return length


def _multiplicity_side_segment(
    points: list[tuple[float, float]],
    at_start: bool,
    fallback_point: tuple[float, float],
    fallback_other: tuple[float, float],
) -> tuple[tuple[float, float], tuple[float, float]]:
    if len(points) < 3:
        return fallback_point, fallback_other

    if at_start:
        return points[1], points[2]

    return points[-2], points[-3]


def _multiplicity_label_pos(
    points: list[tuple[float, float]],
    at_start: bool,
    text: str,
    along_offset: float = 28.0,
    side_offset: float = 30.0,
) -> tuple[float, float]:
    if not points:
        return 0.0, 0.0

    if len(points) == 1:
        point = points[0]
        other = (point[0] + 1.0, point[1])
    elif at_start:
        point = points[0]
        other = points[1]
    else:
        point = points[-1]
        other = points[-2]

    ux, uy = _unit_vector(point, other)
    side_point, side_other = _multiplicity_side_segment(
        points,
        at_start,
        point,
        other,
    )
    sx, sy = _multiplicity_side(side_point, side_other)
    side_dx = side_other[0] - side_point[0]
    side_dy = side_other[1] - side_point[1]
    text_w = max(len(text) * 7.0, 8.0)
    local_along_offset = min(
        along_offset,
        max(10.0, _polyline_length(points) * 0.18),
    )

    base_x = point[0] + ux * local_along_offset
    base_y = point[1] + uy * local_along_offset
    anchor_x = side_point[0] if abs(side_dx) < abs(side_dy) else base_x
    anchor_y = side_point[1] if abs(side_dy) < abs(side_dx) else base_y

    if sx < 0:
        return anchor_x - side_offset - text_w / 2, base_y + 4

    if sx > 0:
        return anchor_x + side_offset - text_w / 2, base_y + 4

    if sy < 0:
        return base_x - text_w / 2, anchor_y - side_offset

    return base_x - text_w / 2, anchor_y + side_offset + 12


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


def _edge_shape_svg(
    points: list[tuple[float, float]],
    path_d: str | None,
    attrs: str,
) -> str:
    if path_d:
        return f'<path class="uml-edge-line" d="{_path_attr(path_d)}"{attrs}/>'

    return f'<polyline class="uml-edge-line" points="{_points_attr(points)}"{attrs}/>'


def _path_label_pos(path_d: str) -> tuple[float, float]:
    point, tangent = _point_on_path(path_d, True, _polyline_length(_flatten_path(path_d)) / 2)
    tx, ty = tangent

    if abs(tx) < abs(ty):
        return point[0] + 10, point[1] - 4

    return point[0] + 6, point[1] - 6


def render_association_svg(
    assoc,
    positions: dict[str, ClassPosition],
    route: list[tuple[float, float]] | None = None,
    path_d: str | None = None,
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

    if path_d:
        src_mult_x, src_mult_y = _multiplicity_label_pos_on_path(path_d, True, mult1)
        tgt_mult_x, tgt_mult_y = _multiplicity_label_pos_on_path(path_d, False, mult2)
    else:
        src_mult_x, src_mult_y = _multiplicity_label_pos(points, True, mult1)
        tgt_mult_x, tgt_mult_y = _multiplicity_label_pos(points, False, mult2)

    edge_shape = _edge_shape_svg(
        points,
        path_d,
        f' fill="none" stroke="{EDGE_COLOR}" stroke-width="{EDGE_STROKE_WIDTH:.1f}"{marker_start}{marker_end}',
    )

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
  {edge_shape}
  {_render_label(mult1 if show_src_mult else "", src_mult_x, src_mult_y, "uml-multiplicity")}
  {_render_label(mult2 if show_tgt_mult else "", tgt_mult_x, tgt_mult_y, "uml-multiplicity")}
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
        f'font-family="{EDGE_LABEL_FONT}" font-size="{EDGE_LABEL_FONT_SIZE}" '
        f'fill="black">{_esc(text)}</text>'
    )
    if not background:
        return label

    width = max(_label_text_width(text) + 4, 10)
    return (
        f'<g{class_attr}>'
        f'<rect x="{x - 2:.1f}" y="{y - 12:.1f}" width="{width:.1f}" height="15" '
        f'fill="white" opacity="0.85" stroke="none"/>'
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{EDGE_LABEL_FONT}" '
        f'font-size="{EDGE_LABEL_FONT_SIZE}" fill="black">{_esc(text)}</text>'
        f'</g>'
    )

def render_generalization_svg(
    gen,
    positions: dict[str, ClassPosition],
    route: list[tuple[float, float]] | None = None,
    path_d: str | None = None,
) -> str:
    src = gen.specific.name
    tgt = gen.general.name

    p1 = positions.get(src)
    p2 = positions.get(tgt)

    if p1 is None or p2 is None:
        return ""

    points = _edge_route(p1, p2, route)

    edge_shape = _edge_shape_svg(
        points,
        path_d,
        f' fill="none" stroke="{EDGE_COLOR}" stroke-width="{EDGE_STROKE_WIDTH:.1f}" marker-end="url(#triangle-empty)"',
    )

    return f"""
<g class="uml-edge"
   data-type="generalization"
   data-src="{_esc(src)}"
   data-tgt="{_esc(tgt)}"
   data-substitutable="{str(gen.is_substitutable).lower()}">
  {edge_shape}
</g>
"""

def render_dependency_svg(
    dep,
    positions: dict[str, ClassPosition],
    route: list[tuple[float, float]] | None = None,
    path_d: str | None = None,
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

    if path_d:
        mid_x, mid_y = _path_label_pos(path_d)
    else:
        mid_idx = len(points) // 2
        mid_x = (points[mid_idx - 1][0] + points[mid_idx][0]) / 2
        mid_y = (points[mid_idx - 1][1] + points[mid_idx][1]) / 2

    edge_shape = _edge_shape_svg(
        points,
        path_d,
        (
            f' fill="none" stroke="{EDGE_COLOR}" stroke-width="{EDGE_STROKE_WIDTH:.1f}" '
            f'stroke-dasharray="{EDGE_DASH_ARRAY}" marker-end="url(#arrow-filled)"'
        ),
    )

    return f"""
<g class="uml-edge"
   data-type="dependency"
   data-src="{_esc(src)}"
   data-tgt="{_esc(tgt)}"
   data-stereotype="{_esc(stereo)}">
  {edge_shape}
  {_render_label(label, mid_x + 6, mid_y - 6, "uml-edge-label")}
</g>
"""

def render_realization_svg(
    real,
    positions: dict[str, ClassPosition],
    route: list[tuple[float, float]] | None = None,
    path_d: str | None = None,
) -> str:
    src = real.implementer.name
    tgt = real.interface_.name

    p1 = positions.get(src)
    p2 = positions.get(tgt)

    if p1 is None or p2 is None:
        return ""

    points = _edge_route(p1, p2, route)

    edge_shape = _edge_shape_svg(
        points,
        path_d,
        (
            f' fill="none" stroke="{EDGE_COLOR}" stroke-width="{EDGE_STROKE_WIDTH:.1f}" '
            f'stroke-dasharray="{EDGE_DASH_ARRAY}" marker-end="url(#triangle-empty)"'
        ),
    )

    return f"""
<g class="uml-edge"
   data-type="realization"
   data-src="{_esc(src)}"
   data-tgt="{_esc(tgt)}">
  {edge_shape}
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
        "  graph [rankdir=TB, splines=true, nodesep=0.8, ranksep=0.9, pad=0.3];",
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
        f'  edge [color="{EDGE_COLOR}", penwidth={EDGE_STROKE_WIDTH:.1f}, arrowhead=none];',
    )


def _extract_graphviz_svg_paths(svg_text: str) -> tuple[
    list[tuple[str, str, str]],
    str,
    float,
    float,
]:
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
    paths: list[tuple[str, str, str]] = []

    for edge in graph.findall(f"{ns}g"):
        if edge.get("class") != "edge":
            continue

        path = edge.find(f"{ns}path")
        title = edge.find(f"{ns}title")
        if path is None or not path.get("d") or title is None or not title.text:
            continue

        if "->" not in title.text:
            continue

        src_id, tgt_id = [part.strip() for part in title.text.split("->", 1)]
        paths.append((src_id, tgt_id, path.get("d", "")))

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

def diagram_to_graphviz_svg(diagram: ClassDiagram, theme: str = DEFAULT_SVG_THEME) -> str:
    resolved_theme, svg_style = _load_svg_style(theme)
    edge_route_map: dict[tuple[str, str], list[list[tuple[float, float]]]] = {}
    graphviz_path_map: dict[tuple[str, str], list[str]] = {}

    if getattr(diagram, "manual_layout", False):
        positions = diagram.positions
        width = max((p.x + p.width for p in positions.values()), default=0) + MARGIN
        height = max((p.y + p.height for p in positions.values()), default=0) + MARGIN
    else:
        dot_text, node_map = diagram_to_layout_dot(diagram)
        visible_dot_text = _make_edges_visible(dot_text)
        graphviz_svg = _run_dot_to_svg(visible_dot_text)
        graphviz_edges, graphviz_transform, graphviz_width, graphviz_height = (
            _extract_graphviz_svg_paths(graphviz_svg)
        )
        plain_text = _run_dot_to_plain(visible_dot_text)

        positions, edge_routes = _shift_layout_to_svg_viewbox(
            plain_text,
            diagram,
            node_map,
            graphviz_transform,
        )

        for src, tgt, points in edge_routes:
            edge_route_map.setdefault((src, tgt), []).append(points)

        for src_id, tgt_id, path_d in graphviz_edges:
            src = node_map.get(src_id)
            tgt = node_map.get(tgt_id)
            if src and tgt:
                graphviz_path_map.setdefault((src, tgt), []).append(
                    _transform_path_d(path_d, graphviz_transform)
                )

        diagram.positions = positions

        width = graphviz_width or max((p.x + p.width for p in positions.values()), default=0) + MARGIN
        height = graphviz_height or max((p.y + p.height for p in positions.values()), default=0) + MARGIN

    SVG_DEFS = """
    <defs>
      <linearGradient id="uml-yellow-title-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="#f0c955"/>
        <stop offset="50%" stop-color="#ffebc2"/>
        <stop offset="100%" stop-color="#f0c955"/>
      </linearGradient>

      <linearGradient id="uml-yellow-section-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="#f5d56b"/>
        <stop offset="50%" stop-color="#fff1cf"/>
        <stop offset="100%" stop-color="#f0c955"/>
      </linearGradient>

      <marker id="diamond-empty" markerWidth="12" markerHeight="8" viewBox="0 0 12 8" refX="0" refY="4" orient="auto" markerUnits="userSpaceOnUse">
        <path class="uml-marker uml-marker-hollow" d="M 0 4 L 6 0 L 12 4 L 6 8 Z" fill="white" stroke="#181818" stroke-width="1"/>
      </marker>

      <marker id="diamond-filled" markerWidth="12" markerHeight="8" viewBox="0 0 12 8" refX="0" refY="4" orient="auto" markerUnits="userSpaceOnUse">
        <path class="uml-marker uml-marker-filled" d="M 0 4 L 6 0 L 12 4 L 6 8 Z" fill="#181818" stroke="#181818" stroke-width="1"/>
      </marker>

      <marker id="diamond-empty-end" markerWidth="12" markerHeight="8" viewBox="0 0 12 8" refX="12" refY="4" orient="auto" markerUnits="userSpaceOnUse">
        <path class="uml-marker uml-marker-hollow" d="M 0 4 L 6 0 L 12 4 L 6 8 Z" fill="white" stroke="#181818" stroke-width="1"/>
      </marker>

      <marker id="diamond-filled-end" markerWidth="12" markerHeight="8" viewBox="0 0 12 8" refX="12" refY="4" orient="auto" markerUnits="userSpaceOnUse">
        <path class="uml-marker uml-marker-filled" d="M 0 4 L 6 0 L 12 4 L 6 8 Z" fill="#181818" stroke="#181818" stroke-width="1"/>
      </marker>

      <marker id="arrow-filled" markerWidth="9" markerHeight="8" viewBox="0 0 9 8" refX="9" refY="4" orient="auto" markerUnits="userSpaceOnUse">
        <path class="uml-marker uml-marker-filled" d="M 9 4 L 0 0 L 4 4 L 0 8 Z" fill="#181818" stroke="#181818" stroke-width="1"/>
      </marker>

      <marker id="triangle-empty" markerWidth="18" markerHeight="12" viewBox="0 0 18 12" refX="18" refY="6" orient="auto" markerUnits="userSpaceOnUse">
        <path class="uml-marker uml-marker-hollow" d="M 18 6 L 0 0 L 0 12 Z" fill="white" stroke="#181818" stroke-width="1"/>
      </marker>
    </defs>
    """

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'class="uml-diagram" data-theme="{_esc(resolved_theme)}">',
        SVG_DEFS,
        svg_style,
    ]
    edge_parts: list[str] = []

    for assoc in diagram.associations:
        if assoc.is_binary():
            src = assoc.ends[0].participant.name
            tgt = assoc.ends[1].participant.name
            routes = edge_route_map.get((src, tgt), [])
            route = routes.pop(0) if routes else None
            paths = graphviz_path_map.get((src, tgt), [])
            path_d = paths.pop(0) if paths else None
        else:
            route = None
            path_d = None

        edge_svg = render_association_svg(assoc, positions, route, path_d)
        edge_parts.append(edge_svg)

    for gen in diagram.generalizations:
        src = gen.specific.name
        tgt = gen.general.name
        routes = edge_route_map.get((src, tgt), [])
        route = routes.pop(0) if routes else None
        paths = graphviz_path_map.get((src, tgt), [])
        path_d = paths.pop(0) if paths else None

        edge_svg = render_generalization_svg(gen, positions, route, path_d)
        edge_parts.append(edge_svg)

    for dep in diagram.dependencies:
        src = dep.client.name
        tgt = dep.supplier.name
        routes = edge_route_map.get((src, tgt), [])
        route = routes.pop(0) if routes else None
        paths = graphviz_path_map.get((src, tgt), [])
        path_d = paths.pop(0) if paths else None

        edge_svg = render_dependency_svg(dep, positions, route, path_d)
        edge_parts.append(edge_svg)

    for real in diagram.realizations:
        src = real.implementer.name
        tgt = real.interface_.name
        routes = edge_route_map.get((src, tgt), [])
        route = routes.pop(0) if routes else None
        paths = graphviz_path_map.get((src, tgt), [])
        path_d = paths.pop(0) if paths else None

        edge_svg = render_realization_svg(real, positions, route, path_d)
        edge_parts.append(edge_svg)

    parts.extend(edge_parts)

    for name, cls in diagram.classifiers.items():
        pos = positions[name]
        parts.append(cls.to_svg(pos.x, pos.y, class_id=name))

    parts.append("</svg>")

    return "\n".join(parts)
