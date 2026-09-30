#!/usr/bin/env python3
"""Build the retained title, single-player pause and loading screens.

These documents are the first stock-composition screens of the retained
interface (docs/dev/ui/retained-screens.md). Every measured value below cites
docs/dev/ui-visual-design.md: section 9 (screen reference), Appendix B.1/B.2
(textures and band silhouettes), section 4 (tokens) and section 8 (motion).

Stock measurements are source units (u) on the 640x480 canvas. The documents
declare a 720 dp view-height canvas, so 1 u = 1.5 dp at every resolution and
the 4:3 canvas is the central 960x720 dp; aspect expansion widens the flat
spans of the framing bands and the backdrop, never the composition.

The generated files are canonical sources. Re-run this script after editing
it; do not hand-edit its outputs.

    python tools/ui/build_retained_screens.py [--check]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAK0 = ROOT / "content" / "baseoq4" / "pak0"
OUTPUTS = {
    "title": PAK0 / "guis" / "menu" / "title.q4ui",
    "pause": PAK0 / "guis" / "menu" / "pause.q4ui",
    "loading": PAK0 / "guis" / "loading" / "loading.q4ui",
}

U = 1.5            # dp per stock source unit at the 720 dp canvas
CANVAS_W = 960.0   # the 4:3 canvas in dp
FAR = 1400.0       # flat spans reach this far past the view edges (21:9 and 32:9 views, band travel)

# Section 4 tokens.
def rgb(hex_colour: str, alpha: float = 1.0) -> list[float]:
    value = hex_colour.lstrip("#")
    return [round(int(value[i:i + 2], 16) / 255, 4) for i in (0, 2, 4)] + [alpha]

OLIVE = "#8B964B"
MARKER = "#909A49"
ORANGE = "#E38900"
VALUE = "#FFBE23"
RAIL_DARK = "#CCCC51"
RAIL_CARD = "#A0A040"
GLOW = "#616F26"
GLOW_MODAL = "#454E1B"   # popup_bg plateau (Appendix B.1)
RIM = "#626934"
PLINTH = "#3E4A21"
PROGRESS = "#E06C00"
PICTURE = "#414624"
OBJECTIVE_HEAD = "#FF8000"
LOAD_SPILL = "#181D0A"
DOTS = "#1C2613"

# Accelerate-then-decelerate, the stock `accel(a, d)` profile with a = d
# (section 8): quadratic ease in-out.
ACCEL = [0.455, 0.03, 0.515, 0.955]
EASE_OUT = [0.16, 1, 0.3, 1]


# ---------------------------------------------------------------- typed values

def length(value: float, unit: str = "dp") -> dict:
    return {"type": "length", "value": round(value, 3), "unit": unit}

def colour(value: list[float]) -> dict:
    return {"type": "color", "value": value}

def keyword(value: str) -> dict:
    return {"type": "keyword", "value": value}

def number(value: float) -> dict:
    return {"type": "number", "value": value}

def font(name: str) -> dict:
    return {"type": "font", "value": name}

def text(key: str) -> dict:
    return {"type": "text", "value": key}

def image(source: str) -> dict:
    return {"type": "image", "value": source}

def transform(tx: float = 0, ty: float = 0, sx: float = 1, sy: float = 1) -> dict:
    return {"type": "transform", "unit": "dp", "value": [round(tx, 3), round(ty, 3), sx, sy, 0]}


def absolute(left=None, top=None, width=None, height=None, right=None, bottom=None) -> dict:
    props = {"position": keyword("absolute")}
    for name, value in (("left", left), ("top", top), ("width", width), ("height", height),
                        ("right", right), ("bottom", bottom)):
        if value is None:
            continue
        props[name] = value if isinstance(value, dict) else length(value)
    return props

FULL = {**absolute(left=0, top=0), "width": length(100, "%"), "height": length(100, "%")}


# -------------------------------------------------------------------- geometry

def vx(u: float, extra: float = 0.0) -> dict:
    """An x on the 4:3 canvas, in a node spanning the whole view."""
    return {"fraction": 0.5, "dp": round(-CANVAS_W / 2 + U * u + extra, 3)}

def edge(side: int, extra: float = FAR) -> dict:
    """The view's leading (0) or trailing (1) edge, pushed further out."""
    return {"fraction": side, "dp": -extra if side == 0 else extra}

def point(x, y) -> list:
    def one(value):
        return round(value, 3) if isinstance(value, (int, float)) else value
    return [one(x), one(y)]

def path(ident: str, points: list, *, fill=None, stroke=None, closed=True, blend=None,
         fill_rule=None) -> dict:
    commands = []
    for index, (x, y) in enumerate(points):
        commands.append({"id": f"p{index}", "op": "move" if index == 0 else "line", "points": [point(x, y)]})
    if closed:
        commands.append({"id": "close", "op": "close"})
    result = {"id": ident, "commands": commands}
    if fill_rule:
        result["fillRule"] = fill_rule
    if fill is not None:
        result["fill"] = fill
    if stroke is not None:
        result["stroke"] = stroke
    if blend:
        result["blend"] = blend
    return result

def solid(value: list[float]) -> dict:
    return {"type": "solid", "color": colour(value)}

def linear(start, end, stops) -> dict:
    return {"type": "linear", "from": point(*start), "to": point(*end),
            "stops": [{"at": at, "color": colour(value)} for at, value in stops]}

def stroke(paint: dict, width: float, *, minimum: float = 1, join: str = "miter", cap: str = "butt") -> dict:
    return {"paint": paint, "widthDp": round(width, 3), "minimumPixels": minimum, "join": join, "cap": cap}


# ----------------------------------------------------------------------- nodes

def group(ident: str, props: dict, children=(), **extra) -> dict:
    node = {"id": ident, "type": "group", "properties": props}
    if children:
        node["children"] = list(children)
    node.update(extra)
    return node

def vector(ident: str, props: dict, paths: list, children=(), **extra) -> dict:
    node = {"id": ident, "type": "vector", "properties": props, "paths": paths}
    if children:
        node["children"] = list(children)
    node.update(extra)
    return node

def label(ident: str, key: str, props: dict) -> dict:
    return {"id": ident, "type": "text", "properties": {"text": text(key), **props}}

def picture(ident: str, source: str, props: dict, fit: str = "cover") -> dict:
    return {"id": ident, "type": "image", "properties": {"image": image(source), "image-fit": keyword(fit), **props}}


def typeface(face: str, size: float, line: float, tint: list[float], **more) -> dict:
    props = {"font-family": font(face), "font-size": length(size), "line-height": length(line), "color": colour(tint)}
    props.update(more)
    return props


# ------------------------------------------------------------------- timelines

class Timelines:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, ident: str, duration: float, tracks: list, *, iterations: int | None = None,
            essential: bool | None = None) -> str:
        timeline = {"id": ident, "durationMs": duration, "tracks": tracks}
        if iterations is not None:
            timeline["iterations"] = iterations
        if essential is not None:
            timeline["essential"] = essential
        self.items.append(timeline)
        return ident


def track(node: str, prop: str, keys: list) -> dict:
    """keys: (ms, typed value[, easing of the interval starting here])."""
    result = []
    for key in keys:
        entry = {"atMs": key[0], "value": key[1]}
        if len(key) > 2 and key[2] is not None:
            entry["easing"] = key[2]
        result.append(entry)
    return {"node": node, "property": prop, "keys": result}


# --------------------------------------------------------------- framing bands

# Appendix B.2 inner edges on the canvas, home state (band-local plus origin).
TOP_HOME = [(-297.9, 89.7), (-283.7, 103.8), (30.7, 103.8), (40.9, 94.7), (76.6, 94.7), (85.8, 103.8),
            (127.6, 103.8), (137.8, 94.7), (172.5, 94.7), (181.7, 103.8), (223.5, 103.8), (233.7, 94.7),
            (268.4, 94.7), (277.6, 103.8), (315.4, 103.8), (352.1, 68.5)]
BOTTOM_HOME = [(-232.7, 421.5), (-222.5, 430.6), (-28.6, 430.6), (2.1, 400.4), (344.9, 400.4),
               (389.8, 443.7), (582.7, 443.7), (591.9, 434.6)]
# Page dock minus home dock (Appendix B.2): top (-77,-63) - (-400,0), bottom (-26,386) - (-399,351).
TOP_TO_PAGE = (323 * U, -63 * U)
BOTTOM_TO_PAGE = (373 * U, 35 * U)


def band_edge(points: list, lead_y: float, trail_y: float) -> list:
    inner = [(edge(0), U * lead_y)]
    inner += [(vx(x), U * y) for x, y in points]
    inner.append((edge(1), U * trail_y))
    return inner


def rim(edge_points: list) -> list:
    """marine.rim: 0.37 falling to nothing across 19 u outside the inner edge,
    measured from the edge (section 6). Ten nested strokes of equal alpha
    accumulate a near-linear falloff; the opaque band fill hides their inner halves."""
    paths = []
    steps = 10
    alpha = 1 - (1 - 0.37) ** (1 / steps)
    for index in range(steps, 0, -1):
        width = 2 * 19 * U * index / steps
        paths.append(path(f"rim-{index}", edge_points, closed=False,
                          stroke=stroke(solid(rgb(RIM, round(alpha, 4))), width, minimum=0, join="round")))
    return paths


def framing_bands(prefix: str) -> list:
    top_edge = band_edge(TOP_HOME, 89.7, 68.5)
    bottom_edge = band_edge(BOTTOM_HOME, 421.5, 434.6)
    top_fill = [(edge(1), -400)] + [(edge(0), -400)] + top_edge
    bottom_fill = bottom_edge + [(edge(1), U * 480 + 400), (edge(0), U * 480 + 400)]
    top = vector(f"{prefix}-top", {**FULL, "transform": transform()},
                 rim(top_edge) + [path("band", top_fill, fill=solid([0, 0, 0, 1]))])
    bottom = vector(f"{prefix}-bottom", {**FULL, "transform": transform()},
                    rim(bottom_edge) + [path("band", bottom_fill, fill=solid([0, 0, 0, 1]))])
    return [top, bottom]


# --------------------------------------------------------------------- backdrop

def grid_path(opacity: float = 0.04) -> dict:
    """The `+` reticle grid: 13 u crosses on a 30 u pitch (section 2, trait 1).
    It covers views up to 21:9 (-240 to 880 u), the side-screen cap of section
    14.4; wider views keep the backdrop and bands but not the faint grid."""
    commands = []
    count = 0
    arm = 6.5 * U
    for column in range(-8, 29):
        for row in range(0, 16):
            cx = vx(15 + 30 * column)
            cy = U * (15 + 30 * row)
            for (ax, ay), (bx, by) in (((-arm, 0), (arm, 0)), ((0, -arm), (0, arm))):
                commands.append({"id": f"m{count}", "op": "move", "points": [[{"fraction": 0.5, "dp": round(cx["dp"] + ax, 3)}, round(cy + ay, 3)]]})
                commands.append({"id": f"l{count}", "op": "line", "points": [[{"fraction": 0.5, "dp": round(cx["dp"] + bx, 3)}, round(cy + by, 3)]]})
                count += 1
    return {"id": "crosses", "commands": commands,
            "stroke": stroke(solid([1, 1, 1, opacity]), 1.0, minimum=1)}


def lit_field(prefix: str, peak: float) -> list:
    """Vignette, additive light band and reticle grid of the Marine menus."""
    vignette = vector(f"{prefix}-vignette", dict(FULL), [path("shade", [(0, 0), ({"fraction": 1}, 0), ({"fraction": 1}, {"fraction": 1}), (0, {"fraction": 1})],
        fill=linear((0, 0), (0, {"fraction": 1}), [(0, [0, 0, 0, 0.97]), (0.3, [0, 0, 0, 0]), (0.7, [0, 0, 0, 0]), (1, [0, 0, 0, 0.97])]))])
    light = vector(f"{prefix}-light", dict(FULL), [path("band", [(0, 0), ({"fraction": 1}, 0), ({"fraction": 1}, {"fraction": 1}), (0, {"fraction": 1})],
        fill=linear((0, 0), (0, {"fraction": 1}), [(0, rgb(GLOW, 0)), (0.1, rgb(GLOW, 0)), (0.5, rgb(GLOW, peak)), (0.9, rgb(GLOW, 0)), (1, rgb(GLOW, 0))]),
        blend="additive")])
    grid = vector(f"{prefix}-grid", dict(FULL), [grid_path()])
    return [vignette, light, grid]


# -------------------------------------------------------------------- controls

def marker_path(ident: str, x: float, y: float, size: float, tint: list[float]) -> dict:
    """The upper-trailing triangle marker (section 2, trait 5)."""
    return path(ident, [(x, y), (x + size, y), (x + size, y + size)], fill=solid(tint))


class Document:
    def __init__(self, ident: str):
        self.ident = ident
        self.timelines = Timelines()
        self.state: dict = {}
        self.actions: dict = {}
        self.events: dict = {}
        self.bindings: list = []

    def bind(self, ident: str, node: str, prop: str, value) -> None:
        self.bindings.append({"id": ident, "node": node, "property": prop, "value": value})

    def session(self, action: str, command: str) -> str:
        self.actions[action] = {"operation": "session.menu", "arguments": {"command": command}}
        return action

    def states(self, control: str, tracks: dict) -> dict:
        """Button feedback timelines. `tracks` maps state -> [(node, prop, value)].
        Hover and focus respond at once (hover.enter 0 ms, focus 80 ms); every
        return to rest is linear over 300 ms (hover.leave); press insets 1 dp
        over 60 ms (section 8)."""
        durations = {"default": 300, "hover": 60, "focus": 80, "pressed": 60, "disabled": 150}
        ids = {}
        for state, duration in durations.items():
            ident = f"{control}.{state}"
            keys = []
            for node, prop, value in tracks[state]:
                ease = None if state == "default" else EASE_OUT
                keys.append(track(node, prop, [(0, value, ease), (duration, value)]))
            self.timelines.add(ident, duration, keys)
            ids[state] = ident
        return ids

    def build(self, root: dict, extras: dict | None = None) -> dict:
        result = {"format": "openq4-ui", "version": 1, "id": self.ident, "canvas": {"height": 720}}
        if self.state:
            result["state"] = self.state
        if self.actions:
            result["actions"] = self.actions
        if self.events:
            result["events"] = self.events
        if self.bindings:
            result["bindings"] = self.bindings
        result["timelines"] = self.timelines.items
        result["root"] = root
        if extras:
            result.update(extras)
        return result


NAV_LEAD = 900.0  # a navigation button starts this far left of the canvas, past any view's leading edge


def navigation_plate(doc: Document, ident: str, key: str, *, action: str | None = None,
                     event: str | None = None, detail: dict | None = None) -> dict:
    """A dark navigation plate that bleeds off the leading edge (section 9):
    b1_dark drawn at 413x52 u on a 30 u pitch, its visible band rows 16-45 of
    64, opaque to 44 %, half at 62 %, gone by 88 % of the width (Appendix B.1);
    the corner marker at 32 u and a Marine 24 dp label at 44 u. The whole
    30 u pitch is the target, from the view's leading edge to 357 u. `detail`
    is the item's message-line explanation, shown while it has hover or focus."""
    lead = NAV_LEAD
    width = lead + 357 * U
    x0 = lead                                     # canvas x = 0 in button coordinates
    fade = [(0, [0, 0, 0, 1]), (0.44, [0, 0, 0, 1]), (0.62, [0, 0, 0, 0.5]), (0.88, [0, 0, 0, 0]), (1, [0, 0, 0, 0])]
    rail = [(0, rgb(RAIL_DARK)), (0.44, rgb(RAIL_DARK)), (0.62, rgb(RAIL_DARK, 0.5)), (0.88, rgb(RAIL_DARK, 0)), (1, rgb(RAIL_DARK, 0))]
    # Rows are 30 u windows centred on b1_dark's visible band (215-239.4 u for
    # the first row, drawn at 202 u): the band sits 2.8-27.2 u into its window.
    top = U * 2.8
    bottom = U * 27.2
    span = 413 * U
    plate = vector(f"{ident}-plate", {**absolute(left=0, top=0, width=width, height=45), "opacity": number(0.4)}, [
        path("fill", [(0, top), (x0 + span, top), (x0 + span, bottom), (0, bottom)],
             fill=linear((x0, 0), (x0 + span, 0), fade)),
        path("rail", [(0, bottom - 0.75), (x0 + span, bottom - 0.75)], closed=False,
             stroke=stroke(linear((x0, 0), (x0 + span, 0), rail), 1.5)),
    ])
    focus = vector(f"{ident}-focus", {**absolute(left=0, top=0, width=width, height=45), "opacity": number(0)}, [
        path("inset", [(0, bottom - 3.2), (x0 + 348, bottom - 3.2)], closed=False,
             stroke=stroke(solid(rgb(ORANGE)), 1.2)),
        # Focus light: a soft additive marine.glow beside the rail (section 13.8).
        path("light", [(x0 + 20, top - 2), (x0 + 70, top - 2), (x0 + 70, bottom + 2), (x0 + 20, bottom + 2)],
             fill=linear((x0 + 20, 0), (x0 + 70, 0), [(0, rgb(GLOW, 0)), (0.5, rgb(GLOW, 0.5)), (1, rgb(GLOW, 0))]), blend="additive"),
    ])
    # The corner marker's solid triangle: 35-41 u across, 11.8 u into the row.
    marker_rest = vector(f"{ident}-marker", {**absolute(left=0, top=0, width=width, height=45), "opacity": number(0.4)}, [
        marker_path("mark", x0 + U * 35, U * 11.8, U * 6, rgb(MARKER))])
    marker_hot = vector(f"{ident}-marker-hot", {**absolute(left=0, top=0, width=width, height=45), "opacity": number(0)}, [
        marker_path("mark", x0 + U * 35, U * 11.8, U * 6, rgb(ORANGE))])
    text_node = label(f"{ident}-label", key, {
        **absolute(left=x0 + U * 44, top=top, width=U * 314, height=bottom - top),
        **typeface("marine", 24, bottom - top, [1, 1, 1, 0.8]), "white-space": keyword("nowrap"),
        "transform": transform()})
    parts = [plate, focus, marker_rest, marker_hot, text_node]
    detail_id = None
    if detail is not None:
        detail_id = detail["id"]
        parts.append(detail)
    lit, rest = number(1), number(0)
    def with_detail(tracks, shown):
        return tracks + ([(detail_id, "opacity", lit if shown else rest)] if detail_id else [])
    ids = doc.states(ident, {
        "default": with_detail([(f"{ident}-plate", "opacity", number(0.4)), (f"{ident}-marker", "opacity", number(0.4)),
                                (f"{ident}-marker-hot", "opacity", number(0)), (f"{ident}-focus", "opacity", number(0)),
                                (f"{ident}-label", "color", colour([1, 1, 1, 0.8])), (f"{ident}-label", "transform", transform())], False),
        "hover": with_detail([(f"{ident}-plate", "opacity", number(0.8)), (f"{ident}-marker", "opacity", number(0)),
                              (f"{ident}-marker-hot", "opacity", number(1)), (f"{ident}-focus", "opacity", number(0)),
                              (f"{ident}-label", "color", colour(rgb(ORANGE))), (f"{ident}-label", "transform", transform(sx=1.03, sy=1.03))], True),
        "focus": with_detail([(f"{ident}-plate", "opacity", number(0.8)), (f"{ident}-marker", "opacity", number(0)),
                              (f"{ident}-marker-hot", "opacity", number(1)), (f"{ident}-focus", "opacity", number(1)),
                              (f"{ident}-label", "color", colour(rgb(ORANGE))), (f"{ident}-label", "transform", transform(sx=1.03, sy=1.03))], True),
        "pressed": with_detail([(f"{ident}-plate", "opacity", number(1)), (f"{ident}-marker", "opacity", number(0)),
                                (f"{ident}-marker-hot", "opacity", number(1)), (f"{ident}-focus", "opacity", number(1)),
                                (f"{ident}-label", "color", colour(rgb(ORANGE))), (f"{ident}-label", "transform", transform(tx=1, ty=1, sx=1.03, sy=1.03))], True),
        "disabled": with_detail([(f"{ident}-plate", "opacity", number(0.4)), (f"{ident}-marker", "opacity", number(0.4)),
                                 (f"{ident}-marker-hot", "opacity", number(0)), (f"{ident}-focus", "opacity", number(0)),
                                 (f"{ident}-label", "color", colour([1, 1, 1, 0.4])), (f"{ident}-label", "transform", transform())], False),
    })
    control = {"role": "button", "label": key, "states": ids}
    if action:
        control["action"] = action
    else:
        control["event"] = event
    return group(ident, {"position": keyword("relative"), "display": keyword("block"),
                         "margin-left": length(-lead), "width": length(width), "height": length(30 * U)},
                 parts, control=control)


def message_line(ident: str, offset_u: float, children: list) -> dict:
    """The stock message-of-the-day slot at 44,364 u (section 13.7), placed
    inside a navigation button so its hover and focus can show it. It never
    takes the pointer: only the plate is the button's target."""
    return group(ident, {**absolute(left=NAV_LEAD + U * 44, top=U * offset_u, width=U * 433, height=U * 33),
                         "opacity": number(0), "pointer-events": keyword("none")}, children)


def link(doc: Document, ident: str, key: str, *, action: str | None = None, event: str | None = None) -> dict:
    """A secondary link on the plinth (section 9): Marine 16 dp at 0.50 behind
    a 4.5 u marker at 0.40; hover and focus turn both orange."""
    marker = vector(f"{ident}-marker", {**absolute(left=0, top=0, width=U * 7, height=U * 17), "opacity": number(0.4)}, [
        marker_path("mark", 0, U * 7.25, U * 4.5, rgb(MARKER))])
    hot = vector(f"{ident}-marker-hot", {**absolute(left=0, top=0, width=U * 7, height=U * 17), "opacity": number(0)}, [
        marker_path("mark", 0, U * 7.25, U * 4.5, rgb(ORANGE))])
    text_node = label(f"{ident}-label", key, {"position": keyword("relative"), "display": keyword("block"),
        "margin-left": length(U * 7), **typeface("marine", 16, U * 17, [1, 1, 1, 0.5]), "white-space": keyword("nowrap")})
    ids = doc.states(ident, {
        "default": [(f"{ident}-marker", "opacity", number(0.4)), (f"{ident}-marker-hot", "opacity", number(0)), (f"{ident}-label", "color", colour([1, 1, 1, 0.5]))],
        "hover": [(f"{ident}-marker", "opacity", number(0)), (f"{ident}-marker-hot", "opacity", number(1)), (f"{ident}-label", "color", colour(rgb(ORANGE)))],
        "focus": [(f"{ident}-marker", "opacity", number(0)), (f"{ident}-marker-hot", "opacity", number(1)), (f"{ident}-label", "color", colour(rgb(ORANGE)))],
        "pressed": [(f"{ident}-marker", "opacity", number(0)), (f"{ident}-marker-hot", "opacity", number(1)), (f"{ident}-label", "color", colour([1, 1, 1, 1]))],
        "disabled": [(f"{ident}-marker", "opacity", number(0.4)), (f"{ident}-marker-hot", "opacity", number(0)), (f"{ident}-label", "color", colour([1, 1, 1, 0.25]))],
    })
    control = {"role": "button", "label": key, "states": ids}
    if action:
        control["action"] = action
    else:
        control["event"] = event
    return group(ident, {"position": keyword("relative"), "display": keyword("block"),
                         "height": length(U * 17), "margin-right": length(U * 14)},
                 [marker, hot, text_node], control=control)


def plinth(doc: Document, links: list) -> dict:
    """The link plinth (bg2, Appendix B.1): 24-361 u by 403-422 u, a 45-degree
    lower-leading cut and a parallel trailing cut, marine.plinth at 0.30."""
    left, right, top, bottom = 24.0, 361.2, 403.3, 422.1
    width, height = U * (right - left), U * (bottom - top)
    lead_cut, trail_cut = U * 11.2, U * 19.2
    shape = path("plinth", [(0, 0), (width - trail_cut, 0), (width, height), (lead_cut, height), (0, height - lead_cut)],
                 fill=solid(rgb(PLINTH, 0.3)))
    row = group("plinth-links", {**absolute(left=U * (32 - left), top=U * -0.3, height=U * 17),
                                  "display": keyword("flex"), "flex-direction": keyword("row"),
                                  "align-items": keyword("flex-start")}, links)
    return vector("plinth", absolute(left=U * left, top=U * top, width=width, height=height), [shape], [row])


def action_plate(doc: Document, ident: str, key: str, left: float, top: float, *, action: str | None = None,
                 event: str | None = None, width: float = 180) -> dict:
    """An action button (section 6): a light plate, 35 dp visible in a 45 dp
    target, a 20 dp lower-leading cut, rails on the leading edge, cut and
    bottom, fill 0.49 fading from 33 % to nothing; 8 dp marker, Marine 20 dp."""
    band_top, band_bottom = 5.0, 40.0
    cut = 20.0
    fill = [(0, rgb(OLIVE, 0.49)), (0.33, rgb(OLIVE, 0.49)), (1, rgb(OLIVE, 0))]
    rail = [(0, rgb(OLIVE)), (0.33, rgb(OLIVE)), (1, rgb(OLIVE, 0))]
    plate = vector(f"{ident}-plate", {**absolute(left=0, top=0, width=width, height=45), "opacity": number(0.4)}, [
        path("fill", [(0, band_top), (width, band_top), (width, band_bottom), (cut, band_bottom), (0, band_bottom - cut)],
             fill=linear((0, 0), (width, 0), fill)),
        path("rail", [(0.75, band_top), (0.75, band_bottom - cut), (cut, band_bottom - 0.75), (width, band_bottom - 0.75)],
             closed=False, stroke=stroke(linear((0, 0), (width, 0), rail), 1.5)),
    ])
    focus = vector(f"{ident}-focus", {**absolute(left=0, top=0, width=width, height=45), "opacity": number(0)}, [
        path("inset", [(3.5, band_top + 3), (3.5, band_bottom - cut + 1.5), (cut + 1.5, band_bottom - 3.5), (width - 20, band_bottom - 3.5)],
             closed=False, stroke=stroke(solid(rgb(ORANGE)), 1.2))])
    marker_rest = vector(f"{ident}-marker", {**absolute(left=14, top=14, width=8, height=8), "opacity": number(0.4)}, [
        marker_path("mark", 0, 0, 8, rgb(MARKER))])
    marker_hot = vector(f"{ident}-marker-hot", {**absolute(left=14, top=14, width=8, height=8), "opacity": number(0)}, [
        marker_path("mark", 0, 0, 8, rgb(ORANGE))])
    text_node = label(f"{ident}-label", key, {**absolute(left=26, top=0, width=width - 30, height=45),
        **typeface("marine", 20, 45, [1, 1, 1, 0.8]), "white-space": keyword("nowrap"), "transform": transform()})
    ids = doc.states(ident, {
        "default": [(f"{ident}-plate", "opacity", number(0.4)), (f"{ident}-marker", "opacity", number(0.4)), (f"{ident}-marker-hot", "opacity", number(0)),
                    (f"{ident}-focus", "opacity", number(0)), (f"{ident}-label", "color", colour([1, 1, 1, 0.8])), (f"{ident}-label", "transform", transform())],
        "hover": [(f"{ident}-plate", "opacity", number(0.8)), (f"{ident}-marker", "opacity", number(0)), (f"{ident}-marker-hot", "opacity", number(1)),
                  (f"{ident}-focus", "opacity", number(0)), (f"{ident}-label", "color", colour(rgb(ORANGE))), (f"{ident}-label", "transform", transform(sx=1.03, sy=1.03))],
        "focus": [(f"{ident}-plate", "opacity", number(0.8)), (f"{ident}-marker", "opacity", number(0)), (f"{ident}-marker-hot", "opacity", number(1)),
                  (f"{ident}-focus", "opacity", number(1)), (f"{ident}-label", "color", colour(rgb(ORANGE))), (f"{ident}-label", "transform", transform(sx=1.03, sy=1.03))],
        "pressed": [(f"{ident}-plate", "opacity", number(1)), (f"{ident}-marker", "opacity", number(0)), (f"{ident}-marker-hot", "opacity", number(1)),
                    (f"{ident}-focus", "opacity", number(1)), (f"{ident}-label", "color", colour(rgb(ORANGE))), (f"{ident}-label", "transform", transform(tx=1, ty=1, sx=1.03, sy=1.03))],
        "disabled": [(f"{ident}-plate", "opacity", number(0.4)), (f"{ident}-marker", "opacity", number(0.4)), (f"{ident}-marker-hot", "opacity", number(0)),
                     (f"{ident}-focus", "opacity", number(0)), (f"{ident}-label", "color", colour([1, 1, 1, 0.4])), (f"{ident}-label", "transform", transform())],
    })
    control = {"role": "button", "label": key, "states": ids}
    if action:
        control["action"] = action
    else:
        control["event"] = event
    return group(ident, absolute(left=left, top=top, width=width, height=45), [plate, focus, marker_rest, marker_hot, text_node], control=control)


def confirmation(doc: Document, ident: str, title_key: str, body_key: str, yes_action: str) -> dict:
    """A stock confirmation modal (section 6): the marine.scrim, an additive
    glow column exactly as wide as the dialog, and a 480 dp black 0.70
    silhouette with a leading tooth, a recessed title slot, a raised trailing
    section and a 38 dp lower-leading chamfer; YES leads, NO trails."""
    visible = f"{ident}.visible"
    doc.state[visible] = {"type": "boolean", "initial": False}
    hide = f"{ident}Hide"
    doc.events[f"{ident}Show"] = [{"op": "setState", "values": {visible: True}}]
    doc.events[hide] = [{"op": "setState", "values": {visible: False}}]
    width, height = 480.0, 204.0          # 320x136 u
    left = (CANVAS_W - width) / 2
    top = U * 155                           # 17 u above centre
    slot_open, slot_depth, tooth, chamfer = 0.73 * width, 17.0, 6.0, 38.0
    silhouette = path("frame", [(0, 0), (tooth, 0), (tooth + slot_depth, slot_depth), (slot_open - slot_depth, slot_depth),
                                (slot_open, 0), (width, 0), (width, height), (chamfer, height), (0, height - chamfer)],
                      fill=solid([0, 0, 0, 0.7]))
    glow_top, glow_bottom = -U * 87, height + U * 108
    glow = vector(f"{ident}-glow", absolute(left=0, top=glow_top, width=width, height=glow_bottom - glow_top), [
        path("column", [(0, 0), ({"fraction": 1}, 0), ({"fraction": 1}, {"fraction": 1}), (0, {"fraction": 1})],
             fill=linear((0, 0), (0, {"fraction": 1}), [(0, rgb(GLOW_MODAL, 0)), (0.28, rgb(GLOW_MODAL, 0.5)), (0.41, rgb(GLOW_MODAL, 0.9)),
                                                        (0.58, rgb(GLOW_MODAL, 0.9)), (0.72, rgb(GLOW_MODAL, 0.5)), (1, rgb(GLOW_MODAL, 0))]),
             blend="additive")])
    frame = vector(f"{ident}-frame", absolute(left=0, top=0, width=width, height=height), [silhouette])
    title = label(f"{ident}-title", title_key, {**absolute(left=tooth + slot_depth + 4, top=-6, width=slot_open - 2 * slot_depth - 12, height=24),
        **typeface("marine", 20, 24, [1, 1, 1, 0.9]), "letter-spacing": length(-0.075, "em"), "white-space": keyword("nowrap")})
    body = label(f"{ident}-body", body_key, {**absolute(left=33, top=40, width=width - 66, height=90),
        **typeface("lowpixel", 17, 22, [1, 1, 1, 0.8])})
    yes = action_plate(doc, f"{ident}_yes", "#str_200157", 30, height - 16 - 45, action=yes_action)
    no = action_plate(doc, f"{ident}_no", "#str_200158", width - 33 - 180, height - 16 - 45, event=hide)
    dialog = group(f"{ident}-dialog", absolute(left=left, top=top, width=width, height=height), [glow, frame, title, body, yes, no])
    stage = group(f"{ident}-stage", {**absolute(top=0, width=CANVAS_W, height=720), "left": length(50, "%"),
                                     "margin-left": length(-CANVAS_W / 2)}, [dialog])
    node = group(ident, {**FULL, "display": keyword("none"), "background-color": colour([0, 0, 0, 0.94])}, [stage],
                 modal={"initialFocus": f"{ident}_no", "back": hide})
    doc.bind(f"{ident}.display", ident, "display", {"op": "select", "args": [{"state": visible}, "block", "none"]})
    return node


def prompt_bar(doc: Document, prompts: list) -> dict:
    """The prompt bar in the bottom band's raised trailing section (section
    13.4): a keycap plate with a 45-degree cut per prompt, then its verb."""
    items = []
    for key_name, verb in prompts:
        cap = vector(f"prompt-{verb[5:]}-cap", {"position": keyword("relative"), "display": keyword("block"),
                                                "height": length(22), "margin-right": length(6), "padding-left": length(8),
                                                "padding-right": length(8)}, [
            path("cap", [(0, 0), ({"fraction": 1}, 0), ({"fraction": 1}, {"fraction": 1}), (6, {"fraction": 1}), (0, {"fraction": 1, "dp": -6})],
                 fill=solid([1, 1, 1, 0.85]))],
            [label(f"prompt-{verb[5:]}-key", key_name, {"position": keyword("relative"), "display": keyword("block"),
                    **typeface("lowpixel", 13, 22, [0.04, 0.05, 0.035, 1]), "white-space": keyword("nowrap")})])
        verb_node = label(f"prompt-{verb[5:]}-verb", verb, {"position": keyword("relative"), "display": keyword("block"),
            "margin-right": length(22), **typeface("marine", 14, 22, [1, 1, 1, 0.8]), "white-space": keyword("nowrap")})
        items += [cap, verb_node]
    return group("prompts", {**absolute(top=U * 447, height=22, right=U * 12),
                             "display": keyword("flex"), "flex-direction": keyword("row"), "align-items": keyword("center")}, items)


# --------------------------------------------------------------- choreography

def band_motion(doc: Document, prefix: str, content: str, extra_home: list) -> None:
    """Section 8 stock choreography, sampled every presented frame:
    open        menu.fade from black over 250 ms, bands already home;
    depart      content out over 250 ms; from 50 ms frame.dock and
                screen.depart, both accel(250, 250) over 500 ms;
    departPopup content out over 150 ms, bands stay home;
    returnHome  bands from their page dock home over 500 ms accel(250, 250);
                the home content, already in place, fades in at 500 ms (150 ms)."""
    top, bottom = f"{prefix}-top", f"{prefix}-bottom"
    home, page_top, page_bottom = transform(), transform(*TOP_TO_PAGE), transform(*BOTTOM_TO_PAGE)
    lights = [(node, prop, lit, dark) for node, prop, lit, dark in extra_home]
    doc.timelines.add("open", 250, [
        track("fade", "background-color", [(0, colour([0, 0, 0, 1])), (250, colour([0, 0, 0, 0]))]),
        track(content, "opacity", [(0, number(1)), (250, number(1))]),
        track(content, "transform", [(0, transform()), (250, transform())]),
        track(top, "transform", [(0, home), (250, home)]),
        track(bottom, "transform", [(0, home), (250, home)]),
    ] + [track(node, prop, [(0, lit), (250, lit)]) for node, prop, lit, dark in lights])
    doc.timelines.add("depart", 550, [
        track(content, "opacity", [(0, number(1)), (250, number(0)), (550, number(0))]),
        track(content, "transform", [(0, transform()), (50, transform(), ACCEL), (550, transform(640 * U, 0))]),
        track(top, "transform", [(0, home), (50, home, ACCEL), (550, page_top)]),
        track(bottom, "transform", [(0, home), (50, home, ACCEL), (550, page_bottom)]),
        track("fade", "background-color", [(0, colour([0, 0, 0, 0])), (550, colour([0, 0, 0, 0]))]),
    ] + [track(node, prop, [(0, lit), (250, dark), (550, dark)]) for node, prop, lit, dark in lights])
    doc.timelines.add("departPopup", 200, [
        track(content, "opacity", [(0, number(1)), (150, number(0)), (200, number(0))]),
    ])
    doc.timelines.add("returnHome", 650, [
        track(top, "transform", [(0, page_top, ACCEL), (500, home), (650, home)]),
        track(bottom, "transform", [(0, page_bottom, ACCEL), (500, home), (650, home)]),
        track(content, "transform", [(0, transform()), (650, transform())]),
        track(content, "opacity", [(0, number(0)), (500, number(0)), (650, number(1))]),
        track("fade", "background-color", [(0, colour([0, 0, 0, 0])), (650, colour([0, 0, 0, 0]))]),
    ] + [track(node, prop, [(0, dark), (500, dark), (650, lit)]) for node, prop, lit, dark in lights])


# ------------------------------------------------------------------- depth

def depth_layer(doc: Document, ident: str, depth: float, children: list) -> dict:
    """Section 13.8 depth: the backdrop, light, grid and frame layers lean up
    to 6 dp away from the pointer, deeper layers further; content never
    moves. The session publishes pointer_x and pointer_y in -1..1. Reduced
    motion holds every layer still. A wrapper group carries the lean, so a
    band's own dock timelines keep their transform."""
    if "pointer_x" not in doc.state:
        doc.state["pointer_x"] = {"type": "number", "initial": 0}
        doc.state["pointer_y"] = {"type": "number", "initial": 0}
    if "motion_reduced" not in doc.state:
        doc.state["motion_reduced"] = {"type": "boolean", "initial": False, "cvar": "ui_retainedReducedMotion"}

    def axis(state: str) -> dict:
        return {"op": "select", "args": [{"state": "motion_reduced"}, 0, {"op": "*", "args": [{"state": state}, round(-6 * depth, 3)]}]}
    doc.bind(f"{ident}.transform", ident, "transform", [axis("pointer_x"), axis("pointer_y"), 1, 1, 0])
    return group(ident, {**FULL, "transform": transform(), "pointer-events": keyword("none")}, children)


# ------------------------------------------------------------- title carry

TITLE_SLOT = (39.0, 19.0)   # the page state's screen title (section 9)


def title_carry(doc: Document, items: list, continue_rows: bool = False) -> dict:
    """Section 13.8 title continuity (title.carry, section 8): during
    frame.dock the activated navigation label travels from its row into the
    page's title slot at 39,19 u and scales from the 24 dp label to the 18 dp
    screen title in text.title, where the stock page then shows its title.
    `items` lists (session request, label key, row top in u); with
    `continue_rows` the rows sit one pitch lower while CONTINUE is shown. The
    session plays carry_<request> only for a real page hand-off."""
    width, height, scale = U * 314, U * 24.4, 0.75
    # Scaling acts about the box center: keep the left and top edges in place.
    end = {"type": "transform", "unit": "dp", "value": [round(-(1 - scale) * width / 2, 3), round(-(1 - scale) * height / 2, 3),
                                                         scale, scale, 0]}
    text_value = items[-1][1]
    for index, (_, key, _) in reversed(list(enumerate(items[:-1], start=1))):
        text_value = {"op": "select", "args": [{"op": "==", "args": [{"state": "carry_item"}, index]}, key, text_value]}
    doc.state["carry_item"] = {"type": "number", "initial": 0}

    def carry_timeline(ident: str, top_u: float) -> str:
        start = {"type": "transform", "unit": "dp", "value": [round(U * (44 - TITLE_SLOT[0]), 3),
                                                               round(U * (top_u + 2.8 - TITLE_SLOT[1]), 3), 1, 1, 0]}
        # A play retargets its first key to the current value, so the label
        # reaches its row by 1 ms, then travels with frame.dock from 50 ms.
        return doc.timelines.add(ident, 550, [
            track("title-carry", "opacity", [(0, number(1)), (1, number(1)), (550, number(1))]),
            track("title-carry", "transform", [(0, start), (1, start), (50, start, ACCEL), (550, end)]),
            track("title-carry", "color", [(0, colour(rgb(ORANGE))), (1, colour(rgb(ORANGE))), (50, colour(rgb(ORANGE)), ACCEL),
                                           (550, colour([1, 1, 1, 0.5]))]),
        ])

    for index, (request, _, top_u) in enumerate(items, start=1):
        steps = [{"op": "setState", "values": {"carry_item": index}}]
        plain = carry_timeline(f"carry-{request}", top_u)
        if continue_rows:
            lowered = carry_timeline(f"carry-{request}-continue", top_u + 30)
            steps.append({"op": "if", "condition": {"state": "menu_continue"},
                          "then": [{"op": "playTimeline", "timeline": lowered}],
                          "else": [{"op": "playTimeline", "timeline": plain}]})
        else:
            steps.append({"op": "playTimeline", "timeline": plain})
        doc.events[f"carry_{request}"] = steps
    doc.bind("title-carry.text", "title-carry", "text", text_value)
    return group("carry", {**absolute(top=0, width=CANVAS_W, height=720), "left": length(50, "%"),
                           "margin-left": length(-CANVAS_W / 2), "pointer-events": keyword("none")}, [
        label("title-carry", items[-1][1], {**absolute(left=U * TITLE_SLOT[0], top=U * TITLE_SLOT[1], width=width, height=height),
              **typeface("marine", 24, height, rgb(ORANGE)), "white-space": keyword("nowrap"), "opacity": number(0),
              "transform": transform()}),
    ])


def hide_carry_at_home(doc: Document) -> None:
    """Opening the menu, or coming back from a page, starts without a carried
    title; the page's own title has taken over by then."""
    for timeline in doc.timelines.items:
        if timeline["id"] in ("open", "returnHome"):
            timeline["tracks"].append(track("title-carry", "opacity", [(0, number(0)), (timeline["durationMs"], number(0))]))


# ------------------------------------------------------------------ the emblem

# The Quake emblem traced from q4logo in its 260x260 u window at 380,125 u
# (visual specification 1.7). The source path lives beside the atlas.
EMBLEM = [
    (91.28, 3.55), (84.55, 7.11), (77.31, 11.81), (70.46, 17.27), (66.65, 20.82), (61.45, 26.41), (57.13, 31.87), (52.81, 38.34),
    (49.26, 44.69), (46.34, 51.29), (44.18, 57.26), (42.66, 62.59), (41.13, 69.95), (40.12, 79.60), (40.12, 89.50), (41.13, 99.02),
    (42.15, 104.23), (44.18, 111.72), (47.23, 119.84), (49.51, 124.54), (47.23, 130.51), (47.10, 131.78), (53.45, 141.43), (60.68, 149.93),
    (68.17, 149.55), (72.24, 153.23), (76.81, 156.79), (77.57, 163.64), (78.20, 164.40), (85.06, 168.47), (95.09, 173.04), (97.88, 174.05),
    (98.64, 174.05), (104.10, 170.50), (104.74, 170.37), (110.96, 172.02), (120.48, 173.42), (120.86, 173.80), (120.86, 212.77), (121.11, 213.28),
    (121.37, 217.98), (122.38, 225.98), (124.92, 239.31), (129.11, 256.57), (129.75, 257.33), (130.25, 256.57), (134.95, 236.89), (136.98, 225.98),
    (138.00, 217.98), (138.25, 213.28), (138.51, 212.77), (138.51, 173.80), (138.89, 173.42), (146.50, 172.40), (154.88, 170.37), (160.72, 174.05),
    (161.48, 174.05), (171.26, 169.99), (177.23, 166.82), (181.67, 163.90), (182.56, 156.79), (191.19, 149.55), (198.68, 149.93), (205.54, 141.93),
    (212.27, 131.78), (212.27, 130.89), (209.85, 124.54), (212.14, 119.84), (215.19, 111.72), (217.22, 104.23), (218.23, 99.02), (219.25, 89.50),
    (219.25, 79.60), (218.23, 69.95), (215.69, 58.91), (212.14, 49.13), (208.08, 40.88), (204.90, 35.67), (200.71, 29.83), (193.86, 21.96),
    (188.91, 17.27), (184.59, 13.71), (174.81, 7.11), (167.71, 3.55), (167.83, 3.94), (168.34, 3.94), (168.72, 4.44), (173.93, 7.49),
    (180.78, 12.70), (186.24, 17.77), (191.45, 23.61), (196.52, 30.72), (200.08, 36.82), (203.12, 43.54), (205.66, 50.91), (207.57, 59.03),
    (208.58, 67.54), (208.71, 75.54), (208.20, 82.14), (207.06, 89.12), (205.54, 95.09), (203.51, 101.05), (199.57, 109.69), (194.49, 117.94),
    (188.27, 125.68), (181.80, 132.03), (174.81, 137.49), (168.21, 141.68), (158.44, 146.25), (148.92, 149.30), (138.89, 151.07), (138.51, 150.69),
    (138.51, 128.35), (137.87, 124.54), (136.47, 118.96), (134.44, 112.86), (130.38, 103.09), (129.62, 102.32), (128.98, 103.09), (124.92, 112.86),
    (122.89, 118.96), (121.49, 124.54), (120.86, 128.35), (120.86, 150.69), (120.35, 151.07), (114.51, 150.19), (106.39, 148.15), (99.40, 145.62),
    (91.15, 141.68), (82.77, 136.22), (76.43, 131.02), (71.22, 125.81), (67.54, 121.49), (64.87, 117.94), (60.94, 111.72), (58.78, 107.78),
    (55.86, 101.05), (52.69, 90.90), (50.91, 79.60), (50.65, 70.08), (51.67, 59.79), (53.83, 50.53), (57.26, 41.13), (61.95, 32.12),
    (67.41, 24.25), (74.27, 16.63), (82.39, 9.65), (87.60, 6.09), (91.79, 3.68),
]


# The ring's center in the emblem window, and a reach from it past the spike's foot.
RING_CENTER = (129.7, 89.5)
GLINT_REACH = 170.0
GLINT_PERIOD_MS = 9000
GLINT_FRACTION = 0.12


def rotation(degrees: float) -> dict:
    return {"type": "transform", "unit": "dp", "value": [0, 0, 1, 1, degrees]}


def emblem(doc: Document) -> dict:
    """The watermark's darkening blend multiplies the lit field by
    rgb(168,166,57); a rim light at 0.20 follows its outline, and a glint
    runs around it every 9 s (section 13.8).

    The glint is the rim drawn bright under a wedge mask 12% of a turn wide
    that turns about the ring's center; the rim inside it turns back, so the
    outline stays put and only the lit stretch moves. Its light falls off
    toward the wedge's edges. Reduced motion hides it, keeping only the rim."""
    outline = [(U * x, U * y) for x, y in EMBLEM]
    cx, cy = RING_CENTER
    side = U * 2 * GLINT_REACH
    centre = side / 2
    shifted = [(U * (x - cx) + centre, U * (y - cy) + centre) for x, y in EMBLEM]
    half = math.pi * GLINT_FRACTION
    reach = side * 0.55

    def spoke(angle: float) -> tuple:
        return (round(centre + reach * math.sin(angle), 3), round(centre - reach * math.cos(angle), 3))

    wedge = [(centre, centre), spoke(-half), spoke(0), spoke(half)]
    left, right = spoke(-half), spoke(half)
    falloff = linear(left, right, [(0, [1, 1, 1, 0]), (0.5, [1, 1, 1, 1]), (1, [1, 1, 1, 0])])
    glint = group("emblem-glint", {**absolute(left=U * cx - centre, top=U * cy - centre, width=side, height=side),
                                   "transform": rotation(0), "display": keyword("block")}, [
        vector("emblem-glint-rim", {**absolute(left=0, top=0, width=side, height=side), "transform": rotation(0)}, [
            path("glint", shifted, stroke=stroke(solid(rgb(RAIL_DARK, 0.8)), 1.5, minimum=1, join="round"), blend="additive")]),
    ], mask={"paths": [path("wedge", wedge, fill=falloff)]})
    doc.state["motion_reduced"] = {"type": "boolean", "initial": False, "cvar": "ui_retainedReducedMotion"}
    doc.bind("emblem-glint.display", "emblem-glint", "display", {"op": "select", "args": [{"state": "motion_reduced"}, "none", "block"]})
    doc.timelines.add("emblemGlint", GLINT_PERIOD_MS, [
        track("emblem-glint", "transform", [(0, rotation(0)), (GLINT_PERIOD_MS, rotation(360))]),
        track("emblem-glint-rim", "transform", [(0, rotation(0)), (GLINT_PERIOD_MS, rotation(-360))])], iterations=0)
    doc.events.setdefault("onInit", []).append({"op": "playTimeline", "timeline": "emblemGlint"})
    return group("emblem", absolute(left=U * 380, top=U * 125, width=U * 260, height=U * 260), [
        vector("emblem-art", absolute(left=0, top=0, width=U * 260, height=U * 260), [
            path("shadow", outline, fill=solid(rgb("#A8A639")), blend="multiply"),
            path("rim", outline, stroke=stroke(solid(rgb(RAIL_DARK, 0.2)), 1.35, minimum=1, join="round"), blend="additive"),
        ]),
        glint,
    ])


# ------------------------------------------------------------------- the title

MENU_BACKGROUNDS = ["gfx/guis/mainmenu/level_mcc.dds", "gfx/guis/mainmenu/level_convoy1.dds", "gfx/guis/mainmenu/level_core1.dds",
                    "gfx/guis/mainmenu/level_process1_first.dds", "gfx/guis/mainmenu/level_tram1.dds"]


def montage(doc: Document) -> dict:
    """Backdrop levelshots cross-fade over 2000 ms every 5000 ms (section 8,
    ambient loops); decorative, so reduced motion holds the first picture."""
    shots = []
    period = 5000 * len(MENU_BACKGROUNDS)
    tracks = []
    for index, source in enumerate(MENU_BACKGROUNDS):
        ident = f"shot-{index}"
        base = [1, 1, 1, 1] if index == 0 else [1, 1, 1, 0]
        shots.append(picture(ident, source, {**FULL, "image-color": colour(base)}))
        if index == 0:
            continue
        start = 5000 * index
        last = index == len(MENU_BACKGROUNDS) - 1
        if not last:
            keys = [(0, colour([1, 1, 1, 0])), (start, colour([1, 1, 1, 0])), (start + 2000, colour([1, 1, 1, 1])),
                    (period - 3000, colour([1, 1, 1, 1])), (period - 2990, colour([1, 1, 1, 0])), (period, colour([1, 1, 1, 0]))]
        else:
            # The newest picture fades out as the loop wraps, revealing the first.
            keys = [(0, colour([1, 1, 1, 1])), (2000, colour([1, 1, 1, 0])), (start, colour([1, 1, 1, 0])),
                    (start + 2000, colour([1, 1, 1, 1])), (period, colour([1, 1, 1, 1]))]
            shots[-1]["properties"]["image-color"] = colour([1, 1, 1, 1])
        tracks.append(track(ident, "image-color", keys))
    doc.timelines.add("montage", period, tracks, iterations=0)
    doc.events.setdefault("onInit", []).append({"op": "playTimeline", "timeline": "montage"})
    return group("shots", dict(FULL), shots)


def title_document() -> dict:
    doc = Document("openq4.title")
    doc.state.update({
        "menu_continue": {"type": "boolean", "initial": False},
        "menu_continue_title": {"type": "string", "initial": ""},
        "menu_continue_detail": {"type": "string", "initial": ""},
        "menu_continue_shot": {"type": "string", "initial": ""},
    })
    doc.session("continue", "continue")
    doc.session("singlePlayer", "singlePlayer")
    doc.session("loadGame", "loadGame")
    doc.session("multiplayer", "multiplayer")
    doc.session("settings", "settings")
    doc.session("mods", "mods")
    doc.session("demos", "demos")
    doc.session("updates", "updates")
    doc.session("credits", "credits")
    doc.session("quit", "quit")
    exit_modal = confirmation(doc, "exitModal", "#str_200169", "#str_200170", "quit")
    doc.events["onBack"] = [{"op": "call", "event": "exitModalShow"}]

    # The message line at 44,364 u explains the focused item (section 13.7):
    # the newest save's levelshot, title and time for CONTINUE, else a sentence.
    nav_top = 212.2
    def offset(row: int) -> float:
        return 364 - (nav_top + 30 * row)
    continue_detail = message_line("detail-continue", offset(0), [
        picture("detail-continue-shot", "", {**absolute(left=0, top=U * 1, width=U * 56, height=U * 31.5)}),
        vector("detail-continue-frame", absolute(left=0, top=U * 1, width=U * 56, height=U * 31.5), [
            path("frame", [(0.5, 0.5), ({"fraction": 1, "dp": -0.5}, 0.5), ({"fraction": 1, "dp": -0.5}, {"fraction": 1, "dp": -0.5}), (0.5, {"fraction": 1, "dp": -0.5})],
                 stroke=stroke(solid(rgb(PICTURE)), 1.5))]),
        label("detail-continue-title", "#str_200984", {**absolute(left=U * 64, top=0, width=U * 369, height=U * 16),
              **typeface("lowpixel", 17, U * 16, [1, 1, 1, 0.8]), "white-space": keyword("nowrap")}),
        label("detail-continue-detail", "#str_200984", {**absolute(left=U * 64, top=U * 16, width=U * 369, height=U * 16),
              **typeface("lowpixel", 14, U * 16, [0.72, 0.76, 0.62, 1]), "white-space": keyword("nowrap")}),
    ])
    doc.bind("detail-continue-shot.image", "detail-continue-shot", "image", {"state": "menu_continue_shot"})
    doc.bind("detail-continue-title.text", "detail-continue-title", "text", {"state": "menu_continue_title"})
    doc.bind("detail-continue-detail.text", "detail-continue-detail", "text", {"state": "menu_continue_detail"})
    rows = [("nav_singleplayer", "#str_42000", "singlePlayer", "#str_230026"), ("nav_loadgame", "#str_200001", "loadGame", "#str_230027"),
            ("nav_multiplayer", "#str_200002", "multiplayer", "#str_230028"), ("nav_settings", "#str_200009", "settings", "#str_230029")]
    buttons = [navigation_plate(doc, "nav_continue", "#str_200984", action="continue", detail=continue_detail)]
    for index, (ident, key, action, sentence) in enumerate(rows, start=1):
        detail_id = f"detail-{ident[4:]}"
        detail = message_line(detail_id, offset(index), [
            label(f"{detail_id}-text", sentence, {**absolute(left=0, top=0, width=U * 433, height=U * 33),
                  **typeface("lowpixel", 17, 22, [1, 1, 1, 0.8])})])
        # Without a save CONTINUE collapses and every row rises one pitch.
        doc.bind(f"{detail_id}.top", detail_id, "top", {"op": "select", "args": [
            {"state": "menu_continue"}, round(U * offset(index), 3), round(U * offset(index - 1), 3)]})
        buttons.append(navigation_plate(doc, ident, key, action=action, detail=detail))
    nav = group("nav", {**absolute(left=0, top=U * nav_top, width=U * 413), "display": keyword("flex"),
                        "flex-direction": keyword("column")}, buttons)
    doc.bind("nav_continue.display", "nav_continue", "display", {"op": "select", "args": [{"state": "menu_continue"}, "block", "none"]})
    links = [link(doc, "link_mods", "#str_200010", action="mods"), link(doc, "link_demos", "#str_41500", action="demos"),
             link(doc, "link_updates", "#str_200011", action="updates"), link(doc, "link_credits", "#str_200012", action="credits"),
             link(doc, "link_exit", "#str_200013", event="exitModalShow")]
    stage = group("home-stage", {**absolute(top=0, width=CANVAS_W, height=720), "left": length(50, "%"), "margin-left": length(-CANVAS_W / 2),
                                 "opacity": number(1)}, [
        emblem(doc),
        picture("wordmark", "gfx/guis/mainmenu/q4text", {**absolute(left=U * 6, top=U * 119, width=U * 376, height=U * 92),
                                                          "image-blend": keyword("additive"), "image-color": colour([1, 1, 1, 1])}, fit="fill"),
    ])
    content = group("home", {**FULL, "transform": transform(), "opacity": number(1)}, [
        group("home-content", {**absolute(top=0, width=CANVAS_W, height=720), "left": length(50, "%"), "margin-left": length(-CANVAS_W / 2)}, [
            nav,
            plinth(doc, links),
        ]),
    ])
    root = group("screen", {**FULL, "background-color": colour([0, 0, 0, 1]), "font-family": font("marine"),
                            "font-size": length(16), "color": colour([1, 1, 1, 0.8])}, [
        depth_layer(doc, "depth-backdrop", 1.0, [montage(doc)]),
        depth_layer(doc, "depth-light", 0.66, lit_field("field", 0.7)),
        stage,
        depth_layer(doc, "depth-frame", 0.33, framing_bands("band")),
        content,
        prompt_bar(doc, [("#str_107019", "#str_200747"), ("#str_107020", "#str_200013")]),
        title_carry(doc, [("singlePlayer", "#str_42000", 212.2), ("loadGame", "#str_200001", 242.2),
                          ("multiplayer", "#str_200002", 272.2), ("settings", "#str_200009", 302.2)], continue_rows=True),
        exit_modal,
        group("fade", {**FULL, "background-color": colour([0, 0, 0, 0]), "pointer-events": keyword("none")}),
    ])
    band_motion(doc, "band", "home", [("wordmark", "image-color", colour([1, 1, 1, 1]), colour([1, 1, 1, 0])),
                                      ("home-stage", "opacity", number(1), number(0))])
    hide_carry_at_home(doc)
    return doc.build(root)


# ------------------------------------------------------------------- the pause

def level_block(doc: Document) -> dict:
    """The current level block in the emblem's place (section 13.7): a card
    (section 6: black 0.94 in a marine.rail.card rail, 12 and 3 dp cuts, a
    40 dp header) with the levelshot in a picture frame, the level, the
    difficulty and the map's objectives."""
    x, y, w, h = U * 374, U * 118, U * 262, U * 270
    major, minor = 12.0, 3.0
    card = [(minor, 0), (w - major, 0), (w, major), (w, h - minor), (w - minor, h), (major, h), (0, h - major), (0, minor)]
    header = 40.0
    frame = vector("level-card", absolute(left=0, top=0, width=w, height=h), [
        path("body", card, fill=solid([0, 0, 0, 0.94])),
        path("wash", [(minor, 0.75), (w - major, 0.75), (w - major + header * 0.3, header), (0.75, header), (0.75, minor)],
             fill=linear((0, 0), (w, 0), [(0, [1, 1, 1, 0.08]), (0.5, [1, 1, 1, 0.08]), (1, [1, 1, 1, 0])])),
        path("rule", [(0, header), (w, header)], closed=False, stroke=stroke(solid(rgb(RAIL_CARD, 0.5)), 1)),
        path("rail", card, stroke=stroke(solid(rgb(RAIL_CARD)), 1.5)),
        marker_path("mark", 14, 16, 8, rgb(MARKER)),
    ])
    pw, ph = w - 30, U * 118
    shot = picture("level-shot", "", {**absolute(left=15, top=header + 12, width=pw, height=ph)})
    shot_frame = vector("level-shot-frame", absolute(left=15, top=header + 12, width=pw, height=ph), [
        path("frame", [(0.5, 0.5), ({"fraction": 1, "dp": -0.5}, 0.5), ({"fraction": 1, "dp": -0.5}, {"fraction": 1, "dp": -0.5}), (0.5, {"fraction": 1, "dp": -0.5})],
             stroke=stroke(solid(rgb(PICTURE)), 1.5))])
    heading = label("level-heading", "#str_230030", {**absolute(left=30, top=0, width=w - 60, height=header),
        **typeface("marine", 14, header, [1, 1, 1, 0.9]), "white-space": keyword("nowrap")})
    below = header + 12 + ph + 10
    name = label("level-name", "#str_230030", {**absolute(left=15, top=below, width=pw, height=24),
        **typeface("marine", 20, 24, [1, 1, 1, 0.9]), "white-space": keyword("nowrap")})
    detail = label("level-detail", "#str_230030", {**absolute(left=15, top=below + 26, width=pw, height=20),
        **typeface("lowpixel", 17, 20, [1, 1, 1, 0.6]), "white-space": keyword("nowrap")})
    objectives_head = label("level-objectives-head", "#str_200291", {**absolute(left=15, top=below + 54, width=pw, height=18),
        **typeface("marine", 14, 18, rgb(OBJECTIVE_HEAD)), "white-space": keyword("nowrap"), "display": keyword("block")})
    objectives = label("level-objectives", "#str_230030", {**absolute(left=15, top=below + 76, width=pw, height=h - below - 90),
        **typeface("lowpixel", 14, 18, [0.82, 0.87, 0.71, 1]), "overflow": keyword("hidden")})
    doc.bind("level-shot.image", "level-shot", "image", {"state": "pause_shot"})
    doc.bind("level-name.text", "level-name", "text", {"state": "pause_level"})
    doc.bind("level-detail.text", "level-detail", "text", {"state": "pause_detail"})
    doc.bind("level-objectives.text", "level-objectives", "text", {"state": "pause_objectives"})
    # A map without objectives shows no empty heading.
    doc.bind("level-objectives-head.display", "level-objectives-head", "display",
             {"op": "select", "args": [{"op": "==", "args": [{"state": "pause_objectives"}, ""]}, "none", "block"]})
    return group("level-block", absolute(left=x, top=y, width=w, height=h),
                 [frame, shot, shot_frame, heading, name, detail, objectives_head, objectives])


def pause_document() -> dict:
    doc = Document("openq4.pause")
    doc.state.update({
        "pause_level": {"type": "string", "initial": ""},
        "pause_detail": {"type": "string", "initial": ""},
        "pause_objectives": {"type": "string", "initial": ""},
        "pause_shot": {"type": "string", "initial": ""},
    })
    doc.session("resume", "resume")
    doc.session("saveGame", "saveGame")
    doc.session("loadGame", "loadGame")
    doc.session("restartLevel", "restartLevel")
    doc.session("settings", "settings")
    doc.session("quitToMenu", "quitToMenu")
    doc.session("quit", "quit")
    quit_modal = confirmation(doc, "quitModal", "#str_200004", "#str_200174", "quitToMenu")
    exit_modal = confirmation(doc, "exitModal", "#str_200169", "#str_200170", "quit")
    doc.events["onBack"] = [{"op": "action", "action": "resume"}]
    nav = group("nav", {**absolute(left=0, top=U * 182.2, width=U * 413), "display": keyword("flex"),
                        "flex-direction": keyword("column")}, [
        navigation_plate(doc, "nav_resume", "#str_200381", action="resume"),
        navigation_plate(doc, "nav_savegame", "#str_200003", action="saveGame"),
        navigation_plate(doc, "nav_loadgame", "#str_200001", action="loadGame"),
        navigation_plate(doc, "nav_restart", "#str_229983", action="restartLevel"),
        navigation_plate(doc, "nav_settings", "#str_200009", action="settings"),
        navigation_plate(doc, "nav_quit", "#str_230025", event="quitModalShow"),
    ])
    content = group("home", {**FULL, "transform": transform(), "opacity": number(1)}, [
        group("home-content", {**absolute(top=0, width=CANVAS_W, height=720), "left": length(50, "%"), "margin-left": length(-CANVAS_W / 2)}, [
            label("paused-title", "#str_230031", {**absolute(left=U * 44, top=U * 134, width=U * 330, height=U * 24),
                  **typeface("marine", 18, U * 24, [1, 1, 1, 0.5]), "white-space": keyword("nowrap")}),
            nav,
            level_block(doc),
            plinth(doc, [link(doc, "link_exit", "#str_200013", event="exitModalShow")]),
        ]),
    ])
    # The paused view, softened by a darkening scrim and vignette where the
    # scene effect is unavailable (sections 9 and 13.6).
    scrim = vector("scrim", dict(FULL), [
        path("dim", [(0, 0), ({"fraction": 1}, 0), ({"fraction": 1}, {"fraction": 1}), (0, {"fraction": 1})], fill=solid([0, 0, 0, 0.45])),
        path("lead", [(0, 0), (vx(413), 0), (vx(413), {"fraction": 1}), (0, {"fraction": 1})],
             fill=linear((vx(-107), 0), (vx(413), 0), [(0, [0, 0, 0, 0.7]), (0.55, [0, 0, 0, 0.35]), (1, [0, 0, 0, 0])])),
    ])
    root = group("screen", {**FULL, "font-family": font("marine"), "font-size": length(16), "color": colour([1, 1, 1, 0.8])}, [
        scrim,
        *lit_field("field", 0.45),
        *framing_bands("band"),
        content,
        prompt_bar(doc, [("#str_107019", "#str_200747"), ("#str_107020", "#str_200381")]),
        title_carry(doc, [("saveGame", "#str_200003", 212.2), ("loadGame", "#str_200001", 242.2),
                          ("restartLevel", "#str_229983", 272.2), ("settings", "#str_200009", 302.2)]),
        quit_modal,
        exit_modal,
        group("fade", {**FULL, "background-color": colour([0, 0, 0, 0]), "pointer-events": keyword("none")}),
    ])
    band_motion(doc, "band", "home", [])
    hide_carry_at_home(doc)
    return doc.build(root)


# ----------------------------------------------------------------- the loading

def corner_bracket(ident: str, left_u: float, top_u: float, flip_x: bool, flip_y: bool) -> dict:
    """load_corner (Appendix B.1): an L bracket with 24 u legs in a 52 u
    window, a 0.8 u white core and a warm 7 u halo, additive #3A3A3A."""
    size = U * 52
    inset, leg = U * 14, U * 24
    ox = size - inset if flip_x else inset
    oy = size - inset if flip_y else inset
    sx = -1 if flip_x else 1
    sy = -1 if flip_y else 1
    points = [(ox, oy + sy * leg), (ox, oy), (ox + sx * leg, oy)]
    halo = path("halo", points, closed=False, stroke=stroke(solid(rgb("#502D14", 0.55)), U * 7, minimum=1, join="miter"), blend="additive")
    core = path("core", points, closed=False, stroke=stroke(solid(rgb("#3A3A3A")), U * 1.2, minimum=1, join="miter"), blend="additive")
    white = path("white", points, closed=False, stroke=stroke(solid([1, 1, 1, 0.55]), U * 0.8, minimum=1, join="miter"), blend="additive")
    return vector(ident, absolute(left=U * left_u, top=U * top_u, width=size, height=size), [halo, core, white])


def loading_document() -> dict:
    """Section 14.17: the stock loading screens in their Remastered form: the
    drifting levelshot, the detail line, the progress with the loader's phase,
    and in multiplayer the band kept low under the server card."""
    doc = Document("openq4.loading")
    doc.state.update({
        "map_loading": {"type": "number", "initial": 0},
        "loading_levelshot": {"type": "string", "initial": ""},
        "loading_levelname": {"type": "string", "initial": ""},
        "loading_detail": {"type": "string", "initial": ""},
        "loading_objectives": {"type": "string", "initial": ""},
        "loading_author": {"type": "string", "initial": ""},
        "server_name": {"type": "string", "initial": ""},
        "server_ip": {"type": "string", "initial": ""},
        "server_gametype": {"type": "string", "initial": ""},
        "server_limit": {"type": "string", "initial": ""},
        "loading_mp": {"type": "boolean", "initial": False},
        "loading_intro": {"type": "boolean", "initial": False},
        "loading_ready": {"type": "boolean", "initial": False},
        "motion_reduced": {"type": "boolean", "initial": False, "cvar": "ui_retainedReducedMotion"},
        "loading_phase": {"type": "string", "initial": ""},
        "loading_count": {"type": "string", "initial": ""},
        "loading_controller": {"type": "boolean", "initial": False},
    })
    doc.events["FinishedLoading"] = [{"op": "setState", "values": {"loading_ready": True}},
                                     {"op": "playTimeline", "timeline": "continuePulse"}]
    # Loading bands (Appendix B.2): black 0.80 with one 45-degree riser each.
    top_edge = [(edge(0), U * 28.8), (vx(268.8), U * 28.8), (vx(290), U * 9.3), (edge(1), U * 9.3)]
    bottom_edge = [(edge(0), U * 468.5), (vx(165), U * 468.5), (vx(207.5), U * 426), (edge(1), U * 426)]

    def spill(edge_points, down: bool) -> list:
        # The *_edgeadd companions add #181D0A from the inner edge into the
        # picture: 0.98 at the edge to 0.55 at 35 u, gone by 80 u.
        paths = []
        steps = 8
        for index in range(steps, 0, -1):
            width = 2 * U * 80 * index / steps
            paths.append(path(f"spill-{index}", edge_points, closed=False, blend="additive",
                              stroke=stroke(solid(rgb(LOAD_SPILL, round(0.98 / steps * 1.4, 4))), width, minimum=0, join="round")))
        return paths

    top_band = vector("load-top", dict(FULL), spill(top_edge, True) + [
        path("band", [(edge(1), -400), (edge(0), -400)] + top_edge, fill=solid([0, 0, 0, 0.8]))])
    bottom_band = vector("load-bottom", dict(FULL), spill(bottom_edge, False) + [
        path("band", bottom_edge + [(edge(1), U * 480 + 400), (edge(0), U * 480 + 400)], fill=solid([0, 0, 0, 0.8]))])
    shot = picture("load-shot", "", {**FULL, "transform": transform()})
    doc.bind("load-shot.image", "load-shot", "image", {"state": "loading_levelshot"})
    # Remastered: the levelshot drifts in by 3% over the load; reduced motion
    # holds it still (section 14.17).
    drift = {"op": "select", "args": [{"state": "motion_reduced"}, 1, {"op": "+", "args": [
        1, {"op": "*", "args": [0.03, {"op": "clamp", "args": [{"state": "map_loading"}, 0, 1]}]}]}]}
    doc.bind("load-shot.transform", "load-shot", "transform", [0, 0, drift, drift, 0])

    brackets = group("brackets", {"display": keyword("block"), **absolute(top=0, width=CANVAS_W, height=720), "left": length(50, "%"), "margin-left": length(-CANVAS_W / 2)}, [
        corner_bracket("bracket-tl", 8, 28, False, False), corner_bracket("bracket-tr", 580, 28, True, False),
        group("brackets-low", absolute(left=0, top=0, width=CANVAS_W, height=720), [
            corner_bracket("bracket-bl", 8, 374, False, True), corner_bracket("bracket-br", 580, 374, True, True)]),
    ])
    doc.bind("brackets.display", "brackets", "display", {"op": "select", "args": [{"state": "loading_intro"}, "none", "block"]})
    # The dot matrix: ten by two 4 u squares on a 9 u pitch, top-leading.
    dots = []
    for column in range(10):
        for row in range(2):
            x0, y0 = U * (12 + 9 * column), U * (4 + 9 * row)
            dots.append(path(f"dot-{column}-{row}", [(x0, y0), (x0 + U * 4, y0), (x0 + U * 4, y0 + U * 4), (x0, y0 + U * 4)],
                             fill=solid(rgb(DOTS, 1))))
    dot_matrix = vector("dots", {**absolute(top=0, width=CANVAS_W, height=U * 40), "left": length(50, "%"), "margin-left": length(-CANVAS_W / 2)}, dots)

    # Identity: the level name trails at the top over a name strip (section 9).
    identity = group("identity", {"display": keyword("block"), **absolute(top=U * 34, width=CANVAS_W, height=U * 60), "left": length(50, "%"), "margin-left": length(-CANVAS_W / 2)}, [
        # The strip also darkens the message line, which must read over any levelshot.
        vector("name-strip", absolute(left=U * 300, top=0, width=U * 340, height=U * 44), [
            path("strip", [(0, 0), ({"fraction": 1}, 0), ({"fraction": 1}, {"fraction": 1}), (0, {"fraction": 1})],
                 fill=linear((0, 0), ({"fraction": 1}, 0), [(0, [0, 0, 0, 0]), (0.5, [0, 0, 0, 0.55]), (1, [0, 0, 0, 0.8])]))]),
        label("level-name", "#str_230030", {**absolute(left=U * 100, top=0, width=U * 532, height=U * 26), **typeface("marine", 26, U * 26, [1, 1, 1, 0.8]),
              "text-align": keyword("right"), "letter-spacing": length(-0.1, "em"), "white-space": keyword("nowrap")}),
        label("level-detail", "#str_230030", {**absolute(left=U * 100, top=U * 27, width=U * 532, height=U * 14), **typeface("lowpixel", 17, U * 14, [1, 1, 1, 0.62]),
              "text-align": keyword("right"), "white-space": keyword("nowrap")}),
    ])
    doc.bind("level-name.text", "level-name", "text", {"state": "loading_levelname"})
    doc.bind("level-detail.text", "level-detail", "text", {"state": "loading_detail"})
    doc.bind("identity.display", "identity", "display", {"op": "select", "args": [{"state": "loading_intro"}, "none", "block"]})

    # Objectives on the leading side, in the objectives display's open plate (section 14.11).
    objectives = group("objectives", {"display": keyword("block"), **absolute(top=U * 120, width=U * 250, height=U * 180), "left": length(50, "%"), "margin-left": length(-CANVAS_W / 2 + U * 18)}, [
        vector("objectives-plate", absolute(left=0, top=0, width=U * 250, height=U * 180), [
            path("fill", [(0, 0), (U * 250, 0), (U * 250, U * 180), (U * 20, U * 180), (0, U * 160)],
                 fill=linear((0, 0), (U * 250, 0), [(0, rgb("#B0CD6B", 0.2)), (0.3, rgb("#B0CD6B", 0.2)), (0.56, rgb("#B0CD6B", 0)), (1, rgb("#B0CD6B", 0))])),
            path("rail", [(0.75, 0), (0.75, U * 160), (U * 20, U * 180 - 0.75), (U * 250, U * 180 - 0.75)], closed=False,
                 stroke=stroke(linear((0, 0), (U * 250, 0), [(0, rgb("#B0CD6B", 0.4)), (0.56, rgb("#B0CD6B", 0.4)), (1, rgb("#B0CD6B", 0))]), 1.5)),
            path("backing", [(0, 0), (U * 250, 0), (U * 250, U * 180), (U * 20, U * 180), (0, U * 160)],
                 fill=linear((0, 0), (U * 250, 0), [(0, [0, 0, 0, 0.5]), (0.66, [0, 0, 0, 0.5]), (1, [0, 0, 0, 0])])),
        ]),
        label("objectives-head", "#str_200291", {**absolute(left=U * 10, top=U * 8, width=U * 230, height=U * 16),
              **typeface("marine", 18, U * 16, rgb(OBJECTIVE_HEAD)), "letter-spacing": length(-0.05, "em"), "white-space": keyword("nowrap")}),
        label("objectives-text", "#str_230030", {**absolute(left=U * 10, top=U * 30, width=U * 225, height=U * 140),
              **typeface("lowpixel", 14, 18, [0.82, 0.87, 0.71, 1]), "overflow": keyword("hidden")}),
    ])
    doc.bind("objectives-text.text", "objectives-text", "text", {"state": "loading_objectives"})
    doc.bind("objectives.display", "objectives", "display", {"op": "select", "args": [
        {"op": "||", "args": [{"state": "loading_mp"}, {"op": "||", "args": [{"state": "loading_intro"},
                                                                              {"op": "==", "args": [{"state": "loading_objectives"}, ""]}]}]}, "none", "block"]})

    # Remastered multiplayer (section 14.17): the bottom band stays low and a
    # section 6 card on the leading side, above the band's thin part, holds
    # the server's name in its header, then its address, mode and limits.
    cw, ch, major, minor, header = U * 250, U * 80, 12.0, 3.0, 40.0
    outline = [(minor, 0), (cw - major, 0), (cw, major), (cw, ch - minor), (cw - minor, ch), (major, ch), (0, ch - major), (0, minor)]

    def card_line(ident: str, top: float, tint: list) -> dict:
        return label(ident, "#str_230030", {**absolute(left=15, top=top, width=cw - 30, height=20),
                                            **typeface("lowpixel", 17, 20, tint), "white-space": keyword("nowrap")})

    # It ends at 384 u, clear of the lower corner bracket (388-412 u).
    server = group("server", {"display": keyword("block"), **absolute(top=U * 304, width=CANVAS_W, height=ch), "left": length(50, "%"),
                              "margin-left": length(-CANVAS_W / 2)}, [
        group("server-card", absolute(left=U * 18, top=0, width=cw, height=ch), [
            vector("server-frame", absolute(left=0, top=0, width=cw, height=ch), [
                path("body", outline, fill=solid([0, 0, 0, 0.94])),
                path("wash", [(minor, 0.75), (cw - major, 0.75), (cw - major + header * 0.3, header), (0.75, header), (0.75, minor)],
                     fill=linear((0, 0), (cw, 0), [(0, [1, 1, 1, 0.08]), (0.5, [1, 1, 1, 0.08]), (1, [1, 1, 1, 0])])),
                path("rule", [(0, header), (cw, header)], closed=False, stroke=stroke(solid(rgb(RAIL_CARD, 0.5)), 1)),
                path("rail", outline, stroke=stroke(solid(rgb(RAIL_CARD)), 1.5)),
                marker_path("mark", 14, 16, 8, rgb(MARKER)),
            ]),
            label("server-name", "#str_230030", {**absolute(left=30, top=0, width=cw - 45, height=header),
                  **typeface("marine", 14, header, [1, 1, 1, 0.9]), "white-space": keyword("nowrap")}),
            card_line("server-address", header + 8, [1, 1, 1, 0.62]),
            card_line("server-mode", header + 28, [1, 1, 1, 0.8]),
            card_line("server-rules", header + 48, [1, 1, 1, 0.62]),
        ]),
    ])
    doc.bind("server-name.text", "server-name", "text", {"state": "server_name"})
    doc.bind("server-address.text", "server-address", "text", {"state": "server_ip"})
    doc.bind("server-mode.text", "server-mode", "text", {"state": "server_gametype"})
    doc.bind("server-rules.text", "server-rules", "text", {"state": "server_limit"})
    doc.bind("server.display", "server", "display", {"op": "select", "args": [{"state": "loading_mp"}, "block", "none"]})

    # Remastered progress (section 14.17): the thick part of the bottom band
    # holds LOADING above a 240 u bar ending at 632 u; under the bar run the
    # loader's phase with its count and, trailing, the percentage in the value
    # color. When the level is ready LOADING becomes the continue prompt for
    # the active device: the south button and CONTINUE on a controller.
    bar_x, bar_w, tail = U * 392, U * 240, U * 8
    # Multiplayer never waits: when its load ends the prompt reads JOINING.
    joining = {"op": "&&", "args": [{"state": "loading_mp"}, {"op": ">=", "args": [{"state": "map_loading"}, 1]}]}
    prompt = {"op": "select", "args": [{"state": "loading_ready"},
              {"op": "select", "args": [{"state": "loading_controller"}, "#str_200984", "#str_200937"]},
              {"op": "select", "args": [joining, "#str_230037", "#str_200938"]}]}
    glyph_shown = {"op": "select", "args": [{"op": "&&", "args": [{"state": "loading_ready"}, {"state": "loading_controller"}]},
                                            "block", "none"]}

    def south_button(ident: str, tint: list) -> dict:
        """The controller's face buttons as a diamond with the south one
        filled: the platform-neutral confirm glyph."""
        def ring(cx: float, cy: float, radius: float, sides: int = 12) -> list:
            return [(round(cx + radius * math.cos(2 * math.pi * i / sides), 3), round(cy + radius * math.sin(2 * math.pi * i / sides), 3))
                    for i in range(sides)]
        paths = [path(name, ring(cx, cy, 2.6), stroke=stroke(solid(tint), 1.2, minimum=1))
                 for name, (cx, cy) in (("north", (9, 3.5)), ("west", (3.5, 9)), ("east", (14.5, 9)))]
        paths.append(path("south", ring(9, 14.5, 3.2), fill=solid(tint)))
        return vector(ident, {"position": keyword("relative"), "display": keyword("none"), "width": length(18),
                              "height": length(18), "margin-right": length(8)}, paths)

    def prompt_row(ident: str, offset: float, tint: list) -> dict:
        return group(ident, {**absolute(top=U * 2 + offset, height=U * 22, right=tail - offset), "display": keyword("flex"),
                             "flex-direction": keyword("row"), "align-items": keyword("center")}, [
            south_button(f"{ident}-glyph", tint),
            label(f"{ident}-text", "#str_200938", {"position": keyword("relative"), "display": keyword("block"),
                  **typeface("marine", 29, U * 22, tint), "white-space": keyword("nowrap")}),
        ])

    def stage_label(ident: str, key: str, tint: list, **more) -> dict:
        return label(ident, key, {"position": keyword("relative"), "display": keyword("block"),
                                  **typeface("lowpixel", 14, U * 10, tint), "white-space": keyword("nowrap"), **more})

    progress = group("progress", {**absolute(top=U * 426, width=CANVAS_W, height=U * 54), "left": length(50, "%"),
                                  "margin-left": length(-CANVAS_W / 2)}, [
        prompt_row("progress-prompt-shadow", 1.5, [0, 0, 0, 0.8]),
        prompt_row("progress-prompt", 0, [1, 1, 1, 1]),
        vector("progress-track", absolute(left=bar_x, top=U * 26, width=bar_w, height=U * 6), [
            path("track", [(U * 6, 0), ({"fraction": 1}, 0), ({"fraction": 1}, {"fraction": 1}), (0, {"fraction": 1}), (0, U * 6)],
                 fill=linear((0, 0), (0, {"fraction": 1}), [(0, rgb(PROGRESS, 0.2)), (0.5, rgb(PROGRESS, 0.3)), (1, rgb(PROGRESS, 0.2))]))]),
        group("progress-fill-clip", {**absolute(left=bar_x, top=U * 26, width=0, height=U * 6), "overflow": keyword("hidden")}, [
            vector("progress-fill", absolute(left=0, top=0, width=bar_w, height=U * 6), [
                path("fill", [(U * 6, 0), ({"fraction": 1}, 0), ({"fraction": 1}, {"fraction": 1}), (0, {"fraction": 1}), (0, U * 6)],
                     fill=linear((0, 0), (0, {"fraction": 1}), [(0, rgb(PROGRESS, 0.35)), (0.5, rgb(PROGRESS, 0.6)), (1, rgb(PROGRESS, 0.35))])),
                path("core", [(U * 3, U * 3), ({"fraction": 1}, U * 3)], closed=False, stroke=stroke(solid(rgb("#FFC070", 0.5)), 1, minimum=1)),
            ])]),
        group("progress-stage", {**absolute(left=bar_x, top=U * 34.5, height=U * 10), "display": keyword("flex"),
                                 "flex-direction": keyword("row")}, [
            stage_label("progress-phase", "#str_230030", [1, 1, 1, 0.62]),
            stage_label("progress-count", "#str_230030", [1, 1, 1, 0.42], **{"margin-left": length(8)}),
        ]),
        group("progress-percent", {**absolute(top=U * 34.5, height=U * 10, right=tail), "display": keyword("flex"),
                                   "flex-direction": keyword("row")}, [
            stage_label("progress-percent-value", "#str_230030", rgb(VALUE)),
            stage_label("progress-percent-sign", "#str_230036", rgb(VALUE)),
        ]),
    ])
    doc.bind("progress-fill-clip.width", "progress-fill-clip", "width",
             {"op": "*", "args": [{"op": "clamp", "args": [{"state": "map_loading"}, 0, 1]}, bar_w]})
    for row in ("progress-prompt", "progress-prompt-shadow"):
        doc.bind(f"{row}-text.text", f"{row}-text", "text", prompt)
        doc.bind(f"{row}-glyph.display", f"{row}-glyph", "display", glyph_shown)
    doc.bind("progress-phase.text", "progress-phase", "text", {"state": "loading_phase"})
    doc.bind("progress-count.text", "progress-count", "text", {"state": "loading_count"})
    doc.bind("progress-percent-value.text", "progress-percent-value", "text", {"op": "numberText", "decimals": 0, "args": [
        {"op": "round", "args": [{"op": "*", "args": [{"op": "clamp", "args": [{"state": "map_loading"}, 0, 1]}, 100]}]}]})
    # The prompt pulses from 100 % to 50 % over 500 ms and back over 200 ms (section 8).
    doc.timelines.add("continuePulse", 700, [
        track("progress-prompt-text", "color", [(0, colour([1, 1, 1, 1])), (500, colour([1, 1, 1, 0.5])), (700, colour([1, 1, 1, 1]))])],
        iterations=0)
    root = group("screen", {**FULL, "background-color": colour([0, 0, 0, 1]), "font-family": font("marine"),
                            "font-size": length(16), "color": colour([1, 1, 1, 0.8])}, [
        shot,
        vector("load-grid", dict(FULL), [grid_path()]),
        top_band, bottom_band, brackets, dot_matrix, identity, objectives, server, progress,
    ])
    return doc.build(root)


HEADER = """// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
// Generated by tools/ui/build_retained_screens.py from docs/dev/ui-visual-design.md;
// regenerate instead of editing. Presented only while ui_retained is 1.
"""


def encode(value, depth: int = 0) -> str:
    """Structured JSON with every small object or array on one line, so the
    generated sources stay reviewable without tens of thousands of lines."""
    flat = json.dumps(value, ensure_ascii=False)
    if len(flat) <= 110 or not isinstance(value, (dict, list)) or not value:
        return flat
    pad, inner = " " * depth, " " * (depth + 1)
    if isinstance(value, dict):
        items = [f"{inner}{json.dumps(key, ensure_ascii=False)}: {encode(item, depth + 1)}" for key, item in value.items()]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    items = [f"{inner}{encode(item, depth + 1)}" for item in value]
    return "[\n" + ",\n".join(items) + "\n" + pad + "]"


def render(document: dict) -> str:
    text_value = HEADER + encode(document) + "\n"
    return text_value.replace("\r\n", "\n").replace("\n", "\r\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail when a generated document differs from its source")
    args = parser.parse_args()
    documents = {"title": title_document(), "pause": pause_document(), "loading": loading_document()}
    stale = []
    for name, document in documents.items():
        output = OUTPUTS[name]
        rendered = render(document)
        if args.check:
            # Git normalizes these text files, so a checkout may hold either
            # line ending; compare the content, not the convention.
            current = output.read_bytes().decode("utf-8").replace("\r\n", "\n") if output.exists() else None
            if current != rendered.replace("\r\n", "\n"):
                stale.append(str(output.relative_to(ROOT)))
            continue
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(rendered.encode("utf-8"))
        print(f"wrote {output.relative_to(ROOT)} ({len(rendered)} bytes)")
    if stale:
        print("stale generated documents: " + ", ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
