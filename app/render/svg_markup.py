"""Shared CAD SVG helpers. Black line, white fill. 1 user unit = 1 cm."""
from __future__ import annotations

import xml.etree.ElementTree as ET

STROKE = "#000000"
FILL = "#ffffff"
FONT = "Arial, Helvetica, sans-serif"
OUTER_STROKE = "1.2"
INNER_STROKE = "0.6"
THIN_STROKE = "0.4"
PAD = 48.0


def fmt(n: float) -> str:
    return f"{round(float(n), 2):.2f}"


def new_svg(width: float, height: float, title: str) -> ET.Element:
    svg = ET.Element("svg")
    svg.set("xmlns", "http://www.w3.org/2000/svg")
    svg.set("viewBox", f"0 0 {fmt(width)} {fmt(height)}")
    svg.set("width", fmt(width))
    svg.set("height", fmt(height))
    svg.set("data-title", title)
    bg = ET.SubElement(svg, "rect")
    bg.set("x", "0")
    bg.set("y", "0")
    bg.set("width", fmt(width))
    bg.set("height", fmt(height))
    bg.set("fill", FILL)
    bg.set("stroke", "none")
    return svg


def add_rect(
    parent: ET.Element,
    x: float,
    y: float,
    w: float,
    h: float,
    stroke: str = INNER_STROKE,
    fill: str = FILL,
    extra: dict[str, str] | None = None,
) -> ET.Element:
    el = ET.SubElement(parent, "rect")
    el.set("x", fmt(x))
    el.set("y", fmt(y))
    el.set("width", fmt(w))
    el.set("height", fmt(h))
    el.set("fill", fill)
    el.set("stroke", STROKE)
    el.set("stroke-width", stroke)
    if extra:
        for key, value in extra.items():
            el.set(key, value)
    return el


def add_line(
    parent: ET.Element,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    stroke: str = INNER_STROKE,
) -> ET.Element:
    el = ET.SubElement(parent, "line")
    el.set("x1", fmt(x1))
    el.set("y1", fmt(y1))
    el.set("x2", fmt(x2))
    el.set("y2", fmt(y2))
    el.set("stroke", STROKE)
    el.set("stroke-width", stroke)
    return el


def add_polygon(
    parent: ET.Element,
    points: list[tuple[float, float]],
    extra: dict[str, str] | None = None,
) -> ET.Element:
    el = ET.SubElement(parent, "polygon")
    el.set("points", " ".join(f"{fmt(x)},{fmt(y)}" for x, y in points))
    el.set("fill", FILL)
    el.set("stroke", STROKE)
    el.set("stroke-width", OUTER_STROKE)
    el.set("fill-rule", "nonzero")
    if extra:
        for key, value in extra.items():
            el.set(key, value)
    return el


def add_text(
    parent: ET.Element,
    x: float,
    y: float,
    text: str,
    size: float = 8.0,
    anchor: str = "middle",
) -> ET.Element:
    el = ET.SubElement(parent, "text")
    el.set("x", fmt(x))
    el.set("y", fmt(y))
    el.set("fill", STROKE)
    el.set("font-family", FONT)
    el.set("font-size", fmt(size))
    el.set("text-anchor", anchor)
    el.text = text
    return el


def serialize(root: ET.Element) -> str:
    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"
