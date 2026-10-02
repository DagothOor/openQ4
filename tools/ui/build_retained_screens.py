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
    "pause_strogg": PAK0 / "guis" / "menu" / "pause_strogg.q4ui",
    "loading": PAK0 / "guis" / "loading" / "loading.q4ui",
    "singleplayer": PAK0 / "guis" / "menu" / "singleplayer.q4ui",
    "campaigns": PAK0 / "guis" / "menu" / "campaigns.q4ui",
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
OBJECTIVE_MARK = "#B0CD6B"   # an open objective's marker (the atlas pause block)
LEVEL_STATS = "#8C947A"
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
            essential: bool | None = None, complete: str | None = None) -> str:
        """`complete` names an event the runtime runs when the timeline plays
        to its end; cancellation and a takeover of every track never complete."""
        timeline = {"id": ident, "durationMs": duration, "tracks": tracks}
        if iterations is not None:
            timeline["iterations"] = iterations
        if essential is not None:
            timeline["essential"] = essential
        if complete is not None:
            timeline["complete"] = complete
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


def rim(edge_points: list, tint: str = RIM, peak: float = 0.37, reach: float = 19.0) -> list:
    """marine.rim: 0.37 falling to nothing across 19 u outside the inner edge,
    measured from the edge (section 6). Ten nested strokes of equal alpha
    accumulate a near-linear falloff; the opaque band fill hides their inner halves."""
    paths = []
    steps = 10
    alpha = 1 - (1 - peak) ** (1 / steps)
    for index in range(steps, 0, -1):
        width = 2 * reach * U * index / steps
        paths.append(path(f"rim-{index}", edge_points, closed=False,
                          stroke=stroke(solid(rgb(tint, round(alpha, 4))), width, minimum=0, join="round")))
    return paths


def framing_bands(prefix: str, family: dict | None = None) -> list:
    """The framing bands with their rim light. `family` swaps the Marine
    silhouettes and rim for another family's (the Strogg pause)."""
    family = family or {}
    top_edge = band_edge(family.get("top", TOP_HOME), *family.get("top_ends", (89.7, 68.5)))
    bottom_edge = band_edge(family.get("bottom", BOTTOM_HOME), *family.get("bottom_ends", (421.5, 434.6)))
    lit = {key: family[key] for key in ("tint", "peak", "reach") if key in family}
    top_fill = [(edge(1), -400)] + [(edge(0), -400)] + top_edge
    bottom_fill = bottom_edge + [(edge(1), U * 480 + 400), (edge(0), U * 480 + 400)]
    top = vector(f"{prefix}-top", {**FULL, "transform": transform()},
                 rim(top_edge, **lit) + [path("band", top_fill, fill=solid([0, 0, 0, 1]))] + family.get("etched_top", []))
    bottom = vector(f"{prefix}-bottom", {**FULL, "transform": transform()},
                    rim(bottom_edge, **lit) + [path("band", bottom_fill, fill=solid([0, 0, 0, 1]))] + family.get("etched_bottom", []))
    return [top, bottom]


# --------------------------------------------------------------------- backdrop

def grid_path(opacity: float = 0.04, tint: list[float] | None = None, arm_u: float = 6.5) -> dict:
    """The `+` reticle grid: 13 u crosses on a 30 u pitch (section 2, trait 1).
    It covers views up to 21:9 (-240 to 880 u), the side-screen cap of section
    14.4; wider views keep the backdrop and bands but not the faint grid."""
    commands = []
    count = 0
    arm = arm_u * U
    for column in range(-8, 29):
        for row in range(0, 16):
            cx = vx(15 + 30 * column)
            cy = U * (15 + 30 * row)
            for (ax, ay), (bx, by) in (((-arm, 0), (arm, 0)), ((0, -arm), (0, arm))):
                commands.append({"id": f"m{count}", "op": "move", "points": [[{"fraction": 0.5, "dp": round(cx["dp"] + ax, 3)}, round(cy + ay, 3)]]})
                commands.append({"id": f"l{count}", "op": "line", "points": [[{"fraction": 0.5, "dp": round(cx["dp"] + bx, 3)}, round(cy + by, 3)]]})
                count += 1
    return {"id": "crosses", "commands": commands,
            "stroke": stroke(solid((tint or [1, 1, 1])[:3] + [opacity]), 1.0, minimum=1)}


def lit_field(prefix: str, peak: float, glow: str = GLOW, grid: dict | None = None) -> list:
    """Vignette, additive light band and reticle grid of the Marine menus;
    `glow` and `grid` give another family's light and crosses."""
    vignette = vector(f"{prefix}-vignette", dict(FULL), [path("shade", [(0, 0), ({"fraction": 1}, 0), ({"fraction": 1}, {"fraction": 1}), (0, {"fraction": 1})],
        fill=linear((0, 0), (0, {"fraction": 1}), [(0, [0, 0, 0, 0.97]), (0.3, [0, 0, 0, 0]), (0.7, [0, 0, 0, 0]), (1, [0, 0, 0, 0.97])]))])
    light = vector(f"{prefix}-light", dict(FULL), [path("band", [(0, 0), ({"fraction": 1}, 0), ({"fraction": 1}, {"fraction": 1}), (0, {"fraction": 1})],
        fill=linear((0, 0), (0, {"fraction": 1}), [(0, rgb(glow, 0)), (0.1, rgb(glow, 0)), (0.5, rgb(glow, peak)), (0.9, rgb(glow, 0)), (1, rgb(glow, 0))]),
        blend="additive")])
    grid = vector(f"{prefix}-grid", dict(FULL), [grid_path(**(grid or {}))])
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
        Hover responds at once (hover.enter 0 ms: a 1 ms step, the shortest a
        timeline can run) and focus over 80 ms; every return to rest is linear
        over 300 ms (hover.leave); press insets 1 dp over 60 ms (section 8)."""
        durations = {"default": 300, "hover": 1, "focus": 80, "pressed": 60, "disabled": 150}
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
    return vector("plinth", {**absolute(left=U * left, top=U * top, width=width, height=height), "opacity": number(1)}, [shape], [row])


def action_plate(doc: Document, ident: str, key: str, left: float, top: float, *, action: str | None = None,
                 event: str | None = None, width: float = 180, tint: str = OLIVE, hot: str = ORANGE,
                 face: str = "marine") -> dict:
    """An action button (section 6): a light plate, 35 dp visible in a 45 dp
    target, a 20 dp lower-leading cut, rails on the leading edge, cut and
    bottom, fill 0.49 fading from 33 % to nothing; 8 dp marker, Marine 20 dp."""
    band_top, band_bottom = 5.0, 40.0
    cut = 20.0
    fill = [(0, rgb(tint, 0.49)), (0.33, rgb(tint, 0.49)), (1, rgb(tint, 0))]
    rail = [(0, rgb(tint)), (0.33, rgb(tint)), (1, rgb(tint, 0))]
    plate = vector(f"{ident}-plate", {**absolute(left=0, top=0, width=width, height=45), "opacity": number(0.4)}, [
        path("fill", [(0, band_top), (width, band_top), (width, band_bottom), (cut, band_bottom), (0, band_bottom - cut)],
             fill=linear((0, 0), (width, 0), fill)),
        path("rail", [(0.75, band_top), (0.75, band_bottom - cut), (cut, band_bottom - 0.75), (width, band_bottom - 0.75)],
             closed=False, stroke=stroke(linear((0, 0), (width, 0), rail), 1.5)),
    ])
    focus = vector(f"{ident}-focus", {**absolute(left=0, top=0, width=width, height=45), "opacity": number(0)}, [
        path("inset", [(3.5, band_top + 3), (3.5, band_bottom - cut + 1.5), (cut + 1.5, band_bottom - 3.5), (width - 20, band_bottom - 3.5)],
             closed=False, stroke=stroke(solid(rgb(hot)), 1.2))])
    marker_rest = vector(f"{ident}-marker", {**absolute(left=14, top=14, width=8, height=8), "opacity": number(0.4)}, [
        marker_path("mark", 0, 0, 8, rgb(MARKER if tint == OLIVE else tint))])
    marker_hot = vector(f"{ident}-marker-hot", {**absolute(left=14, top=14, width=8, height=8), "opacity": number(0)}, [
        marker_path("mark", 0, 0, 8, rgb(hot))])
    text_node = label(f"{ident}-label", key, {**absolute(left=26, top=0, width=width - 30, height=45),
        **typeface(face, 20, 45, [1, 1, 1, 0.8]), "white-space": keyword("nowrap"), "transform": transform()})
    ids = doc.states(ident, {
        "default": [(f"{ident}-plate", "opacity", number(0.4)), (f"{ident}-marker", "opacity", number(0.4)), (f"{ident}-marker-hot", "opacity", number(0)),
                    (f"{ident}-focus", "opacity", number(0)), (f"{ident}-label", "color", colour([1, 1, 1, 0.8])), (f"{ident}-label", "transform", transform())],
        "hover": [(f"{ident}-plate", "opacity", number(0.8)), (f"{ident}-marker", "opacity", number(0)), (f"{ident}-marker-hot", "opacity", number(1)),
                  (f"{ident}-focus", "opacity", number(0)), (f"{ident}-label", "color", colour(rgb(hot))), (f"{ident}-label", "transform", transform(sx=1.03, sy=1.03))],
        "focus": [(f"{ident}-plate", "opacity", number(0.8)), (f"{ident}-marker", "opacity", number(0)), (f"{ident}-marker-hot", "opacity", number(1)),
                  (f"{ident}-focus", "opacity", number(1)), (f"{ident}-label", "color", colour(rgb(hot))), (f"{ident}-label", "transform", transform(sx=1.03, sy=1.03))],
        "pressed": [(f"{ident}-plate", "opacity", number(1)), (f"{ident}-marker", "opacity", number(0)), (f"{ident}-marker-hot", "opacity", number(1)),
                    (f"{ident}-focus", "opacity", number(1)), (f"{ident}-label", "color", colour(rgb(hot))), (f"{ident}-label", "transform", transform(tx=1, ty=1, sx=1.03, sy=1.03))],
        "disabled": [(f"{ident}-plate", "opacity", number(0.4)), (f"{ident}-marker", "opacity", number(0.4)), (f"{ident}-marker-hot", "opacity", number(0)),
                     (f"{ident}-focus", "opacity", number(0)), (f"{ident}-label", "color", colour([1, 1, 1, 0.4])), (f"{ident}-label", "transform", transform())],
    })
    control = {"role": "button", "label": key, "states": ids}
    if action:
        control["action"] = action
    else:
        control["event"] = event
    return group(ident, absolute(left=left, top=top, width=width, height=45), [plate, focus, marker_rest, marker_hot, text_node], control=control)


def outlined_label(ident: str, key: str, box: dict, style: dict, fill: list[float],
                   outline: list[float], extrude: float = 1.0) -> list:
    """Text with a thin outline drawn behind its fill (section 6, the modal
    title): eight opaque copies extruded `extrude` dp around the strokes,
    composited as one group at the outline's alpha, so the copies' overlaps
    never darken it past that. The group's own box encloses every copy,
    because its composite is clipped to that box. Returns the outline group,
    then the fill."""
    diagonal = round(extrude * math.sqrt(0.5), 4)
    offsets = [(-extrude, 0), (extrude, 0), (0, -extrude), (0, extrude),
               (-diagonal, -diagonal), (diagonal, -diagonal), (-diagonal, diagonal), (diagonal, diagonal)]
    pad = extrude + 2
    left, top = box["left"]["value"], box["top"]["value"]
    enclosing = absolute(left=left - pad, top=top - pad, width=box["width"]["value"] + 2 * pad, height=box["height"]["value"] + 2 * pad)
    copies = [label(f"{ident}-outline-{index}", key, {**box, "left": length(pad + dx), "top": length(pad + dy),
                                                      **style, "color": colour([*outline[:3], 1])})
              for index, (dx, dy) in enumerate(offsets, start=1)]
    return [group(f"{ident}-outline", {**enclosing, "opacity": number(outline[3]), "pointer-events": keyword("none")}, copies),
            label(ident, key, {**box, **style, "color": colour(fill)})]


SOFT_FOCUS_BLUR = 5 * U   # modal.softfocus: a 5 u Gaussian (section 4)
SOFT_FOCUS_SATURATION = 0.8


def confirmation(doc: Document, ident: str, title_key: str, body_key: str, yes_action: str,
                 frame_leave_ms: float = 250, dim: tuple = ()) -> dict:
    """A stock confirmation modal (section 6) over the soft-focused screen: an
    additive glow behind the 480 dp dialog, and inside it the stock popup
    art's black 0.70 silhouette, inset so a 6 dp lit margin shows beside it,
    with a leading tooth, a recessed title slot, a raised trailing section and
    a 38 dp lower-leading chamfer. The title hangs from the raised top line
    into the lit slot with a 1 dp black outline at 0.85; YES leads, NO trails.

    The screen beneath takes modal.softfocus, a 5 u blur at 0.80 saturation
    that never dims it, and the glow is cut to the dialog: graded only
    vertically, half strength at the rectangle's top and bottom edges and gone
    40 dp beyond them, fading out over a further 16 dp past each side. With
    the opaque-backing option, or where the renderer cannot soften the screen
    (ui_retainedSoftFocus is 0), the stock 0.94 marine.scrim covers it instead
    and the glow keeps the stock column, exactly the rectangle's width.

    Motion (section 8): modal.enter brings the soft focus (or the scrim), the
    glow and the frame in over 200 ms and shows the title, body and actions
    together at its end; modal.leave hides them at once and, after 50 ms,
    releases the soft focus or scrim and the glow over 250 ms and the frame
    over `frame_leave_ms` (200 ms for Exit). Completion programs show the
    contents and close the modal, so a Show during leave or a Hide during
    enter takes over the other run, which then never completes. Static bases
    are the hidden values, so the first key's retarget never flashes the
    scrim. `dim` lists (node, property, lit, dimmed) that dim over 200 ms on
    enter and return from 50 ms over 150 ms on leave, as the Exit and Mods
    modals dim the wordmark to 40% gray."""
    visible, contents = f"{ident}.visible", f"{ident}.contents"
    doc.state[visible] = {"type": "boolean", "initial": False}
    doc.state[contents] = {"type": "boolean", "initial": False}
    doc.state["soft_focus"] = {"type": "boolean", "initial": False, "cvar": "ui_retainedSoftFocus"}
    show, shown, hide, hidden = f"{ident}Show", f"{ident}Shown", f"{ident}Hide", f"{ident}Hidden"
    enter, leave = f"{ident}Enter", f"{ident}Leave"
    doc.events[show] = [{"op": "setState", "values": {visible: True, contents: False}}, {"op": "playTimeline", "timeline": enter}]
    doc.events[shown] = [{"op": "setState", "values": {contents: True}}]
    doc.events[hide] = [{"op": "setState", "values": {contents: False}}, {"op": "playTimeline", "timeline": leave}]
    doc.events[hidden] = [{"op": "setState", "values": {visible: False}}]
    width, height = 480.0, 204.0          # 320x136 u
    left = (CANVAS_W - width) / 2
    top = U * 155                           # 17 u above centre
    # popup_top/mid/btm stretch 512 texels across the rect: the art starts at
    # texel 7 and ends after 504 (6.5625 dp in from each side), its raised
    # sections start 4 of popup_top's 32 rows down (3.5625 dp) and its bottom
    # edge leaves 6 of popup_btm's 64 rows (5.34 dp). The tooth's top ends at
    # texel 14 and the slot opens to texel 388, about 73% of the width.
    inset, raised, bottom = width * 7 / 512, 3.5625, height - 5.34375
    slot_lead, slot_trail = width * 14 / 512, width * 388 / 512
    slot_depth, chamfer = 17.0, 38.0
    right = width - inset
    silhouette = path("frame", [(inset, raised), (slot_lead, raised), (slot_lead + slot_depth, raised + slot_depth),
                                (slot_trail - slot_depth, raised + slot_depth), (slot_trail, raised), (right, raised),
                                (right, bottom), (inset + chamfer, bottom), (inset, bottom - chamfer)],
                      fill=solid([0, 0, 0, 0.7]))
    whole = [(0, 0), ({"fraction": 1}, 0), ({"fraction": 1}, {"fraction": 1}), (0, {"fraction": 1})]
    glow_top, glow_bottom = -U * 87, height + U * 108
    glow = vector(f"{ident}-glow", {**absolute(left=0, top=glow_top, width=width, height=glow_bottom - glow_top), "opacity": number(0),
                                    "display": keyword("block")}, [
        path("column", whole,
             fill=linear((0, 0), (0, {"fraction": 1}), [(0, rgb(GLOW_MODAL, 0)), (0.28, rgb(GLOW_MODAL, 0.5)), (0.41, rgb(GLOW_MODAL, 0.9)),
                                                        (0.58, rgb(GLOW_MODAL, 0.9)), (0.72, rgb(GLOW_MODAL, 0.5)), (1, rgb(GLOW_MODAL, 0))]),
             blend="additive")])
    # The soft-focus glow keeps the stock column's plateau inside the rectangle
    # and grades from half strength at its edges to nothing 40 dp beyond them.
    # Its side fade is an alpha mask, so the two gradients multiply.
    reach, side = 40.0, 16.0
    plateau = [glow_top + stop * (glow_bottom - glow_top) for stop in (0.41, 0.58)]
    soft_width, soft_height = width + 2 * side, height + 2 * reach
    def soft_stop(y: float) -> float:
        return round((y + reach) / soft_height, 4)
    soft_glow = vector(f"{ident}-glow-soft", {**absolute(left=-side, top=-reach, width=soft_width, height=soft_height),
                                              "opacity": number(0), "display": keyword("none")}, [
        path("column", whole,
             fill=linear((0, 0), (0, {"fraction": 1}), [(0, rgb(GLOW_MODAL, 0)), (soft_stop(0), rgb(GLOW_MODAL, 0.5)),
                                                        (soft_stop(plateau[0]), rgb(GLOW_MODAL, 0.9)), (soft_stop(plateau[1]), rgb(GLOW_MODAL, 0.9)),
                                                        (soft_stop(height), rgb(GLOW_MODAL, 0.5)), (1, rgb(GLOW_MODAL, 0))]),
             blend="additive")],
        mask={"paths": [path("sides", whole, fill=linear((0, 0), ({"fraction": 1}, 0), [
            (0, [1, 1, 1, 0]), (round(side / soft_width, 4), [1, 1, 1, 1]), (round(1 - side / soft_width, 4), [1, 1, 1, 1]), (1, [1, 1, 1, 0])]))]})
    frame = vector(f"{ident}-frame", {**absolute(left=0, top=0, width=width, height=height), "opacity": number(0)}, [silhouette])
    # The title starts at the foot of the slot's leading flank; its capitals
    # hang from the raised top line into the lit slot, as the stock title's
    # do, its baseline 13.5 dp down where the stock one sits.
    foot = slot_lead + slot_depth
    title = outlined_label(f"{ident}-title", title_key,
                           absolute(left=round(foot, 4), top=-4, width=round(slot_trail - slot_depth - foot, 4), height=24),
                           {**typeface("marine", 20, 24, [1, 1, 1, 0.9]), "letter-spacing": length(-0.075, "em"),
                            "white-space": keyword("nowrap")}, [1, 1, 1, 0.9], [0, 0, 0, 0.85])
    # The stock body box starts 45 u down (first baseline 87.5 dp) and runs
    # to the actions at 96 u.
    body = label(f"{ident}-body", body_key, {**absolute(left=33, top=71, width=width - 66, height=73),
        **typeface("lowpixel", 17, 22, [1, 1, 1, 0.8])})
    yes = action_plate(doc, f"{ident}_yes", "#str_200157", 30, U * 96, action=yes_action)
    no = action_plate(doc, f"{ident}_no", "#str_200158", width - 33 - 180, U * 96, event=hide)
    shown_contents = group(f"{ident}-contents", {**FULL, "display": keyword("none")}, [*title, body, yes, no])
    dialog = group(f"{ident}-dialog", absolute(left=left, top=top, width=width, height=height),
                   [glow, soft_glow, frame, shown_contents])
    stage = group(f"{ident}-stage", {**absolute(top=0, width=CANVAS_W, height=720), "left": length(50, "%"),
                                     "margin-left": length(-CANVAS_W / 2)}, [dialog])
    # The soft focus is the first layer's backdrop filter, so it softens
    # everything beneath the modal; hidden, it costs no pass at all.
    softened = group(f"{ident}-softfocus", {**FULL, "display": keyword("none"), "backdrop-blur": length(0),
                                            "backdrop-saturate": number(1)})
    scrim = group(f"{ident}-scrim", {**FULL, "display": keyword("block"), "background-color": colour([0, 0, 0, 0])})
    node = group(ident, {**FULL, "display": keyword("none")}, [softened, scrim, stage],
                 modal={"initialFocus": f"{ident}_no", "back": hide})
    doc.bind(f"{ident}.display", ident, "display", {"op": "select", "args": [{"state": visible}, "block", "none"]})
    doc.bind(f"{ident}.contents", f"{ident}-contents", "display", {"op": "select", "args": [{"state": contents}, "block", "none"]})
    for part, soft in ((f"{ident}-softfocus", True), (f"{ident}-scrim", False), (f"{ident}-glow", False), (f"{ident}-glow-soft", True)):
        doc.bind(f"{part}.display", part, "display", {"op": "select", "args": [{"state": "soft_focus"}, *(("block", "none") if soft else ("none", "block"))]})
    scrim_on, scrim_off = colour([0, 0, 0, 0.94]), colour([0, 0, 0, 0])
    blur_on, blur_off = length(SOFT_FOCUS_BLUR), length(0)
    tint_on, tint_off = number(SOFT_FOCUS_SATURATION), number(1)
    glows = (f"{ident}-glow", f"{ident}-glow-soft")
    doc.timelines.add(enter, 200, [
        track(f"{ident}-scrim", "background-color", [(0, scrim_off), (200, scrim_on)]),
        track(f"{ident}-softfocus", "backdrop-blur", [(0, blur_off), (200, blur_on)]),
        track(f"{ident}-softfocus", "backdrop-saturate", [(0, tint_off), (200, tint_on)]),
        *[track(part, "opacity", [(0, number(0)), (200, number(1))]) for part in glows],
        track(f"{ident}-frame", "opacity", [(0, number(0)), (200, number(1))]),
    ] + [track(node, prop, [(0, lit), (200, dimmed)]) for node, prop, lit, dimmed in dim], complete=shown)
    frame_end = 50 + frame_leave_ms
    doc.timelines.add(leave, 300, [
        track(f"{ident}-scrim", "background-color", [(0, scrim_on), (50, scrim_on), (300, scrim_off)]),
        track(f"{ident}-softfocus", "backdrop-blur", [(0, blur_on), (50, blur_on), (300, blur_off)]),
        track(f"{ident}-softfocus", "backdrop-saturate", [(0, tint_on), (50, tint_on), (300, tint_off)]),
        *[track(part, "opacity", [(0, number(1)), (50, number(1)), (300, number(0))]) for part in glows],
        track(f"{ident}-frame", "opacity", [(0, number(1)), (50, number(1)), (frame_end, number(0))] +
              ([(300, number(0))] if frame_end < 300 else [])),
    ] + [track(node, prop, [(0, dimmed), (50, dimmed), (200, lit), (300, lit)]) for node, prop, lit, dimmed in dim],
        complete=hidden)
    return node


def prompt_bar(doc: Document, prompts: list, cap_tint: list[float] | None = None,
               verb_face: tuple = ("marine", 14, [1, 1, 1, 0.8])) -> dict:
    """The prompt bar in the bottom band's raised trailing section (section
    13.4): a keycap plate with a 45-degree cut per prompt, then its verb."""
    items = []
    for key_name, verb in prompts:
        cap = vector(f"prompt-{verb[5:]}-cap", {"position": keyword("relative"), "display": keyword("block"),
                                                "height": length(22), "margin-right": length(6), "padding-left": length(8),
                                                "padding-right": length(8)}, [
            path("cap", [(0, 0), ({"fraction": 1}, 0), ({"fraction": 1}, {"fraction": 1}), (6, {"fraction": 1}), (0, {"fraction": 1, "dp": -6})],
                 fill=solid(cap_tint or [1, 1, 1, 0.85]))],
            [label(f"prompt-{verb[5:]}-key", key_name, {"position": keyword("relative"), "display": keyword("block"),
                    **typeface("lowpixel", 13, 22, [0.04, 0.05, 0.035, 1]), "white-space": keyword("nowrap")})])
        face, size, tint = verb_face
        verb_node = label(f"prompt-{verb[5:]}-verb", verb, {"position": keyword("relative"), "display": keyword("block"),
            "margin-right": length(22), **typeface(face, size, 22, tint), "white-space": keyword("nowrap")})
        items += [cap, verb_node]
    return group("prompts", {**absolute(top=U * 447, height=22, right=U * 12), "opacity": number(1),
                             "display": keyword("flex"), "flex-direction": keyword("row"), "align-items": keyword("center")}, items)


# --------------------------------------------------------------- choreography

def band_motion(doc: Document, prefix: str, content: str, extra_home: list, quick: tuple = ()) -> None:
    """Section 8 stock choreography, sampled every presented frame:
    open        menu.fade from black over 250 ms, bands already home;
    depart      content out over 250 ms, the `quick` nodes (secondary links
                and the plinth) over 50 ms; from 50 ms frame.dock and
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
    ] + [track(node, prop, [(0, lit), (250, lit)]) for node, prop, lit, dark in lights]
      + [track(node, "opacity", [(0, number(1)), (250, number(1))]) for node in quick])
    doc.timelines.add("depart", 550, [
        track(content, "opacity", [(0, number(1)), (250, number(0)), (550, number(0))]),
        track(content, "transform", [(0, transform()), (50, transform(), ACCEL), (550, transform(640 * U, 0))]),
        track(top, "transform", [(0, home), (50, home, ACCEL), (550, page_top)]),
        track(bottom, "transform", [(0, home), (50, home, ACCEL), (550, page_bottom)]),
        track("fade", "background-color", [(0, colour([0, 0, 0, 0])), (550, colour([0, 0, 0, 0]))]),
    ] + [track(node, prop, [(0, lit), (250, dark), (550, dark)]) for node, prop, lit, dark in lights]
      + [track(node, "opacity", [(0, number(1)), (50, number(0)), (550, number(0))]) for node in quick])
    doc.timelines.add("departPopup", 200, [
        track(content, "opacity", [(0, number(1)), (150, number(0)), (200, number(0))]),
    ])
    doc.timelines.add("returnHome", 650, [
        track(top, "transform", [(0, page_top, ACCEL), (500, home), (650, home)]),
        track(bottom, "transform", [(0, page_bottom, ACCEL), (500, home), (650, home)]),
        track(content, "transform", [(0, transform()), (650, transform())]),
        track(content, "opacity", [(0, number(0)), (500, number(0)), (650, number(1))]),
        track("fade", "background-color", [(0, colour([0, 0, 0, 0])), (650, colour([0, 0, 0, 0]))]),
    ] + [track(node, prop, [(0, dark), (500, dark), (650, lit)]) for node, prop, lit, dark in lights]
      + [track(node, "opacity", [(0, number(0)), (500, number(0)), (650, number(1))]) for node in quick])


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


def title_carry(doc: Document, items: list, continue_rows: bool = False, face: str = "marine",
                tint: str = ORANGE) -> dict:
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
            track("title-carry", "color", [(0, colour(rgb(tint))), (1, colour(rgb(tint))), (50, colour(rgb(tint)), ACCEL),
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
              **typeface(face, 24, height, rgb(tint)), "white-space": keyword("nowrap"), "opacity": number(0),
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
    exit_modal = confirmation(doc, "exitModal", "#str_200169", "#str_200170", "quit", frame_leave_ms=200,
                              dim=(("wordmark", "image-color", colour([1, 1, 1, 1]), colour([0.4, 0.4, 0.4, 1])),))
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
                                      ("home-stage", "opacity", number(1), number(0))], quick=("plinth",))
    hide_carry_at_home(doc)
    return doc.build(root)


def campaign_document(campaigns: bool) -> dict:
    """Single Player page and Campaign sub-page, specification sections 8/9.

    Use the shared Marine plates and docked vector bands. Content readiness
    comes from the filesystem probe, never a module or a folder's name alone.
    """
    doc = Document("openq4.campaigns" if campaigns else "openq4.singleplayer")
    back = "campaignBack" if campaigns else "campaignHome"
    doc.session("back", back)
    doc.events["onBack"] = [{"op": "action", "action": "back"}]
    if campaigns:
        doc.state.update({"awakening_ready": {"type": "boolean", "initial": False},
                          "awakening_present": {"type": "boolean", "initial": False}})
        rows = [("quake4", "#str_230039", "campaignQuake4"),
                ("awakening", "#str_230040", "campaignAwakening")]
    else:
        rows = [("campaign", "#str_230038", "campaigns"), ("arena", "#str_42002", "campaignArena")]
    buttons = []
    for ident, key, action in rows:
        doc.session(action, action)
        buttons.append(navigation_plate(doc, ident, key, action=action))
    if campaigns:
        doc.bind("awakening.enabled", "awakening", "enabled", {"state": "awakening_ready"})
    buttons.append(navigation_plate(doc, "back", "#str_230045", action="back"))
    details = []
    if campaigns:
        for ident, key in [("available", "#str_230041"), ("partial", "#str_230042"), ("absent", "#str_230043")]:
            details.append(label(ident, key, {**absolute(left=0, top=0, width=U * 210, height=U * 140),
                                            "display": keyword("none"),
                                            **typeface("lowpixel", 18, 26, rgb(OLIVE))}))
        doc.bind("available.display", "available", "display", {"op": "select", "args": [{"state": "awakening_ready"}, "block", "none"]})
        for ident, partial in [("partial", True), ("absent", False)]:
            doc.bind(ident + ".display", ident, "display", {"op": "select", "args": [
                {"state": "awakening_ready"}, "none", {"op": "select", "args": [
                    {"state": "awakening_present"}, "block" if partial else "none", "none" if partial else "block"]}]})
    else:
        details.append(label("description", "#str_230044", {**absolute(left=0, top=0, width=U * 210, height=U * 140),
                                                           **typeface("lowpixel", 18, 26, rgb(OLIVE))}))
    bands = framing_bands("band")
    bands[0]["properties"]["transform"] = transform(*TOP_TO_PAGE)
    bands[1]["properties"]["transform"] = transform(*BOTTOM_TO_PAGE)
    content = group("content", {**absolute(top=0, width=CANVAS_W, height=720), "left": length(50, "%"), "margin-left": length(-CANVAS_W / 2)}, [
        label("title", "#str_230038" if campaigns else "#str_42000", {**absolute(left=U * 44, top=U * 54, width=U * 550, height=U * 38),
                         **typeface("marine", 36, 44, rgb(ORANGE))}),
        group("navigation", {**absolute(left=0, top=U * 190, width=U * 357), "display": keyword("flex"), "flex-direction": keyword("column")}, buttons),
        group("details", absolute(left=U * 395, top=U * 190, width=U * 210, height=U * 140), details),
    ])
    return doc.build(group("screen", {**FULL, "background-color": colour([0, 0, 0, 1])}, [
        *lit_field("field", 0.7), *bands, content,
        prompt_bar(doc, [("#str_107019", "#str_200747"), ("#str_107020", "#str_230045")]),
    ]))


# ------------------------------------------------------------------- the pause

OBJECTIVE_ROWS = 3   # the stock objective screen's three slots


def level_row_bindings(doc: Document, ident: str, index: int, text_nodes: tuple) -> dict:
    """A level block row shows the objectives with their state (section
    13.7): the open ones first, newest first, then the ones completed on
    this map, newest first, behind a check. Returns the expression that is
    true while the row holds a completed objective."""
    held = {"state": "pause_objective_count"}
    text = {"state": f"pause_objective_{index}"}
    tail = ""
    for count in range(0, index + 1):
        tail = {"op": "select", "args": [{"op": "==", "args": [held, count]}, {"state": f"pause_completed_{index - count}"}, tail]}
    text = {"op": "select", "args": [{"op": ">", "args": [held, index]}, text, tail]}
    for node in text_nodes:
        doc.bind(f"{node}.text", node, "text", text)
    rows = {"op": "+", "args": [held, {"state": "pause_completed_count"}]}
    doc.bind(f"{ident}.display", ident, "display", {"op": "select", "args": [{"op": ">", "args": [rows, index]}, "block", "none"]})
    completed = {"op": "<=", "args": [held, index]}
    doc.bind(f"{ident}-mark.display", f"{ident}-mark", "display", {"op": "select", "args": [completed, "none", "block"]})
    doc.bind(f"{ident}-check.display", f"{ident}-check", "display", {"op": "select", "args": [completed, "block", "none"]})
    return completed


def level_check(ident: str, tint: list[float]) -> dict:
    """A completed objective's check (the atlas level block)."""
    return vector(f"{ident}-check", {**absolute(left=15, top=2, width=12, height=11), "display": keyword("none")}, [
        path("check", [(0, 6), (3.6, 9.9), (10.5, 1.8)], closed=False, stroke=stroke(solid(tint), 2.1, join="round", cap="round"))])


def level_block(doc: Document) -> dict:
    """The current level block in the emblem's place (section 13.7): a card
    (section 6: black 0.94 in a marine.rail.card rail, 12 and 3 dp cuts, a
    40 dp header) with the levelshot in a picture frame, the level, the
    difficulty, the objectives the player holds and the time in the mission.
    The game publishes the objectives, newest first; a map's own objectives
    summary stands in while it publishes none."""
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
    rows_top, row_h, stats_rule = below + 76, U * 12.5, h - U * 22
    objectives = label("level-objectives", "#str_230030", {**absolute(left=15, top=rows_top, width=pw, height=stats_rule - rows_top - 3),
        **typeface("lowpixel", 14, 18, [0.82, 0.87, 0.71, 1]), "overflow": keyword("hidden"), "display": keyword("block")})
    # Each objective with its state: an open one behind the atlas marker,
    # its title white 0.9; a completed one behind a check at 0.5.
    rows = []
    for index in range(OBJECTIVE_ROWS):
        ident = f"level-objective-{index}"
        mark = vector(f"{ident}-mark", {**absolute(left=15, top=4, width=9, height=9), "display": keyword("block")},
                      [path("mark", [(0, 0), (9, 0), (0, 9)], fill=solid(rgb(OBJECTIVE_MARK, 0.4)))])
        title = label(f"{ident}-text", "#str_230030", {**absolute(left=33, top=0, width=pw - 18, height=row_h),
            **typeface("lowpixel", 13, row_h, [1, 1, 1, 0.9]), "white-space": keyword("nowrap"), "overflow": keyword("hidden")})
        rows.append(group(ident, {**absolute(left=0, top=rows_top + index * row_h, width=w, height=row_h), "display": keyword("none")},
                          [mark, level_check(ident, rgb("#B5C784")), title]))
        completed = level_row_bindings(doc, ident, index, (f"{ident}-text",))
        doc.bind(f"{ident}-text.color", f"{ident}-text", "color", [1, 1, 1, {"op": "select", "args": [completed, 0.5, 0.9]}])
    # The time in the mission under a faint rule at the foot of the card.
    rule = vector("level-stats-rule", {**absolute(left=15, top=stats_rule, width=pw, height=1), "display": keyword("none")},
                  [path("rule", [(0, 0.5), (pw, 0.5)], closed=False, stroke=stroke(solid([1, 1, 1, 0.1]), 1))])
    stats = label("level-stats", "#str_230030", {**absolute(left=15, top=h - U * 20, width=pw, height=U * 14),
        **typeface("lowpixel", 11, U * 14, rgb(LEVEL_STATS)), "white-space": keyword("nowrap")})
    doc.bind("level-stats.text", "level-stats", "text", {"state": "pause_stats"})
    doc.bind("level-stats-rule.display", "level-stats-rule", "display",
             {"op": "select", "args": [{"op": "==", "args": [{"state": "pause_stats"}, ""]}, "none", "block"]})
    doc.bind("level-shot.image", "level-shot", "image", {"state": "pause_shot"})
    doc.bind("level-name.text", "level-name", "text", {"state": "pause_level"})
    doc.bind("level-detail.text", "level-detail", "text", {"state": "pause_detail"})
    doc.bind("level-objectives.text", "level-objectives", "text", {"state": "pause_objectives"})
    published = {"op": ">", "args": [{"op": "+", "args": [{"state": "pause_objective_count"}, {"state": "pause_completed_count"}]}, 0]}
    doc.bind("level-objectives.display", "level-objectives", "display", {"op": "select", "args": [published, "none", "block"]})
    # A map without objectives shows no empty heading.
    doc.bind("level-objectives-head.display", "level-objectives-head", "display",
             {"op": "select", "args": [{"op": "||", "args": [published, {"op": "!=", "args": [{"state": "pause_objectives"}, ""]}]},
                                       "block", "none"]})
    return group("level-block", absolute(left=x, top=y, width=w, height=h),
                 [frame, shot, shot_frame, heading, name, detail, objectives_head, objectives, *rows, rule, stats])


# ----------------------------------------------------------- the Strogg pause

# After Kane's stroggification the pause menu takes the Strogg family
# (section 13.7, the hud_strogg row of section 3 and the atlas Strogg pause).
ST_READ = "#FCFFC8"      # R_Strogg labels and readouts
ST_SELECT = "#FFCC00"    # focus, and the rune copies
ST_LINE = "#F59512"      # rails, rim light, circuit traces and markers
ST_FILL = "#FF9000"      # the card header's wash
ST_BAR = "#FF8000"       # the credits scan bar (section 8)
ST_LIGHT = "#6B2A0E"     # the backdrop's additive light band
ST_GRID = "#FFB060"      # the reticle crosses
ST_PLINTH = "#4A2410"
ST_CARD = "#0A0503"
ST_STATS = "#C9A27A"

# The Marine frame with 30-degree shoulders and downward teeth in place of
# the 45-degree notches, at home, as TOP_HOME and BOTTOM_HOME.
STROGG_TOP = [(-300, 92), (-283, 102), (24, 102), (41, 112), (86, 112), (103, 102), (150, 102), (167, 112), (212, 112),
              (229, 102), (308, 102), (327, 91), (334, 91), (352, 66), (520, 66), (537, 76), (578, 76), (595, 66)]
STROGG_BOTTOM = [(-240, 424), (-223, 434), (-26, 434), (-8, 424), (0, 400), (334, 400), (351, 410), (372, 410),
                 (394, 444), (580, 444), (597, 434)]
# The circuit traces etched in the bands, with their junction dots.
STROGG_TRACES_TOP = ([[(-300, 40), (40, 40), (60, 58), (250, 58)], [(380, 24), (520, 24), (538, 40), (700, 40)]],
                     [(40, 40), (250, 58), (520, 24), (700, 40)])
STROGG_TRACES_BOTTOM = ([[(-200, 460), (120, 460), (140, 448), (300, 448)], [(420, 470), (560, 470), (578, 458), (760, 458)]],
                        [(120, 460), (300, 448), (560, 470)])

# Every Strogg label exists twice on one baseline, in runes and in R_Strogg,
# so it can translate (section 8; section 14.6 gives the runes 1.2 times the
# R_Strogg cap height). Both faces are scaled by their whole height, ascent
# plus descent: the shipped R_Strogg face puts its caps at 0.519 of the size
# and its baseline 0.800 down; the rune face 0.765 and 0.988.
RSTROGG_CAP, RSTROGG_ASCENT = 1329 / 2560, 2048 / 2560
RUNE_CAP, RUNE_ASCENT = 1427 / 1866, 1843 / 1866
RUNE_SCALE = 1.2 * RSTROGG_CAP / RUNE_CAP
SCAN_LENGTH = 150 * U     # the credits scan bar: 150 u, its head about 12 u past the line


def rune_rise(size: float) -> float:
    """How far the rune copy's box rises so the baselines meet: a line box
    puts each face's baseline half its leading plus its ascent down."""
    return size * RUNE_SCALE * (RUNE_ASCENT - 0.5) - size * (RSTROGG_ASCENT - 0.5)


def circle_commands(prefix: str, cx, cy, r: float) -> list:
    """A circle as four cubic quarter arcs, centered on canvas coordinates."""
    k = 0.5523 * r
    def at(dx, dy):
        return point({**cx, "dp": round(cx["dp"] + dx, 3)}, round(cy + dy, 3))
    return [{"id": f"{prefix}m", "op": "move", "points": [at(r, 0)]},
            {"id": f"{prefix}a", "op": "cubic", "points": [at(r, k), at(k, r), at(0, r)]},
            {"id": f"{prefix}b", "op": "cubic", "points": [at(-k, r), at(-r, k), at(-r, 0)]},
            {"id": f"{prefix}c", "op": "cubic", "points": [at(-r, -k), at(-k, -r), at(0, -r)]},
            {"id": f"{prefix}d", "op": "cubic", "points": [at(k, -r), at(r, -k), at(r, 0)]},
            {"id": f"{prefix}z", "op": "close"}]


def circuit_traces(traces: tuple) -> list:
    """The Strogg bands' etched circuit: #F59512 at 0.32, 0.8 u lines with
    1.6 u junction dots (the atlas)."""
    lines, dots = traces
    paint = rgb(ST_LINE, 0.32)
    result = [path(f"trace-{index}", [(vx(x), U * y) for x, y in points], closed=False,
                   stroke=stroke(solid(paint), U * 0.8, minimum=1)) for index, points in enumerate(lines)]
    commands = []
    for index, (x, y) in enumerate(dots):
        commands += circle_commands(f"d{index}", vx(x), U * y, U * 1.6)
    result.append({"id": "trace-dots", "commands": commands, "fill": solid(paint)})
    return result


STROGG_BANDS = {
    "top": STROGG_TOP, "top_ends": (92, 66), "bottom": STROGG_BOTTOM, "bottom_ends": (424, 434),
    # The atlas draws the Strogg rim as a thinner, brighter line than the
    # Marine one: #F59512, held close to the edge.
    "tint": ST_LINE, "peak": 0.34, "reach": 11.0,
    "etched_top": circuit_traces(STROGG_TRACES_TOP), "etched_bottom": circuit_traces(STROGG_TRACES_BOTTOM),
}


def scan_bar(ident: str, height: float, props: dict) -> dict:
    """The credits scan bar (section 8): an additive #FF8000 ramp that
    brightens linearly to a rounded head, with soft top and bottom edges.
    Its head is the node's trailing edge; it reaches SCAN_LENGTH back. The
    bar slides by its right inset, a percentage of the label's wrapper: from
    100% (the head at the wrapper's leading edge, where the bar starts in the
    atlas) to 0% (12 u past the label), so it sweeps any label whole."""
    def capsule(name: str, half: float, k: float, alphas: list) -> dict:
        a, c = half * k, 0.5523
        head, tail = {"fraction": 1}, {"fraction": 1, "dp": -SCAN_LENGTH}
        def x(dp):
            return {"fraction": 1, "dp": round(dp, 3)}
        def y(dp):
            return {"fraction": 0.5, "dp": round(dp, 3)}
        commands = [{"id": "m", "op": "move", "points": [[tail, y(-half)]]},
                    {"id": "top", "op": "line", "points": [[x(-a), y(-half)]]},
                    {"id": "h1", "op": "cubic", "points": [[x(-a + a * c), y(-half)], [head, y(-half * c)], [head, y(0)]]},
                    {"id": "h2", "op": "cubic", "points": [[head, y(half * c)], [x(-a + a * c), y(half)], [x(-a), y(half)]]},
                    {"id": "bottom", "op": "line", "points": [[tail, y(half)]]},
                    {"id": "close", "op": "close"}]
        stops = [(at, rgb(ST_BAR, round(alpha, 4))) for at, alpha in alphas]
        return {"id": name, "commands": commands, "fill": linear((tail, 0), (head, 0), stops), "blend": "additive"}
    ramp = [(0, 0), (0.25, 0.24), (0.5, 0.55), (0.75, 0.84), (0.9, 0.96), (0.955, 1), (1, 0.7)]
    soft = capsule("edge", height / 2, 0.6, [(at, alpha * 0.55) for at, alpha in ramp])
    core = capsule("core", height * 0.29, 0.9, ramp)
    return vector(ident, {**props, "right": length(0, "%"), "opacity": number(0)}, [soft, core])


class Translation:
    """The short credits translation of the Strogg pause (sections 8 and
    13.7): every line arrives in runes at 0.80, then cross-fades into
    R_Strogg while both copies pop 6% larger and settle. Headings and names
    arrive white and settle to their color 60 ms later over 150 ms. A line
    whose base is a control's label fades through its wrapper's opacity, so
    the control's own feedback keeps the label's color."""
    POP = 1.06

    def __init__(self):
        self.lines: list[tuple] = []
        self.bars: list[tuple] = []

    def add(self, prefix: str, delay: float, duration: float, *, rest: list[float] | None = None,
            white: bool = False, width: float | None = None, runes: bool = True) -> None:
        """`rest` is the label's color for a color fade; without it the
        `<prefix>-latin` wrapper fades. `width` keeps a fixed box's leading
        edge in place as it pops. A line without `runes` has no rune copy
        and only fades in."""
        self.lines.append((prefix, delay, duration, rest, white, width, runes))

    def bar(self, ident: str, delay: float, slide: float) -> None:
        self.bars.append((ident, delay, slide))

    @staticmethod
    def pop(scale: float, width: float | None) -> dict:
        return transform(tx=(scale - 1) * width / 2 if width else 0, sx=scale, sy=scale)

    def tracks(self, offset: float) -> tuple:
        """The tracks with every line offset by `offset` ms, and their end."""
        result, end = [], 0.0

        def keys(start, value_from, value_to, length):
            # A play retargets the first key to the current value; the 1 ms
            # key puts the line back in runes before its own start.
            steps = [(0, value_from), (1, value_from)]
            if start > 1:
                steps.append((start, value_from))
            steps.append((max(start, 1) + length, value_to))
            return steps

        for prefix, delay, duration, rest, white, width, has_runes in self.lines:
            start = offset + delay
            hidden = [*rgb(ST_SELECT)[:3], 0]
            runes = [*rgb(ST_SELECT)[:3], 0.8]
            if has_runes:
                result.append(track(f"{prefix}-rune", "color", [(at, colour(value)) for at, value in
                                                                 keys(start, runes, hidden, duration)]))
                result.append(track(f"{prefix}-rune", "transform", [(at, value) for at, value in
                                                                     keys(start, self.pop(self.POP, width), transform(), duration)]))
            latin = f"{prefix}-latin" if rest is None else prefix
            if has_runes:
                pop = self.pop(1 + (self.POP - 1) * 0.9, width)
                result.append(track(latin, "transform", [(at, value) for at, value in keys(start, pop, transform(), duration)]))
            finish = max(start, 1) + duration
            if rest is None:
                result.append(track(latin, "opacity", [(at, number(value)) for at, value in keys(start, 0, 1, duration)]))
            elif white:
                steps = [(at, colour(value)) for at, value in keys(start, [1, 1, 1, 0], [1, 1, 1, 1], duration)]
                steps += [(finish + 60, colour([1, 1, 1, 1])), (finish + 210, colour(rest))]
                result.append(track(latin, "color", steps))
                finish += 210
            else:
                result.append(track(latin, "color", [(at, colour(value)) for at, value in
                                                     keys(start, [*rest[:3], 0], rest, duration)]))
            end = max(end, finish)
        for ident, delay, slide in self.bars:
            start = offset + delay
            # The bar slides in from the leading edge over `slide` ms,
            # accel(0.4, 0.6), and dims to nothing over 3.33 times as long
            # (section 8).
            dim = round(slide * 10 / 3)
            parked, rested = length(100, "%"), length(0, "%")
            result.append(track(ident, "right", [(0, parked), (1, parked), *([(start, parked, ACCEL_LATE)] if start > 1 else []),
                                                 (max(start, 1) + slide, rested)]))
            # It lights only as it starts to slide, never while parked.
            assert start > 1
            result.append(track(ident, "opacity", [(0, number(0)), (1, number(0)), (start, number(0)), (start + 1, number(1)),
                                                   (start + dim, number(0))]))
            end = max(end, max(start, 1) + dim)
        return result, end

    def finish(self, doc: Document) -> None:
        """`translate` runs with `open`; `translateReturn` waits the 500 ms a
        page's return takes before the home content shows (section 8). The
        events replace the timelines of the same names, so the session's
        open and returnHome play both. Neither is essential: reduced motion
        shows the translated labels at once."""
        for ident, offset in (("translate", 0), ("translateReturn", 500)):
            tracks, end = self.tracks(offset)
            doc.timelines.add(ident, end, tracks)
        doc.events["open"] = [{"op": "playTimeline", "timeline": "open"}, {"op": "playTimeline", "timeline": "translate"}]
        doc.events["returnHome"] = [{"op": "playTimeline", "timeline": "returnHome"},
                                    {"op": "playTimeline", "timeline": "translateReturn"}]


# accel(120, 180) of the credits scan bar: accelerating over 40% of the slide.
ACCEL_LATE = [0.4, 0.0, 0.45, 1.0]


def strogg_text(ident: str, key: str, box: dict, size: float, line: float, tint: list[float], **extra) -> list:
    """An R_Strogg label and its rune copy on the same baseline. Both rest
    translated: the rune copy transparent, the label in `tint`; the
    translation's 1 ms keys put them back in runes when it plays."""
    latin = label(ident, key, {**box, **typeface("r_strogg", size, line, tint), "white-space": keyword("nowrap"),
                               "transform": transform(), **extra})
    rune_box = dict(box)
    rune_box["top"] = length(box["top"]["value"] - rune_rise(size))
    rune = label(f"{ident}-rune", key, {**rune_box, **typeface("strogg", round(size * RUNE_SCALE, 3), line, [*rgb(ST_SELECT)[:3], 0]),
                                        "white-space": keyword("nowrap"), "transform": transform(), "pointer-events": keyword("none"), **extra})
    return [rune, latin]


def strogg_navigation_plate(doc: Document, ident: str, key: str, translation: Translation, index: int, *,
                            action: str | None = None, event: str | None = None) -> dict:
    """A Strogg navigation plate (section 13.7 and the atlas): the Marine
    plate's bleed off the leading edge, ending in a 30-degree shoulder at
    357 u, the end of its target. The #F59512 rail runs along its foot, up
    its trailing edge and back over the shoulder; the slanted marker turns
    #FFCC00 with the label on focus, and the focused plate runs the credits
    scan bar under its label. The label arrives in runes and translates
    120 + 45 ms per row after the menu opens, over 200 ms."""
    lead = NAV_LEAD
    width = lead + 357 * U
    x0 = lead
    top, bottom = U * 2.8, U * 27.2
    end, shoulder, foot = x0 + 357 * U, x0 + 341 * U, U * 12
    fade = [(0, [0, 0, 0, 1]), (0.44, [0, 0, 0, 1]), (0.62, [0, 0, 0, 0.5]), (0.88, [0, 0, 0, 0]), (1, [0, 0, 0, 0])]
    rail = [(0, rgb(ST_LINE, 0.9)), (0.55, rgb(ST_LINE, 0.9)), (1, rgb(ST_LINE, 0.45))]
    plate = vector(f"{ident}-plate", {**absolute(left=0, top=0, width=width, height=45), "opacity": number(0.4)}, [
        path("fill", [(0, top), (shoulder, top), (end, foot), (end, bottom), (0, bottom)],
             fill=linear((x0, 0), (end, 0), fade)),
        path("rail", [(0, bottom - 0.75), (end - 0.75, bottom - 0.75), (end - 0.75, foot), (shoulder, top + 0.75),
                      (x0 + 285 * U, top + 0.75)], closed=False, stroke=stroke(linear((x0, 0), (end, 0), rail), 1.5)),
    ])
    focus = vector(f"{ident}-focus", {**absolute(left=0, top=0, width=width, height=45), "opacity": number(0)}, [
        path("inset", [(0, bottom - 3.2), (x0 + 348, bottom - 3.2)], closed=False, stroke=stroke(solid(rgb(ST_SELECT)), 1.2))])

    def slanted(tint: list[float]) -> dict:
        # A parallelogram 6 u wide, slanted as the atlas draws it.
        mx, my = x0 + U * 36.4, U * 11.8
        return path("mark", [(mx, my), (mx + U * 6, my), (mx + U * 4.4, my + U * 6), (mx - U * 1.6, my + U * 6)], fill=solid(tint))
    marker_rest = vector(f"{ident}-marker", {**absolute(left=0, top=0, width=width, height=45), "opacity": number(0.4)},
                         [slanted(rgb(ST_LINE))])
    marker_hot = vector(f"{ident}-marker-hot", {**absolute(left=0, top=0, width=width, height=45), "opacity": number(0)},
                        [slanted(rgb(ST_SELECT))])
    # The label's wrapper fits the label, so the scan bar's head can rest
    # 12 u past it whatever the language; it starts at 30 u, as the bar does.
    size = 24.0
    line_height = bottom - top
    text_node = label(f"{ident}-label", key, {"position": keyword("relative"), "display": keyword("block"),
                                              **typeface("r_strogg", size, line_height, rgb(ST_READ, 0.8)),
                                              "white-space": keyword("nowrap"), "transform": transform()})
    latin = group(f"{ident}-latin", {"position": keyword("relative"), "display": keyword("block"), "margin-left": length(U * 14),
                                     "margin-right": length(U * 12), "opacity": number(1), "transform": transform()}, [text_node])
    rune = label(f"{ident}-rune", key, {**absolute(left=U * 14, top=-rune_rise(size)),
                                        **typeface("strogg", round(size * RUNE_SCALE, 3), line_height, [*rgb(ST_SELECT)[:3], 0]),
                                        "white-space": keyword("nowrap"), "transform": transform(), "pointer-events": keyword("none")})
    bar = scan_bar(f"{ident}-scan", U * 15, {**absolute(left=0, top=0, height=line_height), "right": length(0),
                                             "pointer-events": keyword("none")})
    fit = group(f"{ident}-fit", {**absolute(left=x0 + U * 30, top=top, height=line_height)}, [bar, rune, latin])
    translation.add(ident, 120 + 45 * index, 200)
    slide = 300
    bar_rest, bar_start = length(0, "%"), length(100, "%")
    # Focus (and hover) slide the bar in from the leading edge over 300 ms,
    # accel(0.4, 0.6), and dim it over 1000 ms; any other state lets it go
    # over its own duration.
    run_bar = [(f"{ident}-scan", "right", [(0, bar_start), (1, bar_start, ACCEL_LATE), (1 + slide, bar_rest), (1000, bar_rest)]),
               (f"{ident}-scan", "opacity", [(0, number(1)), (1, number(1)), (1000, number(0))])]
    def settle(duration: float, alpha: float) -> list:
        return [(f"{ident}-scan", "right", [(0, bar_rest), (duration, bar_rest)]),
                (f"{ident}-scan", "opacity", [(0, number(alpha)), (duration, number(alpha))])]
    ids = doc.states(ident, {
        "default": [(f"{ident}-plate", "opacity", number(0.4)), (f"{ident}-marker", "opacity", number(0.4)),
                    (f"{ident}-marker-hot", "opacity", number(0)), (f"{ident}-focus", "opacity", number(0)),
                    (f"{ident}-label", "color", colour(rgb(ST_READ, 0.8))), (f"{ident}-label", "transform", transform())],
        "hover": [(f"{ident}-plate", "opacity", number(0.8)), (f"{ident}-marker", "opacity", number(0)),
                  (f"{ident}-marker-hot", "opacity", number(1)), (f"{ident}-focus", "opacity", number(0)),
                  (f"{ident}-label", "color", colour(rgb(ST_SELECT))), (f"{ident}-label", "transform", transform(sx=1.03, sy=1.03))],
        "focus": [(f"{ident}-plate", "opacity", number(0.8)), (f"{ident}-marker", "opacity", number(0)),
                  (f"{ident}-marker-hot", "opacity", number(1)), (f"{ident}-focus", "opacity", number(1)),
                  (f"{ident}-label", "color", colour(rgb(ST_SELECT))), (f"{ident}-label", "transform", transform(sx=1.03, sy=1.03))],
        "pressed": [(f"{ident}-plate", "opacity", number(1)), (f"{ident}-marker", "opacity", number(0)),
                    (f"{ident}-marker-hot", "opacity", number(1)), (f"{ident}-focus", "opacity", number(1)),
                    (f"{ident}-label", "color", colour(rgb(ST_SELECT))), (f"{ident}-label", "transform", transform(tx=1, ty=1, sx=1.03, sy=1.03))],
        "disabled": [(f"{ident}-plate", "opacity", number(0.4)), (f"{ident}-marker", "opacity", number(0.4)),
                     (f"{ident}-marker-hot", "opacity", number(0)), (f"{ident}-focus", "opacity", number(0)),
                     (f"{ident}-label", "color", colour(rgb(ST_READ, 0.4))), (f"{ident}-label", "transform", transform())],
    })
    extra = {"default": settle(300, 0), "hover": run_bar, "focus": run_bar, "pressed": settle(60, 1), "disabled": settle(150, 0)}
    for timeline in doc.timelines.items:
        state = timeline["id"][len(ident) + 1:]
        if timeline["id"].startswith(ident + ".") and state in extra:
            for node, prop, keys in extra[state]:
                timeline["tracks"].append(track(node, prop, keys))
            timeline["durationMs"] = max(timeline["durationMs"], max(key[0] for _, _, keys in extra[state] for key in keys))
    control = {"role": "button", "label": key, "states": ids}
    if action:
        control["action"] = action
    else:
        control["event"] = event
    return group(ident, {"position": keyword("relative"), "display": keyword("block"),
                         "margin-left": length(-lead), "width": length(width), "height": length(30 * U)},
                 [plate, focus, marker_rest, marker_hot, fit], control=control)


def strogg_link(doc: Document, ident: str, key: str, translation: Translation, delay: float, *, event: str) -> dict:
    """EXIT on the Strogg plinth: R_Strogg 16 dp at 0.50 behind the slanted
    marker; hover and focus turn both #FFCC00. It arrives in runes and
    translates at `delay` over 200 ms, after the navigation."""
    def slanted(name: str, tint: list[float], alpha: float) -> dict:
        return vector(name, {**absolute(left=0, top=0, width=U * 7, height=U * 17), "opacity": number(alpha)}, [
            path("mark", [(U * 1.2, U * 7.25), (U * 5.7, U * 7.25), (U * 4.5, U * 11.75), (0, U * 11.75)], fill=solid(tint))])
    marker, hot = slanted(f"{ident}-marker", rgb(ST_LINE), 0.4), slanted(f"{ident}-marker-hot", rgb(ST_SELECT), 0)
    text_node = label(f"{ident}-label", key, {"position": keyword("relative"), "display": keyword("block"),
        **typeface("r_strogg", 16, U * 17, rgb(ST_READ, 0.5)), "white-space": keyword("nowrap")})
    latin = group(f"{ident}-latin", {"position": keyword("relative"), "display": keyword("block"), "margin-left": length(U * 7),
                                     "opacity": number(1), "transform": transform()}, [text_node])
    rune = label(f"{ident}-rune", key, {**absolute(left=U * 7, top=-rune_rise(16)),
                                        **typeface("strogg", round(16 * RUNE_SCALE, 3), U * 17, [*rgb(ST_SELECT)[:3], 0]),
                                        "white-space": keyword("nowrap"), "transform": transform(), "pointer-events": keyword("none")})
    translation.add(ident, delay, 200)
    rest, lit = colour(rgb(ST_READ, 0.5)), colour(rgb(ST_SELECT))
    ids = doc.states(ident, {
        "default": [(f"{ident}-marker", "opacity", number(0.4)), (f"{ident}-marker-hot", "opacity", number(0)), (f"{ident}-label", "color", rest)],
        "hover": [(f"{ident}-marker", "opacity", number(0)), (f"{ident}-marker-hot", "opacity", number(1)), (f"{ident}-label", "color", lit)],
        "focus": [(f"{ident}-marker", "opacity", number(0)), (f"{ident}-marker-hot", "opacity", number(1)), (f"{ident}-label", "color", lit)],
        "pressed": [(f"{ident}-marker", "opacity", number(0)), (f"{ident}-marker-hot", "opacity", number(1)),
                    (f"{ident}-label", "color", colour(rgb(ST_READ)))],
        "disabled": [(f"{ident}-marker", "opacity", number(0.4)), (f"{ident}-marker-hot", "opacity", number(0)),
                     (f"{ident}-label", "color", colour(rgb(ST_READ, 0.25)))],
    })
    return group(ident, {"position": keyword("relative"), "display": keyword("block"), "height": length(U * 17),
                         "margin-right": length(U * 14)}, [marker, hot, rune, latin],
                 control={"role": "button", "label": key, "states": ids, "event": event})


def strogg_plinth(links: list) -> dict:
    """The plinth in #4A2410 at 0.30 with the Strogg shoulder at its
    trailing end and a steeper leading cut (the atlas)."""
    left, right, top, bottom = 24.0, 361.2, 403.3, 422.1
    width, height = U * (right - left), U * (bottom - top)
    shape = path("plinth", [(0, 0), (width - U * 10.7, 0), (width, U * 12.5), (width, height), (U * 7.2, height), (0, height - U * 6.3)],
                 fill=solid(rgb(ST_PLINTH, 0.3)))
    row = group("plinth-links", {**absolute(left=U * (32 - left), top=U * -0.3, height=U * 17),
                                  "display": keyword("flex"), "flex-direction": keyword("row"),
                                  "align-items": keyword("flex-start")}, links)
    return vector("plinth", {**absolute(left=U * left, top=U * top, width=width, height=height), "opacity": number(1)}, [shape], [row])


def strogg_level_block(doc: Document, translation: Translation, start: float) -> dict:
    """The Strogg level block (section 13.7): the Marine block's content in a
    chamfered card (10 u at every corner, #0A0503 at 0.94 in a #F59512 rail
    at 0.75) under the stock HUD grain, the header washed #FF9000, the
    levelshot chamfered in an orange frame, and every line in R_Strogg,
    translating from runes after the actions from `start` ms."""
    x, y, w, h = U * 374, U * 118, U * 262, U * 270
    cut, header = U * 10, 40.0
    card = [(cut, 0), (w - cut, 0), (w, cut), (w, h - cut), (w - cut, h), (cut, h), (0, h - cut), (0, cut)]
    frame = vector("level-card", absolute(left=0, top=0, width=w, height=h), [
        path("body", card, fill=solid(rgb(ST_CARD, 0.94))),
        path("wash", [(cut + 0.75, 0.75), (w - cut - 0.75, 0.75), (w - 0.75, cut + 0.75), (w - 0.75, header), (0.75, header), (0.75, cut + 0.75)],
             fill=linear((0, 0), (w, 0), [(0, rgb(ST_FILL, 0.16)), (0.5, rgb(ST_FILL, 0.1)), (1, [1, 1, 1, 0])])),
        path("rule", [(0, header), (w, header)], closed=False, stroke=stroke(solid(rgb(ST_LINE, 0.5)), 1)),
        path("rail", card, stroke=stroke(solid(rgb(ST_LINE, 0.75)), 1.5)),
        path("mark", [(U * 12, U * 9.8), (U * 18, U * 9.8), (U * 16.4, U * 16.2), (U * 10.4, U * 16.2)], fill=solid(rgb(ST_LINE))),
    ])
    # The masked grain: the stock Strogg HUD static (s_static), added warm and
    # faint in tiles of its own 128 texels, inside the chamfers.
    inset, tile = cut / 2, 128.0
    tiles = []
    columns, rows_needed = math.ceil((w - 2 * inset) / tile), math.ceil((h - 2 * inset) / tile)
    for row in range(rows_needed):
        for column in range(columns):
            tiles.append(picture(f"level-grain-{row}-{column}", "gfx/guis/hud/s_static",
                                 {**absolute(left=column * tile, top=row * tile, width=tile, height=tile),
                                  "image-blend": keyword("additive"), "image-color": colour([1, 0.75, 0.4, 0.14])}, fit="fill"))
    grain = group("level-grain", {**absolute(left=inset, top=inset, width=w - 2 * inset, height=h - 2 * inset),
                                  "overflow": keyword("hidden"), "pointer-events": keyword("none")}, tiles)
    pw, ph = w - 30, U * 118
    px, py, chamfer = 15, header + 12, U * 6
    shot = picture("level-shot", "", {**absolute(left=px, top=py, width=pw, height=ph)})
    corners = vector("level-shot-frame", absolute(left=px, top=py, width=pw, height=ph), [
        path("lead", [(0, 0), (chamfer, 0), (0, chamfer)], fill=solid(rgb(ST_CARD))),
        path("trail", [({"fraction": 1}, {"fraction": 1, "dp": -chamfer}), ({"fraction": 1}, {"fraction": 1}),
                       ({"fraction": 1, "dp": -chamfer}, {"fraction": 1})], fill=solid(rgb(ST_CARD))),
        path("frame", [(chamfer, 0.5), ({"fraction": 1, "dp": -0.5}, 0.5), ({"fraction": 1, "dp": -0.5}, {"fraction": 1, "dp": -chamfer}),
                       ({"fraction": 1, "dp": -chamfer}, {"fraction": 1, "dp": -0.5}), (0.5, {"fraction": 1, "dp": -0.5}), (0.5, chamfer)],
             stroke=stroke(solid(rgb(ST_LINE, 0.6)), 1.5)),
    ])
    lines = []
    def line(ident: str, key: str, box: dict, size: float, height_dp: float, tint: list[float], delay: float, duration: float,
             white: bool = False, **extra) -> None:
        lines.extend(strogg_text(ident, key, {**box, "height": length(height_dp)}, size, height_dp, tint, **extra))
        translation.add(ident, start + delay, duration, rest=tint, white=white, width=box["width"]["value"])
    line("level-heading", "#str_230030", absolute(left=U * 24, top=0, width=w - U * 34), 15, header, rgb(ST_READ), 0, 300, white=True)
    below = header + 12 + ph + 10
    line("level-name", "#str_230030", absolute(left=15, top=below, width=pw), 21, 24, rgb(ST_READ), 80, 400, white=True)
    line("level-detail", "#str_230030", absolute(left=15, top=below + 26, width=pw), 17, 20, rgb(ST_SELECT), 140, 200)
    line("level-objectives-head", "#str_200291", absolute(left=15, top=below + 54, width=pw), 14.5, 18, rgb(ST_SELECT), 180, 200,
         display=keyword("block"))
    rows_top, row_h, stats_rule = below + 76, U * 12.5, h - U * 22
    # A map's own objectives summary wraps, so it fades in with its heading
    # rather than translating.
    objectives = label("level-objectives", "#str_230030", {**absolute(left=15, top=rows_top, width=pw, height=stats_rule - rows_top - 3),
        **typeface("r_strogg", 14, 18, rgb(ST_READ, 0.85)), "overflow": keyword("hidden"), "display": keyword("block")})
    translation.add("level-objectives", start + 180, 200, rest=rgb(ST_READ, 0.85), runes=False)
    rows = []
    for index in range(OBJECTIVE_ROWS):
        ident = f"level-objective-{index}"
        mark = vector(f"{ident}-mark", {**absolute(left=15, top=4, width=9, height=9), "display": keyword("block")}, [
            path("mark", [(1.95, 0), (9, 0), (7.05, 7.5), (0, 7.5)], fill=solid(rgb(ST_LINE, 0.6)))])
        text_parts = strogg_text(f"{ident}-text", "#str_230030", absolute(left=33, top=0, width=pw - 18, height=row_h),
                                 16, row_h, rgb(ST_READ), overflow=keyword("hidden"))
        translation.add(f"{ident}-text", start + 220 + 60 * index, 200, rest=rgb(ST_READ), width=pw - 18)
        # The translation owns the text's color, so a completed row dims as
        # a whole, to the atlas's 0.55.
        rows.append(group(ident, {**absolute(left=0, top=rows_top + index * row_h, width=w, height=row_h), "display": keyword("none"),
                                  "opacity": number(1)}, [mark, level_check(ident, rgb(ST_SELECT)), *text_parts]))
        completed = level_row_bindings(doc, ident, index, (f"{ident}-text", f"{ident}-text-rune"))
        doc.bind(f"{ident}.opacity", ident, "opacity", {"op": "select", "args": [completed, 0.55, 1]})
    rule = vector("level-stats-rule", {**absolute(left=15, top=stats_rule, width=pw, height=1), "display": keyword("none")},
                  [path("rule", [(0, 0.5), (pw, 0.5)], closed=False, stroke=stroke(solid([1, 1, 1, 0.1]), 1))])
    stats = label("level-stats", "#str_230030", {**absolute(left=15, top=h - U * 20, width=pw, height=U * 14),
        **typeface("lowpixel", 11, U * 14, rgb(ST_STATS)), "white-space": keyword("nowrap")})
    doc.bind("level-stats.text", "level-stats", "text", {"state": "pause_stats"})
    doc.bind("level-stats-rule.display", "level-stats-rule", "display",
             {"op": "select", "args": [{"op": "==", "args": [{"state": "pause_stats"}, ""]}, "none", "block"]})
    doc.bind("level-shot.image", "level-shot", "image", {"state": "pause_shot"})
    for ident, value in (("level-name", "pause_level"), ("level-detail", "pause_detail")):
        doc.bind(f"{ident}.text", ident, "text", {"state": value})
        doc.bind(f"{ident}-rune.text", f"{ident}-rune", "text", {"state": value})
    doc.bind("level-objectives.text", "level-objectives", "text", {"state": "pause_objectives"})
    published = {"op": ">", "args": [{"op": "+", "args": [{"state": "pause_objective_count"}, {"state": "pause_completed_count"}]}, 0]}
    doc.bind("level-objectives.display", "level-objectives", "display", {"op": "select", "args": [published, "none", "block"]})
    shown = {"op": "select", "args": [{"op": "||", "args": [published, {"op": "!=", "args": [{"state": "pause_objectives"}, ""]}]},
                                      "block", "none"]}
    doc.bind("level-objectives-head.display", "level-objectives-head", "display", shown)
    doc.bind("level-objectives-head-rune.display", "level-objectives-head-rune", "display", shown)
    return group("level-block", absolute(left=x, top=y, width=w, height=h),
                 [frame, grain, shot, corners, *lines, objectives, *rows, rule, stats])


def strogg_title(translation: Translation) -> dict:
    """GAME PAUSED in R_Strogg #FCFFC8, translating from runes at 60 ms over
    500 ms under the scan bar, arriving white (section 13.7)."""
    size, height = 18.5, U * 24
    rest = rgb(ST_READ)
    text_node = label("paused-title", "#str_230031", {"position": keyword("relative"), "display": keyword("block"),
        **typeface("r_strogg", size, height, rest), "white-space": keyword("nowrap"), "transform": transform()})
    latin = group("paused-title-latin", {"position": keyword("relative"), "display": keyword("block"), "margin-left": length(U * 14),
                                         "margin-right": length(U * 12)}, [text_node])
    rune = label("paused-title-rune", "#str_230031", {**absolute(left=U * 14, top=-rune_rise(size)),
        **typeface("strogg", round(size * RUNE_SCALE, 3), height, [*rgb(ST_SELECT)[:3], 0]), "white-space": keyword("nowrap"),
        "transform": transform(), "pointer-events": keyword("none")})
    bar = scan_bar("paused-title-scan", U * 16, {**absolute(left=0, top=0, height=height), "right": length(0),
                                                  "pointer-events": keyword("none")})
    translation.add("paused-title", 60, 500, rest=rest, white=True)
    translation.bar("paused-title-scan", 60, 150)
    return group("paused-title-fit", {**absolute(left=U * 30, top=U * 134, height=height), "pointer-events": keyword("none")},
                 [bar, rune, latin])


# ------------------------------------------------------- the objectives page

# The pause menu's OBJECTIVES (section 13.7) opens the objectives display of
# section 14.11 in its Remastered form as a page of the pause: every open
# objective, newest first, and the ones completed on this map below them.
OBJECTIVE_PAGE_ROWS = 8      # open objectives the page lists (Session.cpp pageRows)
COMPLETED_ROWS = 8           # completed ones, newest first
OBJ_FRAME = "#B0CD6B"        # frames and markers (section 3, wristcomm)
OBJ_TEXT = "#D0DEB6"         # descriptions
OBJ_SERIAL = "#D9E7BF"
ST_OBJ_FRAME, ST_OBJ_MARK = "#FF9000", "#FF9900"   # the Strogg display (section 14.11)
OBJ_TOP, OBJ_BOTTOM = 62.0, 428.0    # u: the list, under the docked top band, over the docked bottom band
OBJ_LEFT, OBJ_WIDTH = 14.0, 600.0    # u: the stock plates are 600 u wide


def objective_frame(ident: str, tint: str) -> dict:
    """The objective plate (section 14.11): an open plate whose foot strip is
    cut at the lower leading corner through the whole foot, its fill
    dissolving toward the trailing side (full to 29%, half at 40%, 0.05 at
    51%, gone at 56%) and its rail along the leading edge, the cut and the
    bottom. Frames rest at 0.40, baked into the paint, so no layer is held
    for them. It spans its entry, so it grows with the entry's text."""
    cut = U * 20 * 0.9
    outline = [(0, 0), ({"fraction": 1}, 0), ({"fraction": 1}, {"fraction": 1}), (cut, {"fraction": 1}), (0, {"fraction": 1, "dp": -cut})]
    def ramp(peak: float) -> list:
        return [(0, rgb(tint, round(peak * 0.4, 4))), (0.29, rgb(tint, round(peak * 0.4, 4))), (0.40, rgb(tint, round(peak * 0.2, 4))),
                (0.51, rgb(tint, round(peak * 0.04, 4))), (0.56, rgb(tint, 0)), (1, rgb(tint, 0))]
    return vector(ident, {**absolute(left=0, top=0), "right": length(0), "bottom": length(0), "pointer-events": keyword("none")}, [
        path("fill", outline, fill=linear((0, 0), ({"fraction": 1}, 0), ramp(0.49))),
        path("rail", [(0.9, 0), (0.9, {"fraction": 1, "dp": -cut}), (cut, {"fraction": 1, "dp": -0.9}), ({"fraction": 1}, {"fraction": 1, "dp": -0.9})],
             closed=False, stroke=stroke(linear((0, 0), ({"fraction": 1}, 0), ramp(1.0)), 1.8)),
    ])


def objectives_scrollbar(doc: Document, ident: str, viewport: str, tint: str, hot: str, left: float, top: float, height: float) -> dict:
    """The list's scrollbar at the plates' trailing end (the atlas): a thin
    trough at 0.15 and a thumb at 0.55 in the frame color, the family's
    focus color on hover, focus and press. Scroll position stays view state."""
    trough = vector(f"{ident}-trough", {**absolute(left=0, top=0), "width": length(100, "%"), "height": length(100, "%"),
                                        "pointer-events": keyword("none")}, [
        path("line", [(15.75, 0), (20.25, 0), (20.25, {"fraction": 1}), (15.75, {"fraction": 1})], fill=solid(rgb(tint, 0.15)))])
    thumb_shape = [(14.25, 0), (21.75, 0), (21.75, {"fraction": 1, "dp": -3}), (18.75, {"fraction": 1}), (14.25, {"fraction": 1})]
    base = vector(f"{ident}-thumb-base", {**absolute(left=0, top=0), "width": length(100, "%"), "height": length(100, "%"),
                                          "pointer-events": keyword("none"), "opacity": number(1)}, [path("thumb", thumb_shape, fill=solid(rgb(tint, 0.55)))])
    active = vector(f"{ident}-thumb-active", {**absolute(left=0, top=0), "width": length(100, "%"), "height": length(100, "%"),
                                              "pointer-events": keyword("none"), "opacity": number(0)}, [path("thumb", thumb_shape, fill=solid(rgb(hot)))])
    thumb = group(f"{ident}-thumb", {**absolute(left=0, top=0, width=36, height=36)}, [base, active])
    track_node = group(f"{ident}-track", {"position": keyword("relative"), "display": keyword("block"), "width": length(36),
                                          "height": length(100, "%")}, [trough, thumb])
    ids = doc.states(ident, {
        "default": [(f"{ident}-thumb-base", "opacity", number(1)), (f"{ident}-thumb-active", "opacity", number(0))],
        "hover": [(f"{ident}-thumb-base", "opacity", number(0)), (f"{ident}-thumb-active", "opacity", number(1))],
        "focus": [(f"{ident}-thumb-base", "opacity", number(0)), (f"{ident}-thumb-active", "opacity", number(1))],
        "pressed": [(f"{ident}-thumb-base", "opacity", number(0)), (f"{ident}-thumb-active", "opacity", number(1))],
        "disabled": [(f"{ident}-thumb-base", "opacity", number(0.4)), (f"{ident}-thumb-active", "opacity", number(0))],
    })
    return group(ident, {**absolute(left=left, top=top, width=36, height=height)}, [track_node],
                 control={"role": "scrollbar", "label": "#str_200380", "viewport": viewport, "orientation": "vertical",
                          "lineStep": round(U * 48, 3), "minimumThumb": 36,
                          "parts": {"track": f"{ident}-track", "thumb": f"{ident}-thumb"}, "states": ids})


def strogg_action_plate(doc: Document, ident: str, key: str, left: float, top: float, *, event: str, width: float) -> dict:
    """An action plate in the Strogg family: the Marine plate's 35 dp band
    in a 45 dp target, ending in the 30-degree shoulder of the Strogg
    navigation plates, its #F59512 rail along the foot, up the trailing
    edge and over the shoulder, the slanted marker, and an R_Strogg label in
    #FCFFC8 turning #FFCC00 on hover and focus."""
    band_top, band_bottom = 5.0, 40.0
    shoulder_x, shoulder_y = U * 16, U * 9.2
    fill = [(0, rgb(ST_LINE, 0.49)), (0.33, rgb(ST_LINE, 0.49)), (1, rgb(ST_LINE, 0.12))]
    rail = [(0, rgb(ST_LINE, 0.9)), (0.55, rgb(ST_LINE, 0.9)), (1, rgb(ST_LINE, 0.45))]
    plate = vector(f"{ident}-plate", {**absolute(left=0, top=0, width=width, height=45), "opacity": number(0.4)}, [
        path("fill", [(0, band_top), (width - shoulder_x, band_top), (width, band_top + shoulder_y), (width, band_bottom), (0, band_bottom)],
             fill=linear((0, 0), (width, 0), fill)),
        path("rail", [(0.75, band_top), (0.75, band_bottom - 0.75), (width - 0.75, band_bottom - 0.75), (width - 0.75, band_top + shoulder_y),
                      (width - shoulder_x, band_top + 0.75), (width * 0.6, band_top + 0.75)],
             closed=False, stroke=stroke(linear((0, 0), (width, 0), rail), 1.5)),
    ])
    focus = vector(f"{ident}-focus", {**absolute(left=0, top=0, width=width, height=45), "opacity": number(0)}, [
        path("inset", [(3.5, band_bottom - 3.5), (width - shoulder_x - 4, band_bottom - 3.5)], closed=False,
             stroke=stroke(solid(rgb(ST_SELECT)), 1.2))])

    def slanted(name: str, tint: list[float], alpha: float) -> dict:
        return vector(name, {**absolute(left=14, top=14, width=10, height=9), "opacity": number(alpha)}, [
            path("mark", [(2.4, 0), (9.6, 0), (7.2, 9), (0, 9)], fill=solid(tint))])
    marker_rest, marker_hot = slanted(f"{ident}-marker", rgb(ST_LINE), 0.4), slanted(f"{ident}-marker-hot", rgb(ST_SELECT), 0)
    text_node = label(f"{ident}-label", key, {**absolute(left=28, top=0, width=width - 32, height=45),
        **typeface("r_strogg", 20, 45, rgb(ST_READ, 0.8)), "white-space": keyword("nowrap"), "transform": transform()})
    rest, lit = colour(rgb(ST_READ, 0.8)), colour(rgb(ST_SELECT))
    ids = doc.states(ident, {
        "default": [(f"{ident}-plate", "opacity", number(0.4)), (f"{ident}-marker", "opacity", number(0.4)), (f"{ident}-marker-hot", "opacity", number(0)),
                    (f"{ident}-focus", "opacity", number(0)), (f"{ident}-label", "color", rest), (f"{ident}-label", "transform", transform())],
        "hover": [(f"{ident}-plate", "opacity", number(0.8)), (f"{ident}-marker", "opacity", number(0)), (f"{ident}-marker-hot", "opacity", number(1)),
                  (f"{ident}-focus", "opacity", number(0)), (f"{ident}-label", "color", lit), (f"{ident}-label", "transform", transform(sx=1.03, sy=1.03))],
        "focus": [(f"{ident}-plate", "opacity", number(0.8)), (f"{ident}-marker", "opacity", number(0)), (f"{ident}-marker-hot", "opacity", number(1)),
                  (f"{ident}-focus", "opacity", number(1)), (f"{ident}-label", "color", lit), (f"{ident}-label", "transform", transform(sx=1.03, sy=1.03))],
        "pressed": [(f"{ident}-plate", "opacity", number(1)), (f"{ident}-marker", "opacity", number(0)), (f"{ident}-marker-hot", "opacity", number(1)),
                    (f"{ident}-focus", "opacity", number(1)), (f"{ident}-label", "color", lit), (f"{ident}-label", "transform", transform(tx=1, ty=1, sx=1.03, sy=1.03))],
        "disabled": [(f"{ident}-plate", "opacity", number(0.4)), (f"{ident}-marker", "opacity", number(0.4)), (f"{ident}-marker-hot", "opacity", number(0)),
                     (f"{ident}-focus", "opacity", number(0)), (f"{ident}-label", "color", colour(rgb(ST_READ, 0.4))), (f"{ident}-label", "transform", transform())],
    })
    return group(ident, absolute(left=left, top=top, width=width, height=45), [plate, focus, marker_rest, marker_hot, text_node],
                 control={"role": "button", "label": key, "states": ids, "event": event})


def objectives_page(doc: Document, strogg: bool) -> tuple:
    """The OBJECTIVES page (sections 13.7 and 14.11). Choosing OBJECTIVES
    docks the bands as a page hand-off does and carries the label into the
    title slot; at 550 ms, when a stock page would appear, the stock entry
    motion plays: the back bar slides 220 u in and fades to 0.80 over
    150 ms, then the heading, plates, text and screenshots fade in over
    100 ms (the frames rest at 0.40 in their paint, so they fade in with
    the text rather than leading at 0.50). Every open objective is
    reachable, newest first, as plates of
    the stock construction whose titles wrap to two lines and descriptions
    wrap without a limit; the completed ones follow under COMPLETED, title
    only at 0.40 with a check. The list scrolls with the wheel, the stick or
    the bar, and Back (the plate at 532,441 u, or the back input) returns
    to the pause with the bands. The Strogg family keeps the construction
    with #FF9000 frames, #FF9900 markers, an R_Strogg heading and the STROGG
    NET serial. Returns the back bar, which lies under the framing bands,
    and the page."""
    frame_tint = ST_OBJ_FRAME if strogg else OBJ_FRAME
    mark_tint = ST_OBJ_MARK if strogg else OBJ_FRAME
    hot = ST_SELECT if strogg else ORANGE
    visible, leaving = "objectives.visible", "objectives.leaving"
    doc.state[visible] = {"type": "boolean", "initial": False}
    doc.state[leaving] = {"type": "boolean", "initial": False}
    doc.state["pause_completed_count"] = {"type": "number", "initial": 0}
    for index in range(OBJECTIVE_PAGE_ROWS):
        doc.state.setdefault(f"pause_objective_{index}", {"type": "string", "initial": ""})
        doc.state[f"pause_objective_text_{index}"] = {"type": "string", "initial": ""}
        doc.state[f"pause_objective_shot_{index}"] = {"type": "string", "initial": ""}
    for index in range(COMPLETED_ROWS):
        doc.state[f"pause_completed_{index}"] = {"type": "string", "initial": ""}
    # The back bar: black 0.80 over the leading 45% of the view, opaque to
    # 190 u, half at 285 u, clear by 380 u. It lies under the framing bands,
    # so their rim light keeps its strength.
    bar = vector("objectives-bar", {**FULL, "transform": transform(), "opacity": number(0), "pointer-events": keyword("none"),
                                    "display": keyword("none")}, [
        path("bar", [(0, 0), (vx(380), 0), (vx(380), {"fraction": 1}), (0, {"fraction": 1})],
             fill=linear((vx(190), 0), (vx(380), 0), [(0, [0, 0, 0, 0.8]), (0.5, [0, 0, 0, 0.4]), (1, [0, 0, 0, 0])]))])
    heading_face = ("r_strogg", 17) if strogg else ("marine", 18)
    heading = label("objectives-heading", "#str_200291", {**absolute(left=U * 20, top=U * 44, width=U * 560, height=24),
        **typeface(heading_face[0], heading_face[1], 24, rgb(OBJECTIVE_HEAD)), "letter-spacing": length(-1.5),
        "white-space": keyword("nowrap")})
    entries = []
    for index in range(OBJECTIVE_PAGE_ROWS):
        ident = f"objectives-entry-{index}"
        marker = vector(f"{ident}-mark", absolute(left=U * 10, top=U * 5, width=U * 8, height=U * 8.5), [
            path("mark", [(0, 0), (U * 8, 0), (U * 8, U * 8.5)], fill=solid(rgb(mark_tint, 0.4)))])
        # The title wraps to two lines at the stock's 308 u; a longer one is
        # cut at the second line's foot.
        title = label(f"{ident}-title", "#str_230030", {"position": keyword("relative"), "display": keyword("block"),
            "margin-left": length(U * 20), "padding-top": length(U * 4), "width": length(U * 308), "max-height": length(U * 24),
            "overflow": keyword("hidden"), **typeface("lowpixel", 14.4, U * 12, [1, 1, 1, 1]), "white-space": keyword("normal")})
        shot = picture(f"{ident}-shot", "", {**absolute(left=U * 1, top=U * 1, width=U * 132, height=U * 98)})
        shot_frame = vector(f"{ident}-shot-frame", {**absolute(left=0, top=0, width=U * 134, height=U * 100)}, [
            path("back", [(0, 0), (U * 134, 0), (U * 134, U * 100), (0, U * 100)], fill=solid([0, 0, 0, 0.5]),
                 stroke=stroke(solid([0, 0, 0, 1]), U * 1))])
        shot_box = group(f"{ident}-shotbox", {"position": keyword("relative"), "display": keyword("block"), "margin-left": length(U * 22),
            "width": length(U * 134), "height": length(U * 100), "flex-shrink": number(0)}, [shot_frame, shot])
        text_node = label(f"{ident}-text", "#str_230030", {"position": keyword("relative"), "display": keyword("block"),
            "margin-left": length(U * 8), "width": length(U * 178), **typeface("lowpixel", 14.4, U * 13.75, rgb(OBJ_TEXT)),
            "white-space": keyword("normal")})
        body = group(f"{ident}-body", {"position": keyword("relative"), "display": keyword("flex"), "flex-direction": keyword("row"),
            "align-items": keyword("flex-start"), "margin-top": length(U * 2)}, [shot_box, text_node])
        # 112 + 20 u at least. As in the stock, the screenshot (18-118 u)
        # reaches into the foot strip, and 14 u stay clear below the content.
        entries.append(group(ident, {"position": keyword("relative"), "display": keyword("none"), "margin-left": length(U * OBJ_LEFT),
            "box-sizing": keyword("border-box"), "width": length(U * OBJ_WIDTH), "min-height": length(U * 132), "padding-bottom": length(U * 14),
            "margin-bottom": length(U * 11)}, [objective_frame(f"{ident}-frame", frame_tint), marker, title, body]))
        doc.bind(f"{ident}.display", ident, "display",
                 {"op": "select", "args": [{"op": ">", "args": [{"state": "pause_objective_count"}, index]}, "block", "none"]})
        doc.bind(f"{ident}-title.text", f"{ident}-title", "text", {"state": f"pause_objective_{index}"})
        doc.bind(f"{ident}-text.text", f"{ident}-text", "text", {"state": f"pause_objective_text_{index}"})
        doc.bind(f"{ident}-shot.image", f"{ident}-shot", "image", {"state": f"pause_objective_shot_{index}"})
    # No open objective: one plate with the stock static screenshot and the
    # stock line beside it, Lowpixel 0.31 in #D0DEB6 wrapping at 164 u.
    empty = group("objectives-empty", {"position": keyword("relative"), "display": keyword("none"), "margin-left": length(U * OBJ_LEFT),
        "width": length(U * OBJ_WIDTH), "height": length(U * 132), "margin-bottom": length(U * 11)}, [
        objective_frame("objectives-empty-frame", frame_tint),
        vector("objectives-empty-shot-frame", absolute(left=U * 22, top=U * 17, width=U * 134, height=U * 100), [
            path("back", [(0, 0), (U * 134, 0), (U * 134, U * 100), (0, U * 100)], fill=solid([0, 0, 0, 0.5]),
                 stroke=stroke(solid([0, 0, 0, 1]), U * 1))]),
        picture("objectives-empty-shot", "gfx/objectives/none", {**absolute(left=U * 23, top=U * 18, width=U * 132, height=U * 98)}),
        label("objectives-empty-text", "#str_200935", {**absolute(left=U * 164, top=U * 43, width=U * 164, height=U * 73),
              **typeface("lowpixel", 22.3, U * 16, rgb(OBJ_TEXT)), "white-space": keyword("normal")})])
    doc.bind("objectives-empty.display", "objectives-empty", "display",
             {"op": "select", "args": [{"op": "==", "args": [{"state": "pause_objective_count"}, 0]}, "block", "none"]})
    # The completed ones: title only at 0.40 behind a check, newest first.
    completed_rows = [group("objectives-completed-head", {"position": keyword("relative"), "display": keyword("flex"),
        "flex-direction": keyword("row"), "margin-bottom": length(U * 4)}, [
        label("objectives-completed-label", "#str_230047", {"position": keyword("relative"), "display": keyword("block"),
              **typeface("lowpixel", 13, U * 12, [1, 1, 1, 0.4]), "white-space": keyword("nowrap")}),
        label("objectives-completed-count", "#str_230030", {"position": keyword("relative"), "display": keyword("block"),
              "margin-left": length(U * 6), **typeface("lowpixel", 13, U * 12, [1, 1, 1, 0.4]), "white-space": keyword("nowrap")})])]
    doc.bind("objectives-completed-count.text", "objectives-completed-count", "text",
             {"op": "numberText", "args": [{"state": "pause_completed_count"}], "decimals": 0})
    for index in range(COMPLETED_ROWS):
        ident = f"objectives-done-{index}"
        check = vector(f"{ident}-check", absolute(left=0, top=U * 2, width=U * 9, height=U * 8), [
            path("check", [(U * 0.5, U * 4), (U * 3, U * 6.6), (U * 7.6, U * 1.2)], closed=False,
                 stroke=stroke(solid(rgb(hot if strogg else "#B5C784", 0.4)), U * 1.4, join="round", cap="round"))])
        title = label(f"{ident}-title", "#str_230030", {**absolute(left=U * 12, top=0, width=U * 560, height=U * 12),
            **typeface("lowpixel", 14.4, U * 12, [1, 1, 1, 0.4]), "white-space": keyword("nowrap"), "overflow": keyword("hidden")})
        completed_rows.append(group(ident, {"position": keyword("relative"), "display": keyword("none"), "height": length(U * 13)},
                                    [check, title]))
        doc.bind(f"{ident}.display", ident, "display",
                 {"op": "select", "args": [{"op": ">", "args": [{"state": "pause_completed_count"}, index]}, "block", "none"]})
        doc.bind(f"{ident}-title.text", f"{ident}-title", "text", {"state": f"pause_completed_{index}"})
    completed = group("objectives-completed", {"position": keyword("relative"), "display": keyword("none"),
        "margin-left": length(U * (OBJ_LEFT + 12)), "margin-top": length(U * 2)}, completed_rows)
    doc.bind("objectives-completed.display", "objectives-completed", "display",
             {"op": "select", "args": [{"op": ">", "args": [{"state": "pause_completed_count"}, 0]}, "block", "none"]})
    serial = label("objectives-serial", "#str_200280" if strogg else "#str_200275", {"position": keyword("relative"),
        "display": keyword("block"), "margin-left": length(U * (OBJ_LEFT + 12)), "margin-top": length(U * 12),
        "margin-bottom": length(U * 8), **typeface("r_strogg" if strogg else "marine", 13, 18, rgb(OBJ_SERIAL, 0.25)),
        "white-space": keyword("nowrap")})
    column = group("objectives-column", {"position": keyword("relative"), "display": keyword("block")},
                   [*entries, empty, completed, serial])
    viewport = group("objectives-list", {**absolute(left=0, top=U * OBJ_TOP, width=U * (OBJ_LEFT + OBJ_WIDTH + 2),
        height=U * (OBJ_BOTTOM - OBJ_TOP)), "overflow": keyword("auto")}, [column])
    scrollbar = objectives_scrollbar(doc, "objectives_scroll", "objectives-list", frame_tint, hot,
                                     U * (OBJ_LEFT + OBJ_WIDTH) + 2, U * OBJ_TOP, U * (OBJ_BOTTOM - OBJ_TOP))
    if strogg:
        back = strogg_action_plate(doc, "objectives_back", "#str_200018", U * 532, U * 441, event="objectivesHide", width=U * 109)
    else:
        back = action_plate(doc, "objectives_back", "#str_200018", U * 532, U * 441, event="objectivesHide", width=U * 109)
    canvas = group("objectives-canvas", {**absolute(top=0, width=CANVAS_W, height=720), "left": length(50, "%"),
                                         "margin-left": length(-CANVAS_W / 2)}, [heading, viewport, scrollbar, back])
    content = group("objectives-content", {**FULL, "opacity": number(0)}, [canvas])
    node = group("objectives", {**FULL, "display": keyword("none")}, [content],
                 modal={"initialFocus": "objectives_scroll", "back": "objectivesHide"})
    for part in ("objectives", "objectives-bar"):
        doc.bind(f"{part}.display", part, "display", {"op": "select", "args": [{"state": visible}, "block", "none"]})
    # Choosing OBJECTIVES docks the bands and carries the label as a page
    # hand-off does; the stock entry motion follows at 550 ms. Back fades the
    # page and brings the bands home; the page closes when they arrive, and
    # a second Back during that leave changes nothing.
    home_return = [{"op": "call", "event": "returnHome"}] if strogg else [{"op": "playTimeline", "timeline": "returnHome"}]
    doc.events["objectivesShow"] = [{"op": "setState", "values": {visible: True, leaving: False}}, {"op": "call", "event": "carry_objectives"},
                                    {"op": "playTimeline", "timeline": "depart"}, {"op": "playTimeline", "timeline": "objectivesEnter"}]
    doc.events["objectivesHide"] = [{"op": "if", "condition": {"op": "!", "args": [{"state": leaving}]},
                                     "then": [{"op": "setState", "values": {leaving: True}},
                                              {"op": "playTimeline", "timeline": "objectivesLeave"}, *home_return]}]
    doc.events["objectivesHidden"] = [{"op": "setState", "values": {visible: False, leaving: False}}]
    shown, hidden_bar = transform(), transform(-220 * U)
    doc.timelines.add("objectivesEnter", 800, [
        track("objectives-bar", "transform", [(0, hidden_bar), (1, hidden_bar), (550, hidden_bar, EASE_OUT), (700, shown)]),
        track("objectives-bar", "opacity", [(0, number(0)), (1, number(0)), (550, number(0)), (700, number(1))]),
        track("objectives-content", "opacity", [(0, number(0)), (1, number(0)), (700, number(0)), (800, number(1))]),
        track("prompts", "opacity", [(0, number(1)), (150, number(0)), (800, number(0))]),
    ])
    doc.timelines.add("objectivesLeave", 650, [
        track("objectives-content", "opacity", [(0, number(1)), (100, number(0)), (650, number(0))]),
        track("objectives-bar", "opacity", [(0, number(1)), (150, number(0)), (650, number(0))]),
        track("prompts", "opacity", [(0, number(0)), (500, number(0)), (650, number(1))]),
    ], complete="objectivesHidden")
    return bar, node


def pause_document(strogg: bool = False) -> dict:
    """The single-player pause (section 13.7). `strogg` builds the Strogg
    pause that the session presents after Kane's stroggification."""
    doc = Document("openq4.pause_strogg" if strogg else "openq4.pause")
    doc.state.update({
        "pause_level": {"type": "string", "initial": ""},
        "pause_detail": {"type": "string", "initial": ""},
        "pause_objectives": {"type": "string", "initial": ""},
        "pause_shot": {"type": "string", "initial": ""},
        "pause_objective_count": {"type": "number", "initial": 0},
        **{f"pause_objective_{index}": {"type": "string", "initial": ""} for index in range(OBJECTIVE_ROWS)},
        "pause_stats": {"type": "string", "initial": ""},
    })
    doc.session("resume", "resume")
    doc.session("saveGame", "saveGame")
    doc.session("loadGame", "loadGame")
    doc.session("restartLevel", "restartLevel")
    doc.session("settings", "settings")
    doc.session("quitToMenu", "quitToMenu")
    doc.session("quit", "quit")
    quit_modal = confirmation(doc, "quitModal", "#str_200004", "#str_200174", "quitToMenu")
    exit_modal = confirmation(doc, "exitModal", "#str_200169", "#str_200170", "quit", frame_leave_ms=200)
    doc.events["onBack"] = [{"op": "action", "action": "resume"}]
    items = [("nav_resume", "#str_200381", "resume", None), ("nav_savegame", "#str_200003", "saveGame", None),
             ("nav_loadgame", "#str_200001", "loadGame", None), ("nav_restart", "#str_229983", "restartLevel", None),
             ("nav_objectives", "#str_200380", None, "objectivesShow"), ("nav_settings", "#str_200009", "settings", None),
             ("nav_quit", "#str_230025", None, "quitModalShow")]
    translation = Translation() if strogg else None
    if strogg:
        plates = [strogg_navigation_plate(doc, ident, key, translation, index, action=action, event=event)
                  for index, (ident, key, action, event) in enumerate(items)]
    else:
        plates = [navigation_plate(doc, ident, key, action=action, event=event) for ident, key, action, event in items]
    nav = group("nav", {**absolute(left=0, top=U * 182.2, width=U * 413), "display": keyword("flex"),
                        "flex-direction": keyword("column")}, plates)
    if strogg:
        # The actions translate 45 ms apart, EXIT after them, and the level
        # block's lines follow.
        exit_link = strogg_link(doc, "link_exit", "#str_200013", translation, 120 + 45 * len(items), event="exitModalShow")
        home_parts = [strogg_title(translation), nav, strogg_level_block(doc, translation, 120 + 45 * (len(items) + 1)),
                      strogg_plinth([exit_link])]
    else:
        home_parts = [label("paused-title", "#str_230031", {**absolute(left=U * 44, top=U * 134, width=U * 330, height=U * 24),
                            **typeface("marine", 18, U * 24, [1, 1, 1, 0.5]), "white-space": keyword("nowrap")}),
                      nav, level_block(doc), plinth(doc, [link(doc, "link_exit", "#str_200013", event="exitModalShow")])]
    content = group("home", {**FULL, "transform": transform(), "opacity": number(1)}, [
        group("home-content", {**absolute(top=0, width=CANVAS_W, height=720), "left": length(50, "%"), "margin-left": length(-CANVAS_W / 2)},
              home_parts),
    ])
    # The paused view, softened and never dimmed (sections 9 and 13.7). The
    # specification gives scene softening no values of its own, so the pause
    # takes modal.softfocus's; it ramps in with menu.fade. With the
    # opaque-backing option, or where the renderer cannot soften the view, a
    # darkening scrim and vignette stand in (section 13.6).
    doc.state["soft_focus"] = {"type": "boolean", "initial": False, "cvar": "ui_retainedSoftFocus"}
    softened = group("scene-softfocus", {**FULL, "display": keyword("none"), "backdrop-blur": length(SOFT_FOCUS_BLUR),
                                         "backdrop-saturate": number(SOFT_FOCUS_SATURATION)})
    doc.bind("scene-softfocus.display", "scene-softfocus", "display", {"op": "select", "args": [{"state": "soft_focus"}, "block", "none"]})
    doc.bind("scrim.display", "scrim", "display", {"op": "select", "args": [{"state": "soft_focus"}, "none", "block"]})
    scrim = vector("scrim", {**FULL, "display": keyword("block")}, [
        path("dim", [(0, 0), ({"fraction": 1}, 0), ({"fraction": 1}, {"fraction": 1}), (0, {"fraction": 1})], fill=solid([0, 0, 0, 0.45])),
        path("lead", [(0, 0), (vx(413), 0), (vx(413), {"fraction": 1}), (0, {"fraction": 1})],
             fill=linear((vx(-107), 0), (vx(413), 0), [(0, [0, 0, 0, 0.7]), (0.55, [0, 0, 0, 0.35]), (1, [0, 0, 0, 0])])),
    ])
    prompts = [("#str_107019", "#str_200747"), ("#str_107020", "#str_200381")]
    carries = [("saveGame", "#str_200003", 212.2), ("loadGame", "#str_200001", 242.2),
               ("restartLevel", "#str_229983", 272.2), ("objectives", "#str_200380", 302.2),
               ("settings", "#str_200009", 332.2)]
    objectives_bar, objectives = objectives_page(doc, strogg)
    if strogg:
        # The Strogg light, crosses and bands; the confirmations stay the
        # stock dialogs of section 6.
        field = lit_field("field", 0.55, glow=ST_LIGHT, grid={"tint": rgb(ST_GRID), "arm_u": 5.5})
        bands = framing_bands("band", STROGG_BANDS)
        prompt = prompt_bar(doc, prompts, cap_tint=rgb(ST_SELECT, 0.85), verb_face=("r_strogg", 14, rgb(ST_READ, 0.8)))
        carry = title_carry(doc, carries, face="r_strogg", tint=ST_SELECT)
    else:
        field = lit_field("field", 0.45)
        bands = framing_bands("band")
        prompt = prompt_bar(doc, prompts)
        carry = title_carry(doc, carries)
    root = group("screen", {**FULL, "font-family": font("marine"), "font-size": length(16), "color": colour([1, 1, 1, 0.8])}, [
        softened,
        scrim,
        *field,
        objectives_bar,
        *bands,
        content,
        objectives,
        prompt,
        carry,
        quit_modal,
        exit_modal,
        group("fade", {**FULL, "background-color": colour([0, 0, 0, 0]), "pointer-events": keyword("none")}),
    ])
    band_motion(doc, "band", "home", [], quick=("plinth",))
    # The softened view rests at modal.softfocus, so a page's return keeps it.
    # A play retargets its first key from the current value, and the pause
    # document outlives each pause; the second key restarts the ramp from
    # nothing every time the pause opens, behind menu.fade's black.
    opening = next(timeline for timeline in doc.timelines.items if timeline["id"] == "open")
    opening["tracks"] += [
        track("scene-softfocus", "backdrop-blur", [(0, length(0)), (1, length(0)), (250, length(SOFT_FOCUS_BLUR))]),
        track("scene-softfocus", "backdrop-saturate", [(0, number(1)), (1, number(1)), (250, number(SOFT_FOCUS_SATURATION))]),
    ]
    hide_carry_at_home(doc)
    if strogg:
        translation.finish(doc)
    # A pause can close without Back (a console load or disconnect); every
    # opening starts at home without the Objectives page, prompts showing.
    opening["tracks"].append(track("prompts", "opacity", [(0, number(1)), (1, number(1)), (250, number(1))]))
    reset = {"op": "setState", "values": {"objectives.visible": False, "objectives.leaving": False}}
    doc.events["open"] = [reset, *doc.events.get("open", [{"op": "playTimeline", "timeline": "open"}])]
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
    documents = {"title": title_document(), "pause": pause_document(), "pause_strogg": pause_document(strogg=True),
                 "loading": loading_document(),
                 "singleplayer": campaign_document(False), "campaigns": campaign_document(True)}
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
