"""The retained multiplayer menus (docs/dev/ui-visual-design.md section 14.18).

Built by tools/ui/build_retained_screens.py, which writes and checks them with
the other retained screens. The Escape card covers the game's multiplayer menu
(mpmain.gui) while a match runs: a card centered over the softened view with a
header, a horizontal strip of eight tabs, the page and a prompt bar. A page
that is not built yet hands off to its stock page through the mpStockPage
verb, and the session keeps the card opt-in (ui_retainedMultiplayer) while
any page does (RETAINED_MP_ESCAPE_MISSING_PAGES).

The tab strip cannot fit eight Marine labels in the specified 648 dp card in
any shipped language: with the active tab's flare and shoulder, even the
shortest English set needs about 860 dp. The Escape card therefore grows to
the widest language's fitted strip, never past a 4:3 view's 16 dp margins,
and generation fails when a language would need more (docs/dev/ui/
retained-screens.md, Multiplayer menus).
"""
from __future__ import annotations

import re
from pathlib import Path

import build_retained_screens as b
from build_retained_screens import (EASE_OUT, FULL, MARKER, OLIVE, ORANGE, RAIL_CARD, SOFT_FOCUS_BLUR,
                                    SOFT_FOCUS_SATURATION, VALUE, Document, absolute, colour, confirmation, group,
                                    keyword, label, length, linear, link, marker_path, number, path, rgb, solid,
                                    stroke, track, transform, typeface, vector)

ROOT = Path(__file__).resolve().parents[2]
STRINGS = ROOT / "content" / "baseoq4" / "pak0" / "strings"

TAB_GREEN = "#5A652A"          # the active tab's fill (Appendix B.1, ctrls_tab2-4)
BODY = [0, 0, 0, 0.94]         # the card's body (section 6, panel anatomy)
VIEW_43 = 960.0                # the narrowest landscape view the card must clear, in dp
SIDE_MARGIN = 16.0             # the card never comes closer than this to the view's sides
ESCAPE_MIN_W, ESCAPE_H = 648.0, 477.0
HEADER_H = 40.0
CUT_MAJOR, CUT_MINOR = 12.0, 3.0
INSET = 24.0                   # page content inset
TAB_TOP, TAB_RISE = 52.0, 30.0
TAB_FLARE, TAB_SHOULDER, TAB_PAD = 3.0, 18.0, 5.0
TAB_SIZE = 14.0                # Marine label size in dp (decision D7: the spec gives none)
STRIP_EDGE = 12.0              # the strip's distance from the card's sides
KEYCAP_W, KEYCAP_GAP = 20.0, 6.0
PAGE_TOP = TAB_TOP + TAB_RISE + 16.0
PROMPT_H = 22.0
PROMPT_BOTTOM = 16.0
PAGE_FADE_MS = 150
OPEN_MS, RISE_MS, REDUCED_MS, RELEASE_MS = 250, 150, 80, 250
RISE_DP = 12.0
PLACEHOLDER = "#str_230030"    # bound labels' text before their first binding

# The eight Escape tabs in order: (page id, tab label, the stock menu button
# the interim hand-off presses). The session's RETAINED_MP_STOCK_PAGES lists
# the same buttons in the same order.
ESCAPE_TABS = [
    ("team", "#str_231001", "main_b_jointeam"),
    ("players", "#str_231002", "main_b_players"),
    ("vote", "#str_231003", "main_b_vote"),
    ("match", "#str_231004", "main_b_matchcontrol"),
    ("settings", "#str_231005", "main_b_settings"),
    ("voice", "#str_231006", "main_b_voiceconfig"),
    ("server", "#str_231007", "main_b_serverinfo"),
    ("admin", "#str_231008", "main_b_admin"),
]
KEY_PREVIOUS, KEY_NEXT = "#str_231009", "#str_231010"
VERB_TABS = "#str_231011"
HANDOFF_NOTE, HANDOFF_ACTION = "#str_231012", "#str_231013"
KEY_ESCAPE, KEY_ENTER = "#str_107020", "#str_107019"
VERB_RESUME, VERB_SELECT = "#str_200381", "#str_200747"
MAIN_MENU, DISCONNECT, DISCONNECT_BODY = "#str_200188", "#str_200006", "#str_200173"


def table_text(key: str) -> dict:
    """`key`'s text in every shipped language's openQ4 table."""
    texts = {}
    for language in b.LANGUAGES:
        for line in (STRINGS / f"{language}_openq4.lang").read_text(encoding="utf-8").splitlines():
            match = re.match(r'\s*"(#str_\d+)"\s+"(.*)"\s*$', line)
            if match and match.group(1) == key:
                texts[language] = match.group(2)
    missing = sorted(set(b.LANGUAGES) - set(texts))
    if missing:
        raise SystemExit(f"{key} is missing from the {', '.join(missing)} openQ4 tables")
    return texts


def tab_slot(label_width: float) -> float:
    """A tab's slot: the leading flare and padding, the label, the padding and
    the trailing shoulder, so the active silhouette never reaches a neighbour."""
    return TAB_FLARE + TAB_PAD + label_width + TAB_PAD + TAB_SHOULDER


def label_width(key: str, language: str) -> float:
    return b.text_width("marine", table_text(key)[language], TAB_SIZE)


def strip_chrome() -> float:
    """The strip's width beside its tabs: its edges and the two keycaps."""
    return 2 * (STRIP_EDGE + KEYCAP_W + KEYCAP_GAP)


def fitted_card_width(keys: list) -> float:
    """The Escape card's width: the specified 648 dp, or the widest language's
    tabs with the strip's keycaps and edges and a 2 % margin against layout
    rounding, rounded up to a whole dp. Fails when that needs more than a 4:3
    view allows."""
    strips = {language: sum(tab_slot(label_width(key, language)) for key in keys) for language in b.LANGUAGES}
    needed = max(strips.values()) * 1.02 + strip_chrome()
    limit = VIEW_43 - 2 * SIDE_MARGIN
    if needed > limit:
        raise SystemExit(f"the Escape tab strip needs {needed:.0f} dp, past a 4:3 view's {limit:g} dp; per language: "
                         + ", ".join(f"{language} {round(width)}" for language, width in strips.items()))
    return max(ESCAPE_MIN_W, float(int(needed + 0.999)))


# ------------------------------------------------------------------- the card

def card_frame(width: float, height: float) -> dict:
    """The section 6 card: a black body at 0.94 inside one marine.rail.card
    rail, 12 dp cuts at the top-trailing and bottom-leading corners and 3 dp
    cuts at the other two."""
    def outline(inset: float) -> list:
        d = inset * 0.4142   # a 45-degree corner moves this far along each side per unit of inset
        return [(CUT_MINOR + d, inset), (width - CUT_MAJOR - d, inset), (width - inset, CUT_MAJOR + d),
                (width - inset, height - CUT_MINOR - d), (width - CUT_MINOR - d, height - inset),
                (CUT_MAJOR + d, height - inset), (inset, height - CUT_MAJOR - d), (inset, CUT_MINOR + d)]
    return vector("card-frame", absolute(left=0, top=0, width=width, height=height), [
        path("body", outline(0), fill=solid(BODY)),
        path("rail", outline(0.75), stroke=stroke(solid(rgb(RAIL_CARD)), 1.5)),
    ])


def bound_text(ident: str, doc: Document, state: str, face: str, size: float, tint: list) -> dict:
    node = label(ident, PLACEHOLDER, {"position": keyword("relative"), "display": keyword("block"),
                                      **typeface(face, size, HEADER_H, tint), "white-space": keyword("nowrap")})
    doc.bind(f"{ident}.text", ident, "text", {"state": state})
    return node


def card_header(doc: Document, width: float, title_state: str, trailing: list) -> list:
    """The 40 dp header (sections 6 and 14.18): a white 0.16 wash in the light
    plate's shape fading toward the trailing edge, a 1 dp rule below, the
    8 dp triangle and the title in Marine, and the trailing texts."""
    band_top, band_bottom, cut = 3.0, HEADER_H - 3.0, 19.0
    wash = vector("header-wash", absolute(left=1.5, top=0, width=width - 3, height=HEADER_H), [
        path("wash", [(0, band_top), ({"fraction": 1}, band_top), ({"fraction": 1}, band_bottom), (cut, band_bottom),
                      (0, band_bottom - cut)],
             fill=linear((0, 0), ({"fraction": 1}, 0), [(0, [1, 1, 1, 0.16]), (0.5, [1, 1, 1, 0.16]), (1, [1, 1, 1, 0])])),
    ])
    rule = vector("header-rule", absolute(left=1.5, top=HEADER_H, width=width - 3, height=1), [
        path("rule", [(0, 0.5), ({"fraction": 1}, 0.5)], closed=False, stroke=stroke(solid(rgb(RAIL_CARD, 0.8)), 1)),
    ])
    # One row: the triangle, the title taking whatever the trailing texts
    # leave and clipping there, then the trailing texts at their own widths.
    triangle = vector("header-triangle", {"position": keyword("relative"), "display": keyword("block"), "width": length(8),
                                          "height": length(8), "flex-shrink": number(0), "margin-right": length(-8)},
                      [marker_path("mark", 0, 0, 8, rgb(MARKER))])
    title = label("header-title", PLACEHOLDER, {"position": keyword("relative"), "display": keyword("block"), "flex-grow": number(1),
                  "flex-shrink": number(1), "min-width": length(0), "height": length(HEADER_H), "overflow": keyword("hidden"),
                  **typeface("marine", 20, HEADER_H, [1, 1, 1, 0.9]), "white-space": keyword("nowrap")})
    doc.bind("header-title.text", "header-title", "text", {"state": title_state})
    for item in trailing:
        item["properties"]["flex-shrink"] = number(0)
    row = group("header-row", {**absolute(left=INSET, top=0, right=INSET, height=HEADER_H), "display": keyword("flex"),
                               "flex-direction": keyword("row"), "align-items": keyword("center"), "column-gap": length(16)},
                [triangle, title, *trailing])
    return [wash, rule, row]


def keycap(ident: str, key: str, *, fixed: bool = False, event: str | None = None, doc: Document | None = None) -> dict:
    """A keycap plate with a 45-degree lower-leading cut (section 13.4) and
    its key name in Lowpixel. A `fixed` cap is the strip's 20 dp glyph; the
    prompt bar's caps fit their key names. With `event` it is a button."""
    shape = path("cap", [(0, 0), ({"fraction": 1}, 0), ({"fraction": 1}, {"fraction": 1}), (6, {"fraction": 1}),
                         (0, {"fraction": 1, "dp": -6})], fill=solid([1, 1, 1, 1]))
    name_props = {"position": keyword("relative"), "display": keyword("block"), **typeface("lowpixel", 13, PROMPT_H, [0.04, 0.05, 0.035, 1]),
                  "white-space": keyword("nowrap")}
    if fixed:
        name_props.update({**absolute(left=0, top=0, width=KEYCAP_W, height=PROMPT_H), "text-align": keyword("center")})
        cap_props = {**absolute(left=0, top=0, width=KEYCAP_W, height=PROMPT_H), "opacity": number(0.85)}
        props = {"position": keyword("absolute"), "width": length(KEYCAP_W), "height": length(PROMPT_H)}
    else:
        cap_props = {"position": keyword("relative"), "display": keyword("block"), "height": length(PROMPT_H),
                     "padding-left": length(7), "padding-right": length(7), "opacity": number(0.85)}
        props = {"position": keyword("relative"), "display": keyword("block"), "height": length(PROMPT_H)}
    name = label(f"{ident}-key", key, name_props)
    if fixed:
        children = [vector(f"{ident}-cap", cap_props, [shape]), name]
    else:
        children = [vector(f"{ident}-cap", cap_props, [shape], [name])]
    if event is None:
        return group(ident, props, children)
    ids = doc.states(ident, {
        "default": [(f"{ident}-cap", "opacity", number(0.85))], "hover": [(f"{ident}-cap", "opacity", number(1))],
        "focus": [(f"{ident}-cap", "opacity", number(1))], "pressed": [(f"{ident}-cap", "opacity", number(1))],
        "disabled": [(f"{ident}-cap", "opacity", number(0.4))],
    })
    return group(ident, props, children, control={"role": "button", "label": key, "event": event, "states": ids})


def tab(doc: Document, index: int, ident: str, key: str) -> dict:
    """One tab of the strip: its label in flow, padded to hold the leading
    flare and the trailing shoulder, so the tab is as wide as its label in
    the running language plus its share of the strip's remainder. The active tab rises 30 dp with a 3 dp leading
    flare and an 18 dp 45-degree trailing shoulder, filled #5A652A from 1.00
    at the top to 0.60 at the baseline inside a white outline, and erases the
    strip's baseline beneath it. Inactive labels sit at 0.55 and rise to 0.85
    on hover; the active label is white, and focus turns a label orange."""
    node = f"tab-{ident}"
    h = TAB_RISE
    right = {"fraction": 1}
    shoulder = {"fraction": 1, "dp": -TAB_SHOULDER}
    edge = [(0, h), (TAB_FLARE, h - TAB_FLARE), (TAB_FLARE, 0), (shoulder, 0), (right, TAB_SHOULDER), (right, h)]
    silhouette = vector(f"{node}-active", {**FULL, "display": keyword("none")}, [
        path("erase", [(0, h - 0.75), (right, h - 0.75)], closed=False, stroke=stroke(solid([0, 0, 0, 1]), 2.5)),
        path("fill", edge, fill=linear((0, 0), (0, h), [(0, rgb(TAB_GREEN, 1)), (1, rgb(TAB_GREEN, 0.6))])),
        path("outline", edge, closed=False, stroke=stroke(solid([1, 1, 1, 0.75]), 1.5)),
    ])
    face = {"text-align": keyword("center"), "white-space": keyword("nowrap")}
    # The lit copy lies under the label, so focus's orange still shows on the
    # active tab, and the 0.55 white at rest reads as white over it.
    lit = label(f"{node}-lit", key, {**absolute(left=TAB_FLARE + TAB_PAD, top=0, right=TAB_PAD + TAB_SHOULDER, height=h),
                                     "display": keyword("none"), **typeface("marine", TAB_SIZE, h, [1, 1, 1, 1]), **face})
    text_node = label(f"{node}-label", key, {"position": keyword("relative"), "display": keyword("block"),
                                             **typeface("marine", TAB_SIZE, h, [1, 1, 1, 0.55]), **face})
    ids = doc.states(node, {
        "default": [(f"{node}-label", "color", colour([1, 1, 1, 0.55]))],
        "hover": [(f"{node}-label", "color", colour([1, 1, 1, 0.85]))],
        "focus": [(f"{node}-label", "color", colour(rgb(ORANGE)))],
        "pressed": [(f"{node}-label", "color", colour(rgb(ORANGE)))],
        "disabled": [(f"{node}-label", "color", colour([1, 1, 1, 0.3]))],
    })
    active = {"op": "==", "args": [{"state": "card.tab"}, index]}
    doc.bind(f"{node}-active.display", f"{node}-active", "display", {"op": "select", "args": [active, "block", "none"]})
    doc.bind(f"{node}-lit.display", f"{node}-lit", "display", {"op": "select", "args": [active, "block", "none"]})
    return group(node, {"position": keyword("relative"), "display": keyword("block"), "height": length(h),
                        "padding-left": length(TAB_FLARE + TAB_PAD), "padding-right": length(TAB_PAD + TAB_SHOULDER),
                        "flex-grow": number(1)},
                 [silhouette, lit, text_node],
                 control={"role": "button", "label": key, "event": f"tab_{ident}", "states": ids})


def tab_strip(doc: Document, width: float, tabs: list) -> list:
    """The strip under the header (section 14.18): Q and E keycaps at its
    ends run the previous and next tab; the tabs share the width between
    them; the baseline runs under all of them, broken under the active tab,
    and a #5A652A wash fades below it over one tab height."""
    inner_left = STRIP_EDGE + KEYCAP_W + KEYCAP_GAP
    inner_width = width - 2 * inner_left
    slots = [tab(doc, index, ident, key) for index, (ident, key, _window) in enumerate(tabs)]
    keys_top = TAB_TOP + (TAB_RISE - PROMPT_H) / 2
    previous = keycap("tab-previous", KEY_PREVIOUS, fixed=True, event="onTabPrevious", doc=doc)
    following = keycap("tab-next", KEY_NEXT, fixed=True, event="onTabNext", doc=doc)
    previous["properties"].update(absolute(left=STRIP_EDGE, top=keys_top))
    following["properties"].update(absolute(left=width - STRIP_EDGE - KEYCAP_W, top=keys_top))
    row = group("tabs", {**absolute(left=inner_left, top=TAB_TOP, width=inner_width, height=TAB_RISE),
                         "display": keyword("flex"), "flex-direction": keyword("row"), "align-items": keyword("flex-end")}, slots)
    baseline_y = TAB_TOP + TAB_RISE
    baseline = vector("tab-baseline", absolute(left=STRIP_EDGE, top=baseline_y - 1.5, width=width - 2 * STRIP_EDGE, height=2), [
        path("rail", [(0, 0.75), ({"fraction": 1}, 0.75)], closed=False, stroke=stroke(solid([1, 1, 1, 0.75]), 1.5))])
    wash = vector("tab-wash", absolute(left=STRIP_EDGE, top=baseline_y, width=width - 2 * STRIP_EDGE, height=TAB_RISE), [
        path("wash", [(0, 0), ({"fraction": 1}, 0), ({"fraction": 1}, {"fraction": 1}), (0, {"fraction": 1})],
             fill=linear((0, 0), (0, {"fraction": 1}), [(0, rgb(TAB_GREEN, 0.57)), (1, rgb(TAB_GREEN, 0.02))]))])
    # The baseline lies under the row, so the active tab's eraser covers it.
    return [wash, baseline, row, previous, following]


def in_game_plate(doc: Document, ident: str, key: str, left: float, top: float, *, width: float = 300,
                  primary: bool = False, action: str | None = None, event: str | None = None) -> dict:
    """An action on an in-game card (section 14.18): the light plate of
    section 6 (b6_light) with its leading, cut and bottom rails, at 0.62 for
    the page's primary action and 0.28 for the others, rising to 1.00 with
    the orange marker and inset rail when focused; Marine 20 dp."""
    rest = 0.62 if primary else 0.28
    band_top, band_bottom, cut = 5.0, 40.0, 20.0
    fill = [(0, rgb(OLIVE, 0.49)), (0.33, rgb(OLIVE, 0.49)), (1, rgb(OLIVE, 0))]
    rail = [(0, rgb(OLIVE)), (0.33, rgb(OLIVE)), (1, rgb(OLIVE, 0))]
    plate = vector(f"{ident}-plate", {**absolute(left=0, top=0, width=width, height=45), "opacity": number(rest)}, [
        path("fill", [(0, band_top), (width, band_top), (width, band_bottom), (cut, band_bottom), (0, band_bottom - cut)],
             fill=linear((0, 0), (width, 0), fill)),
        path("rail", [(0.75, band_top), (0.75, band_bottom - cut), (cut, band_bottom - 0.75), (width, band_bottom - 0.75)],
             closed=False, stroke=stroke(linear((0, 0), (width, 0), rail), 1.5)),
    ])
    inset = vector(f"{ident}-focus", {**absolute(left=0, top=0, width=width, height=45), "opacity": number(0)}, [
        path("inset", [(3.5, band_top + 3), (3.5, band_bottom - cut + 1.5), (cut + 1.5, band_bottom - 3.5), (width - 20, band_bottom - 3.5)],
             closed=False, stroke=stroke(solid(rgb(ORANGE)), 1.2))])
    marker_rest = vector(f"{ident}-marker", {**absolute(left=14, top=14, width=8, height=8), "opacity": number(rest)}, [
        marker_path("mark", 0, 0, 8, rgb(MARKER))])
    marker_hot = vector(f"{ident}-marker-hot", {**absolute(left=14, top=14, width=8, height=8), "opacity": number(0)}, [
        marker_path("mark", 0, 0, 8, rgb(ORANGE))])
    text_node = label(f"{ident}-label", key, {**absolute(left=26, top=0, width=width - 30, height=45),
                      **typeface("marine", 20, 45, [1, 1, 1, 0.8]), "white-space": keyword("nowrap"), "transform": transform()})

    def state(plate_opacity, marker, hot, focus, tint, moved):
        return [(f"{ident}-plate", "opacity", number(plate_opacity)), (f"{ident}-marker", "opacity", number(marker)),
                (f"{ident}-marker-hot", "opacity", number(hot)), (f"{ident}-focus", "opacity", number(focus)),
                (f"{ident}-label", "color", colour(tint)), (f"{ident}-label", "transform", moved)]
    ids = doc.states(ident, {
        "default": state(rest, rest, 0, 0, [1, 1, 1, 0.8], transform()),
        "hover": state(0.8, 0, 1, 0, rgb(ORANGE), transform(sx=1.03, sy=1.03)),
        "focus": state(1, 0, 1, 1, rgb(ORANGE), transform(sx=1.03, sy=1.03)),
        "pressed": state(1, 0, 1, 1, rgb(ORANGE), transform(tx=1, ty=1, sx=1.03, sy=1.03)),
        "disabled": state(rest, rest, 0, 0, [1, 1, 1, 0.8], transform()),
    })
    control = {"role": "button", "label": key, "states": ids}
    if action:
        control["action"] = action
    else:
        control["event"] = event
    return group(ident, absolute(left=left, top=top, width=width, height=45), [plate, inset, marker_rest, marker_hot, text_node],
                 control=control)


def page_group(doc: Document, index: int, ident: str, width: float, height: float, children: list, controls: list) -> dict:
    """A page of the card: shown while it is current or fading out. Its
    controls answer only while it is current, so a page fading out takes no
    input (their disabled visuals equal their rest)."""
    current = {"op": "==", "args": [{"state": "card.tab"}, index]}
    for control in controls:
        doc.bind(f"{control}.enabled", control, "enabled", current)
    shown = {"op": "||", "args": [current, {"op": "==", "args": [{"state": "card.leaving"}, index]}]}
    doc.bind(f"page-{ident}.display", f"page-{ident}", "display", {"op": "select", "args": [shown, "block", "none"]})
    page_height = height - PAGE_TOP - PROMPT_BOTTOM - PROMPT_H - 16
    return group(f"page-{ident}", {**absolute(left=INSET, top=PAGE_TOP, width=width - 2 * INSET, height=page_height),
                                   "display": keyword("none"), "opacity": number(1)}, children)


def handoff_page(doc: Document, index: int, ident: str, width: float, height: float) -> tuple[dict, str]:
    """An interim page: it says the page opens in the classic menu and offers
    that as its primary action, which records the page and runs mpStockPage."""
    event = f"stock_{ident}"
    doc.events[event] = [{"op": "setState", "values": {"card.stock_page": index}}, {"op": "action", "action": "mpStockPage"}]
    primary = f"page-{ident}-open"
    page_width = width - 2 * INSET
    note = label(f"page-{ident}-note", HANDOFF_NOTE, {**absolute(left=0, top=0, width=page_width, height=24),
                 **typeface("lowpixel", 17, 24, [1, 1, 1, 0.8]), "white-space": keyword("nowrap")})
    # The plate fits its label in every language: 26 dp before it, 20 dp of
    # fade after it.
    plate_width = max(300.0, max(b.text_width("marine", text, 20) for text in table_text(HANDOFF_ACTION).values()) + 46)
    if plate_width > page_width:
        raise SystemExit(f"the hand-off action needs {plate_width:.0f} dp, past the page's {page_width:g} dp")
    plate = in_game_plate(doc, primary, HANDOFF_ACTION, 0, 36, width=round(plate_width, 3), primary=True, event=event)
    return page_group(doc, index, ident, width, height, [note, plate], [primary]), primary


# ---------------------------------------------------------------- Team page

TEAM_SLOTS = 3
SLOT_TOP, SLOT_PITCH = 50.0, 62.0
SLOT_W = 640.0                # a slot's plate; its reason or detail runs under the label
ERROR = "#E46D56"             # an unavailable action's reason (section 14.18)
MP_MARINE, MP_STROGG, MP_SPECTATOR, MP_NEUTRAL = "#6AA42B", "#FF7B04", "#999999", "#8B964B"
# Every label a slot can show, in every language: its own strings, and the
# join form with each team's name.
SLOT_LABELS = ("#str_231014", "#str_231016", "#str_231017", "#str_231018", "#str_200195")
JOIN_FORMAT, TEAM_NAMES = "#str_231015", ("#str_200197", "#str_200199")


def any_text(key: str) -> dict:
    """`key`'s text in every shipped language, from any of its tables (the
    English table where a language's own lacks it, as the engine falls back)."""
    import re
    texts = {}
    for language in ("english",) + tuple(b.LANGUAGES):
        for path in sorted(b.STRINGS.glob(f"{language}_*.lang")):
            for line in path.read_text(encoding="utf-8").splitlines():
                match = re.match(r'\s*"(#str_\d+)"\s+"(.*)"\s*$', line)
                if match and match.group(1) == key:
                    texts[language] = match.group(2)
    return {language: texts.get(language, texts["english"]) for language in b.LANGUAGES}


def check_slot_labels() -> None:
    """Fail generation when a slot's label and lock would leave the plate."""
    room = SLOT_W - 26 - 20 - 20       # after the marker, before the lock and the fade
    widest = {}
    for key in SLOT_LABELS:
        for language, text in any_text(key).items():
            widest[(key, language)] = b.text_width("marine", text, 20)
    formats = table_text(JOIN_FORMAT)
    for team in TEAM_NAMES:
        for language, name in any_text(team).items():
            widest[(JOIN_FORMAT + " " + team, language)] = b.text_width("marine", formats[language].replace("%s", name), 20)
    over = {key: round(width) for key, width in widest.items() if width > room}
    if over:
        raise SystemExit(f"Team page labels past their {room:g} dp: {over}")


def padlock(ident: str, tint: list) -> dict:
    """The lock after an unavailable action's label: a shackle over a body."""
    return vector(ident, {"position": keyword("relative"), "display": keyword("none"), "width": length(12), "height": length(14),
                          "margin-left": length(8), "flex-shrink": number(0)}, [
        path("shackle", [(3, 7), (3, 3.5), (4.5, 1.5), (7.5, 1.5), (9, 3.5), (9, 7)], closed=False, stroke=stroke(solid(tint), 1.5)),
        path("body", [(1, 6.5), (11, 6.5), (11, 13.5), (1, 13.5)], fill=solid(tint)),
    ])


def slot_plate(doc: Document, index: int, width: float) -> tuple[dict, str]:
    """A Team page action: an in-game plate whose label, availability and
    reason the game publishes (mp.action<i>.*). An unavailable action stays in
    place, dimmed, with a lock after its label and its reason in the error
    color on the plate; choosing it shakes the plate for 300 ms and pulses the
    reason, and nothing else happens. An available one records its slot and
    runs mpTeamAction, which the game derives again from the player's state."""
    ident = f"team-slot-{index}"
    key = f"mp.action{index}"
    for name, kind in (("shown", "boolean"), ("available", "boolean"), ("label", "string"), ("reason", "string"), ("detail", "string")):
        doc.state[f"{key}.{name}"] = {"type": kind, "initial": False if kind == "boolean" else ""}
    plate = in_game_plate(doc, ident, PLACEHOLDER, 0, 0, width=width, primary=index == 0, event=f"team_slot_{index}")
    # The label leaves the plate's own box for a row with the lock after it.
    label_node = next(child for child in plate["children"] if child["id"] == f"{ident}-label")
    plate["children"].remove(label_node)
    label_node["properties"].update({"position": keyword("relative"), "display": keyword("block"), "flex-shrink": number(1),
                                     "min-width": length(0), "overflow": keyword("hidden")})
    for prop in ("left", "top", "width"):
        label_node["properties"].pop(prop, None)
    doc.bind(f"{ident}-label.text", f"{ident}-label", "text", {"state": f"{key}.label"})
    lock = padlock(f"{ident}-lock", rgb(ERROR))
    unavailable = {"op": "!", "args": [{"state": f"{key}.available"}]}
    doc.bind(f"{ident}-lock.display", f"{ident}-lock", "display", {"op": "select", "args": [unavailable, "block", "none"]})
    row = group(f"{ident}-row", {**absolute(left=26, top=0, width=width - 46, height=45), "display": keyword("flex"),
                                 "flex-direction": keyword("row"), "align-items": keyword("center"), "pointer-events": keyword("none")},
                [label_node, lock])
    plate["children"].append(row)
    # The plate dims with its label; the reason beside it keeps its color.
    plate["properties"]["opacity"] = number(1)
    doc.bind(f"{ident}.opacity", ident, "opacity", {"op": "select", "args": [{"state": f"{key}.available"}, 1, 0.6]})
    side = {**absolute(left=26, top=40, width=width - 26, height=18), "white-space": keyword("nowrap"), "overflow": keyword("hidden"),
            "display": keyword("none")}
    reason = label(f"{ident}-reason", PLACEHOLDER, {**side, **typeface("lowpixel", 14, 18, rgb(ERROR)), "opacity": number(1)})
    detail = label(f"{ident}-detail", PLACEHOLDER, {**side, **typeface("lowpixel", 14, 18, [1, 1, 1, 0.7])})
    doc.bind(f"{ident}-reason.text", f"{ident}-reason", "text", {"state": f"{key}.reason"})
    doc.bind(f"{ident}-detail.text", f"{ident}-detail", "text", {"state": f"{key}.detail"})
    doc.bind(f"{ident}-reason.display", f"{ident}-reason", "display", {"op": "select", "args": [unavailable, "block", "none"]})
    doc.bind(f"{ident}-detail.display", f"{ident}-detail", "display",
             {"op": "select", "args": [{"state": f"{key}.available"}, "block", "none"]})
    holder = group(f"{ident}-slot", {**absolute(left=0, top=SLOT_TOP + SLOT_PITCH * index, width=width, height=58),
                                     "transform": transform(), "display": keyword("none")}, [plate, reason, detail])
    doc.bind(f"{ident}-slot.display", f"{ident}-slot", "display", {"op": "select", "args": [{"state": f"{key}.shown"}, "block", "none"]})
    shake = f"shake-{ident}"
    doc.timelines.add(shake, 300, [
        track(f"{ident}-slot", "transform", [(0, transform()), (50, transform(tx=-6)), (110, transform(tx=6)), (170, transform(tx=-4)),
                                             (230, transform(tx=3)), (300, transform())]),
        track(f"{ident}-reason", "opacity", [(0, number(1)), (100, number(0.35)), (200, number(1)), (300, number(1))]),
    ])
    doc.events[f"team_slot_{index}"] = [
        {"op": "if", "condition": {"state": f"{key}.available"},
         "then": [{"op": "setState", "values": {"card.team_action": index}}, {"op": "action", "action": "mpTeamAction"}],
         "else": [{"op": "playTimeline", "timeline": shake}]},
    ]
    return holder, ident


def team_page(doc: Document, index: int, ident: str, width: float, height: float) -> tuple[dict, str]:
    """The Team page (section 14.18): the player's team in its header band
    with its score and both teams' sizes (spectators and deathmatch their own
    bands), the actions the game offers now, and the last three chat lines."""
    check_slot_labels()
    page_width = width - 2 * INSET
    page_height = height - PAGE_TOP - PROMPT_BOTTOM - PROMPT_H - 16
    doc.state.update({
        "card.team_action": {"type": "number", "initial": -1},
        "mp.team.band": {"type": "string", "initial": ""},
        "mp.team.band_color": {"type": "number", "initial": 3},
        "mp.team.band_score": {"type": "string", "initial": ""},
        "mp.team.band_detail": {"type": "string", "initial": ""},
        **{f"mp.chat{line}": {"type": "string", "initial": ""} for line in range(3)},
    })
    band_h, cut = 36.0, 8.0
    bands = []
    for color_index, tint in enumerate((MP_MARINE, MP_STROGG, MP_SPECTATOR, MP_NEUTRAL)):
        # The header band (section 6): an upper-leading cut, top and leading
        # rails, the fill full to half the width and fading toward the end.
        node = f"team-band-{color_index}"
        bands.append(vector(node, {**absolute(left=0, top=0, width=page_width, height=band_h), "display": keyword("none")}, [
            path("fill", [(cut, 0), ({"fraction": 1}, 0), ({"fraction": 1}, band_h), (0, band_h), (0, cut)],
                 fill=linear((0, 0), ({"fraction": 1}, 0), [(0, rgb(tint, 0.49)), (0.5, rgb(tint, 0.49)), (0.75, rgb(tint, 0.25)),
                                                         (0.95, rgb(tint, 0.05)), (1, rgb(tint, 0))])),
            path("rail", [(0.75, band_h), (0.75, cut), (cut, 0.75), ({"fraction": 0.6}, 0.75)], closed=False,
                 stroke=stroke(linear((0, 0), ({"fraction": 0.6}, 0), [(0, rgb(tint)), (0.7, rgb(tint)), (1, rgb(tint, 0))]), 1.5)),
        ]))
        doc.bind(f"{node}.display", node, "display",
                 {"op": "select", "args": [{"op": "==", "args": [{"state": "mp.team.band_color"}, color_index]}, "block", "none"]})
    band_title = label("team-band-title", PLACEHOLDER, {**absolute(left=20, top=0, width=page_width * 0.5, height=band_h),
                       **typeface("marine", 20, band_h, [1, 1, 1, 0.95]), "white-space": keyword("nowrap")})
    band_score = label("team-band-score", PLACEHOLDER, {**absolute(left=page_width * 0.5, top=0, width=page_width * 0.2, height=band_h),
                       **typeface("lowpixel", 20, band_h, rgb(VALUE)), "text-align": keyword("right"), "white-space": keyword("nowrap")})
    band_detail = label("team-band-detail", PLACEHOLDER, {**absolute(left=page_width * 0.72, top=0, width=page_width * 0.26, height=band_h),
                        **typeface("lowpixel", 17, band_h, [1, 1, 1, 0.8]), "white-space": keyword("nowrap")})
    doc.bind("team-band-title.text", "team-band-title", "text", {"state": "mp.team.band"})
    doc.bind("team-band-score.text", "team-band-score", "text", {"state": "mp.team.band_score"})
    doc.bind("team-band-detail.text", "team-band-detail", "text", {"state": "mp.team.band_detail"})
    slots, controls = [], []
    for slot in range(TEAM_SLOTS):
        holder, control = slot_plate(doc, slot, min(page_width, SLOT_W))
        slots.append(holder)
        controls.append(control)
    chat = [label(f"team-chat-{line}", PLACEHOLDER, {**absolute(left=0, top=page_height - 22 * (3 - line), width=page_width, height=20),
                  **typeface("lowpixel", 15, 20, [1, 1, 1, 0.65]), "white-space": keyword("nowrap"), "overflow": keyword("hidden")})
            for line in range(3)]
    for line in range(3):
        doc.bind(f"team-chat-{line}.text", f"team-chat-{line}", "text", {"state": f"mp.chat{line}"})
    doc.session("mpTeamAction", "mpTeamAction")
    children = [*bands, band_title, band_score, band_detail, *slots, *chat]
    return page_group(doc, index, ident, width, height, children, controls), controls[0]


# -------------------------------------------------------------- Server page

ROTATION_SLOTS = 16
RULES = ("#str_231023", "#str_231024", "#str_231025", "#str_200038", "#str_231026", "#str_231027", "#str_231028")
HEADING = [0.545, 0.588, 0.294, 1]   # #8B964B, the multiplayer headings' olive


def server_page(doc: Document, index: int, ident: str, width: float, height: float) -> tuple[dict, str]:
    """The Server page (section 14.18): the name and address, the server's
    message in #FFFF8D, the rules in two columns (mode, map, limits, players,
    friendly fire, balance and next map) and the map rotation, the current map
    in orange. It has no actions; its tab keeps the focus."""
    page_width = width - 2 * INSET
    doc.state.update({
        "mp.server.name": {"type": "string", "initial": ""},
        "mp.server.address": {"type": "string", "initial": ""},
        "mp.server.message": {"type": "string", "initial": ""},
        **{f"mp.rule{rule}": {"type": "string", "initial": ""} for rule in range(len(RULES))},
        **{f"mp.rotation{slot}": {"type": "string", "initial": ""} for slot in range(ROTATION_SLOTS)},
        "mp.rotation_count": {"type": "number", "initial": 0},
        "mp.rotation_current": {"type": "number", "initial": -1},
    })
    name = label("server-name", PLACEHOLDER, {**absolute(left=0, top=0, width=page_width, height=28),
                 **typeface("marine", 20, 28, [1, 1, 1, 0.9]), "white-space": keyword("nowrap"), "overflow": keyword("hidden")})
    address_label = label("server-address-label", "#str_231030", {**absolute(left=0, top=30, width=120, height=20),
                          **typeface("lowpixel", 14, 20, HEADING), "white-space": keyword("nowrap")})
    address = label("server-address", PLACEHOLDER, {**absolute(left=124, top=30, width=page_width - 124, height=20),
                    **typeface("profont", 15, 20, [1, 1, 1, 0.75]), "white-space": keyword("nowrap")})
    message = label("server-message", PLACEHOLDER, {**absolute(left=0, top=56, width=page_width, height=60),
                    **typeface("lowpixel", 17, 20, b.rgb("#FFFF8D")), "white-space": keyword("pre-line"), "overflow": keyword("hidden")})
    for node, state in (("server-name", "mp.server.name"), ("server-address", "mp.server.address"), ("server-message", "mp.server.message")):
        doc.bind(f"{node}.text", node, "text", {"state": state})
    # Two columns of rules, the left one wider for the limits; each column's
    # labels take the width of its longest in any language.
    rules = []
    split = round(page_width * 0.55, 3)
    columns_x = (0.0, split)
    columns_w = (split - 12, page_width - split)
    label_w = [max(b.text_width("lowpixel", text, 14) for key in RULES[start:stop] for text in any_text(key).values()) + 6
               for start, stop in ((0, 4), (4, len(RULES)))]
    for rule, key in enumerate(RULES):
        side = 0 if rule < 4 else 1
        left, top = columns_x[side], 124 + 24 * (rule % 4)
        rules.append(label(f"server-rule-{rule}-label", key, {**absolute(left=left, top=top, width=round(label_w[side], 3), height=22),
                           **typeface("lowpixel", 14, 22, HEADING), "white-space": keyword("nowrap")}))
        value_left = round(left + label_w[side] + 6, 3)
        value = label(f"server-rule-{rule}", PLACEHOLDER, {**absolute(left=value_left, top=top, width=round(columns_w[side] - label_w[side] - 6, 3),
                      height=22), **typeface("lowpixel", 15, 22, [1, 1, 1, 0.85]), "white-space": keyword("nowrap"), "overflow": keyword("hidden")})
        doc.bind(f"server-rule-{rule}.text", f"server-rule-{rule}", "text", {"state": f"mp.rule{rule}"})
        rules.append(value)
    heading = label("server-rotation-label", "#str_231029", {**absolute(left=0, top=228, width=page_width, height=20),
                    **typeface("lowpixel", 14, 20, HEADING), "white-space": keyword("nowrap")})
    rotation = []
    columns, pitch_x = 4, page_width / 4
    for slot in range(ROTATION_SLOTS):
        node = f"server-rotation-{slot}"
        rotation.append(label(node, PLACEHOLDER, {**absolute(left=pitch_x * (slot % columns), top=250 + 19 * (slot // columns),
                                                            width=pitch_x - 8, height=19),
                              **typeface("lowpixel", 15, 19, [1, 1, 1, 0.7]), "white-space": keyword("nowrap"), "overflow": keyword("hidden"),
                              "display": keyword("none")}))
        doc.bind(f"{node}.text", node, "text", {"state": f"mp.rotation{slot}"})
        doc.bind(f"{node}.display", node, "display",
                 {"op": "select", "args": [{"op": "<", "args": [slot, {"state": "mp.rotation_count"}]}, "block", "none"]})
        current = {"op": "==", "args": [{"state": "mp.rotation_current"}, slot]}
        hot = rgb(ORANGE)
        doc.bind(f"{node}.color", node, "color", [{"op": "select", "args": [current, hot[channel], rest]}
                                                  for channel, rest in enumerate((1, 1, 1, 0.7))])
    children = [name, address_label, address, message, *rules, heading, *rotation]
    return page_group(doc, index, ident, width, height, children, []), f"tab-{ident}"


PAGE_BUILDERS = {"team": team_page, "server": server_page}


def prompt_row(width: float, height: float, back_verb: str, trailing: list) -> dict:
    """The prompt bar inside the card (section 14.18): Resume or Spectate on
    the back key, Tabs on Q and E, Select on Enter, then the trailing
    actions, the destructive one last."""
    def prompt(ident: str, keys: list, verb: str) -> list:
        caps = [keycap(f"prompt-{ident}-{n}", key) for n, key in enumerate(keys)]
        for cap in caps:
            cap["properties"]["margin-right"] = length(3 if cap is not caps[-1] else 6)
        return caps + [label(f"prompt-{ident}-verb", verb, {"position": keyword("relative"), "display": keyword("block"),
                       "margin-right": length(18), **typeface("marine", 14, PROMPT_H, [1, 1, 1, 0.8]),
                       "white-space": keyword("nowrap")})]
    items = (prompt("back", [KEY_ESCAPE], back_verb) + prompt("tabs", [KEY_PREVIOUS, KEY_NEXT], VERB_TABS) +
             prompt("select", [KEY_ENTER], VERB_SELECT))
    spacer = group("prompt-spacer", {"position": keyword("relative"), "display": keyword("block"), "flex-grow": number(1),
                                     "height": length(PROMPT_H)})
    return group("prompts", {**absolute(left=INSET, top=height - PROMPT_BOTTOM - PROMPT_H, width=width - 2 * INSET, height=PROMPT_H),
                             "display": keyword("flex"), "flex-direction": keyword("row"), "align-items": keyword("center")},
                 items + [spacer] + trailing)


def backdrop(doc: Document) -> list:
    """The view behind the card, softened and never dimmed (section 14.18 with
    modal.softfocus's values, decision D1); with the opaque-backing option,
    or where the renderer cannot soften it, a centred darkening scrim with a
    vignette stands in (section 13.6)."""
    doc.state["soft_focus"] = {"type": "boolean", "initial": False, "cvar": "ui_retainedSoftFocus"}
    softened = group("scene-softfocus", {**FULL, "display": keyword("none"), "backdrop-blur": length(SOFT_FOCUS_BLUR),
                                         "backdrop-saturate": number(SOFT_FOCUS_SATURATION)})
    whole = [(0, 0), ({"fraction": 1}, 0), ({"fraction": 1}, {"fraction": 1}), (0, {"fraction": 1})]
    scrim = vector("scrim", {**FULL, "display": keyword("block"), "opacity": number(1)}, [
        path("dim", whole, fill=solid([0, 0, 0, 0.45])),
        path("vignette", whole, fill=linear((0, 0), (0, {"fraction": 1}),
                                            [(0, [0, 0, 0, 0.6]), (0.3, [0, 0, 0, 0]), (0.7, [0, 0, 0, 0]), (1, [0, 0, 0, 0.6])])),
    ])
    doc.bind("scene-softfocus.display", "scene-softfocus", "display", {"op": "select", "args": [{"state": "soft_focus"}, "block", "none"]})
    doc.bind("scrim.display", "scrim", "display", {"op": "select", "args": [{"state": "soft_focus"}, "none", "block"]})
    return [softened, scrim]


def card_motion(doc: Document, tabs: list, primaries: list) -> None:
    """Section 14.18 motion and the tab programs.

    open      the softening ramps in over 250 ms while the card rises 12 dp and
              fades in over 150 ms (ease-out); under reduced motion no rise,
              and the softening and fade take 80 ms. The current page's
              primary action takes focus.
    release   every way out closes the card at once; the softening releases
              over 250 ms while the session keeps drawing the closed card.
    tab_<id>  switches to a tab at once and cross-fades the page over 150 ms,
              then focuses its primary action; onTabPrevious and onTabNext
              wrap around the strip.
    """
    blur, tint = length(SOFT_FOCUS_BLUR), number(SOFT_FOCUS_SATURATION)
    none_blur, none_tint = length(0), number(1)

    def opening(ident: str, ramp: float, fade: float, rise: float, essential: bool | None = None) -> None:
        # Each opening restarts from nothing at 1 ms: a play retargets only its
        # first key from the current value, and the document outlives each open.
        doc.timelines.add(ident, max(ramp, fade), essential=essential, tracks=[
            track("scene-softfocus", "backdrop-blur", [(0, none_blur), (1, none_blur), (ramp, blur)]),
            track("scene-softfocus", "backdrop-saturate", [(0, none_tint), (1, none_tint), (ramp, tint)]),
            track("scrim", "opacity", [(0, number(0)), (1, number(0)), (ramp, number(1))]),
            track("card", "opacity", [(0, number(0)), (1, number(0), EASE_OUT), (fade, number(1))]),
            track("card", "transform", [(0, transform(ty=rise)), (1, transform(ty=rise), EASE_OUT), (fade, transform())]),
        ])
    opening("open", OPEN_MS, RISE_MS, RISE_DP)
    # Reduced motion's own opening plays as authored: the runtime would
    # otherwise jump the softening to its end instead of ramping it in 80 ms.
    opening("open-reduced", REDUCED_MS, REDUCED_MS, 0, essential=True)
    doc.timelines.add("release", RELEASE_MS, [
        track("scene-softfocus", "backdrop-blur", [(0, blur), (RELEASE_MS, none_blur)]),
        track("scene-softfocus", "backdrop-saturate", [(0, tint), (RELEASE_MS, none_tint)]),
        track("scrim", "opacity", [(0, number(1)), (RELEASE_MS, number(0))]),
    ])
    doc.timelines.add("unrelease", OPEN_MS, [
        track("scene-softfocus", "backdrop-blur", [(0, none_blur), (1, none_blur), (OPEN_MS, blur)]),
        track("scene-softfocus", "backdrop-saturate", [(0, none_tint), (1, none_tint), (OPEN_MS, tint)]),
        track("scrim", "opacity", [(0, number(0)), (1, number(0)), (OPEN_MS, number(1))]),
        track("card", "opacity", [(0, number(1)), (OPEN_MS, number(1))]),
    ])
    count = len(tabs)

    def focus_current() -> dict:
        steps: list = []
        for index in reversed(range(count)):
            steps = [{"op": "if", "condition": {"op": "==", "args": [{"state": "card.tab"}, index]},
                      "then": [{"op": "focus", "control": primaries[index]}], **({"else": steps} if steps else {})}]
        return steps[0]
    for index, (ident, _key, _window) in enumerate(tabs):
        page = f"page-{ident}"
        # The page arriving fades in from nothing; every other page fades from
        # where it stands to nothing, which leaves hidden pages at 0.
        doc.timelines.add(f"show-{ident}", PAGE_FADE_MS, [
            track(page, "opacity", [(0, number(0)), (1, number(0)), (PAGE_FADE_MS, number(1))]),
            *[track(f"page-{other}", "opacity", [(0, number(1)), (PAGE_FADE_MS, number(0))])
              for other, _k, _w in tabs if other != ident],
        ], complete="pageShown")
        doc.events[f"tab_{ident}"] = [
            {"op": "if", "condition": {"op": "!=", "args": [{"state": "card.tab"}, index]},
             "then": [{"op": "setState", "values": {"card.leaving": {"state": "card.tab"}, "card.tab": index}},
                      {"op": "playTimeline", "timeline": f"show-{ident}"},
                      {"op": "focus", "control": primaries[index]}]},
        ]
    doc.events["pageShown"] = [{"op": "setState", "values": {"card.leaving": -1}}]
    for name, step in (("onTabPrevious", -1), ("onTabNext", 1)):
        steps: list = []
        for index in reversed(range(count)):
            target = tabs[(index + step) % count][0]
            steps = [{"op": "if", "condition": {"op": "==", "args": [{"state": "card.tab"}, index]},
                      "then": [{"op": "call", "event": f"tab_{target}"}], **({"else": steps} if steps else {})}]
        doc.events[name] = steps
    doc.events["open"] = [
        {"op": "setState", "values": {"card.released": False, "card.leaving": -1}},
        {"op": "if", "condition": {"state": "reduced_motion"},
         "then": [{"op": "playTimeline", "timeline": "open-reduced"}], "else": [{"op": "playTimeline", "timeline": "open"}]},
        focus_current(),
    ]
    doc.events["release"] = [{"op": "setState", "values": {"card.released": True}}, {"op": "playTimeline", "timeline": "release"}]
    doc.events["onActivate"] = [{"op": "if", "condition": {"state": "card.released"},
                                 "then": [{"op": "setState", "values": {"card.released": False}},
                                          {"op": "playTimeline", "timeline": "unrelease"}]}]
    doc.events["onBack"] = [{"op": "action", "action": "mpClose"}]


def escape_document() -> dict:
    """The Escape card (section 14.18), opened with the menu key during a
    match, Resume leading its prompt bar. The Team and Server pages are built;
    the others hand off to their stock pages for now."""
    doc = Document("openq4.mp_escape")
    width, height = fitted_card_width([key for _, key, _ in ESCAPE_TABS]), ESCAPE_H
    doc.state.update({
        "card.tab": {"type": "number", "initial": 0},
        "card.leaving": {"type": "number", "initial": -1},
        "card.stock_page": {"type": "number", "initial": -1},
        "card.released": {"type": "boolean", "initial": False},
        "reduced_motion": {"type": "boolean", "initial": False, "cvar": "ui_retainedReducedMotion"},
        "mp.title": {"type": "string", "initial": ""},
        "mp.mode": {"type": "string", "initial": ""},
        "mp.clock": {"type": "string", "initial": ""},
        "mp.score": {"type": "string", "initial": ""},
    })
    for verb in ("mpClose", "mpMainMenu", "mpDisconnect", "mpStockPage"):
        doc.session(verb, verb)
    trailing = [bound_text("header-mode", doc, "mp.mode", "lowpixel", 15, [1, 1, 1, 0.7]),
                bound_text("header-clock", doc, "mp.clock", "lowpixel", 17, rgb(VALUE)),
                bound_text("header-score", doc, "mp.score", "lowpixel", 15, [1, 1, 1, 0.85])]
    pages, primaries = [], []
    for index, (ident, _key, _window) in enumerate(ESCAPE_TABS):
        page, primary = PAGE_BUILDERS.get(ident, lambda d, i, n, w, h: handoff_page(d, i, n, w, h))(doc, index, ident, width, height)
        pages.append(page)
        primaries.append(primary)
    actions = [link(doc, "prompt-mainmenu", MAIN_MENU, action="mpMainMenu"),
               link(doc, "prompt-disconnect", DISCONNECT, event="disconnectModalShow")]
    actions[-1]["properties"]["margin-right"] = length(0)
    card = group("card", {"position": keyword("absolute"), "left": length(50, "%"), "top": length(50, "%"),
                          "width": length(width), "height": length(height), "margin-left": length(-width / 2),
                          "margin-top": length(-height / 2), "opacity": number(0), "transform": transform()},
                 [card_frame(width, height), *card_header(doc, width, "mp.title", trailing), *tab_strip(doc, width, ESCAPE_TABS),
                  *pages, prompt_row(width, height, VERB_RESUME, actions)])
    disconnect = confirmation(doc, "disconnectModal", DISCONNECT, DISCONNECT_BODY, "mpDisconnect")
    # Every way out hides the card and its modal at once; the backdrop
    # releases behind them.
    chrome = group("chrome", {**FULL, "display": keyword("block")}, [card, disconnect])
    doc.bind("chrome.display", "chrome", "display", {"op": "select", "args": [{"state": "card.released"}, "none", "block"]})
    root = group("screen", {**FULL, "font-family": b.font("marine"), "font-size": length(16), "color": colour([1, 1, 1, 0.8])},
                 [*backdrop(doc), chrome])
    card_motion(doc, ESCAPE_TABS, primaries)
    return doc.build(root)
