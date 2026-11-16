"""Botanical SVG with bounded ambient motion; no clock or network reads."""

import copy
import hashlib
import math
import xml.etree.ElementTree as ET
from datetime import timedelta
from importlib.resources import files

from .growth import stage, traits
from .models import iso_day
from .state import validate_state

RENDERER_VERSION = 3
SLOTS = {
    "branches": 6,
    "cover": 8,
    "creatures": 4,
    "fireflies": 8,
    "flowers": 10,
    "leaves": 6,
    "mushrooms": 9,
    "ripples": 6,
    "seedlings": 6,
}
# Permanent development is independent of the recent trait counts.
STAGES = {
    "seed": (0.18, 2),
    "sprout": (0.32, 4),
    "grove": (0.55, 7),
    "mature": (0.8, 10),
    "sanctuary": (1, 13),
}
ANCHORS = {"plant": (604, 268), "pond": (230, 265)}
CANOPY_CENTERS = [(500, 100), (590, 70), (380, 125), (680, 115), (610, 130), (440, 115)]
EXTRA_CANOPY = [(350, 171), (430, 170), (490, 155), (555, 160), (660, 150), (700, 190)]


MOTION_CSS = """
.ambient { transform-box: fill-box; transform-origin: center; }
.leaf-sway {
  transform-origin: center bottom; animation: leaf-sway 7s ease-in-out infinite;
}
.firefly-travel { animation: firefly-travel 11s ease-in-out infinite; }
.pond-ripple { animation: pond-ripple 8s ease-in-out infinite; }
[data-motion="calm"] .leaf-sway { animation-name: leaf-calm; animation-duration: 17s; }
[data-motion="calm"] .firefly-travel {
  animation-name: firefly-calm; animation-duration: 23s;
}
[data-motion="calm"] .pond-ripple {
  animation-name: ripple-calm; animation-duration: 19s;
}
@keyframes leaf-sway {
  0%, 100% { transform: rotate(-2deg); }
  50% { transform: rotate(3deg); }
}
@keyframes firefly-travel {
  0%, 100% { transform: translate(-3px, 2px); opacity: 0.65; }
  50% { transform: translate(4px, -6px); opacity: 1; }
}
@keyframes pond-ripple {
  0%, 100% { transform: scale(0.9); opacity: 0.6; }
  50% { transform: scale(1.2); opacity: 1; }
}
@keyframes leaf-calm {
  0%, 100% { transform: rotate(-0.5deg); }
  50% { transform: rotate(0.75deg); }
}
@keyframes firefly-calm {
  0%, 100% { transform: translate(-1px, 0.5px); opacity: 0.8; }
  50% { transform: translate(1px, -1.5px); opacity: 1; }
}
@keyframes ripple-calm {
  0%, 100% { transform: scale(0.98); opacity: 0.8; }
  50% { transform: scale(1.04); opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  .ambient, .ambient * { animation: none !important; transition: none !important; }
}
""".strip()


def _node(parent, tag, **attributes):
    return ET.SubElement(
        parent,
        tag,
        {
            key.rstrip("_").replace("_", "-"): str(value)
            for key, value in attributes.items()
        },
    )


def _variation(subject, feature, index):
    # Independent salts avoid RNG iteration coupling when another trait changes.
    seed = f"terrarium-seed-v{subject['seed_version']}:{subject['id']}"
    digest = hashlib.sha256(f"{seed}:{feature}:{index}".encode()).digest()
    return int.from_bytes(digest[:2], "big") / 65535


def _position(subject, feature, index, x, y):
    dx = round(8 * _variation(subject, feature + "-x", index) - 4, 2)
    dy = round(4 * _variation(subject, feature + "-y", index) - 2, 2)
    return f"translate({x + dx:.2f} {y + dy:.2f})"


def _slots(value, name):
    return math.ceil(value * SLOTS[name])


def _motion(parent, subject, family, index):
    # CSS transforms act on a child, preserving the parent's placement in all modes.
    delay = 12 * _variation(subject, "motion-" + family, index)
    return _node(
        parent, "g", class_=f"ambient {family}", style=f"animation-delay:-{delay:.2f}s"
    )


def _motion_mode(state):
    last = iso_day(state["last_complete_activity_day"])
    active = any(
        state["days"][(last - timedelta(days=offset)).isoformat()][metric]
        for offset in range(7)
        for metric in ("prs", "reviews", "issues")
    )
    return "active" if active else "calm"


def _fragment(parent, fragment, **attributes):
    return _node(parent, "use", href=f"#{fragment}", **attributes)


def _growth_transform(scale):
    x, y = ANCHORS["plant"]
    return f"translate({x} {y}) scale({scale}) translate({-x} {-y})"


def _placed_piece(parent, subject, feature, index, fragment, target, origin, scale=1):
    pose = _position(subject, feature, index, *target)
    group = _node(
        parent,
        "g",
        id=f"{feature}-{index}",
        transform=f"{pose} scale({scale}) translate({-origin[0]} {-origin[1]})",
    )
    _fragment(group, fragment)
    return group


def render(state):
    """Assemble a bounded paper-cut habitat from validated, explicit state.

    Native vector pieces are packaged resources, not a baked background image.
    Growth and recent traits select geometry; browser time only drives ambient CSS.
    """
    validate_state(state)
    subject = state["subject"]
    normalized = traits(state["current_traits"])
    xp = sum(
        d["activity_xp_awarded"] + d["popularity_xp_awarded"]
        for d in state["days"].values()
    )
    growth_stage = stage(xp)
    scale, canopy_count = STAGES[growth_stage]
    root = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "viewBox": "0 0 900 360",
            "role": "img",
            "aria-labelledby": "scene-title scene-desc",
            "data-art": "papercut",
            "data-stage": growth_stage,
            "data-renderer-version": str(RENDERER_VERSION),
            "data-motion": _motion_mode(state),
        },
    )
    _node(
        root, "title", id="scene-title"
    ).text = f"{subject['login']}'s GitHub terrarium"
    _node(root, "desc", id="scene-desc").text = (
        f"A {growth_stage} paper-cut habitat for public GitHub user {subject['id']}. "
        f"Activity complete through {state['last_complete_activity_day']} UTC. "
        "Stars bring flowers and fireflies; forks add branches and seedlings; "
        "Pull requests enrich the canopy; reviews enrich the pond; "
        "issues add mushrooms."
    )
    _node(root, "style").text = MOTION_CSS
    asset = ET.fromstring(
        files("github_terrarium.art").joinpath("papercut.svg").read_bytes()
    )
    definitions = copy.deepcopy(next(n for n in asset if n.tag.endswith("}defs")))
    for node in definitions.iter():
        node.tag = node.tag.removeprefix("{http://www.w3.org/2000/svg}")
    root.append(definitions)
    background = _node(root, "g", id="background")
    _node(background, "rect", width=900, height=360, fill="#f8dc8c")
    world = _node(root, "g", clip_path="url(#inside)")
    landscape = _node(world, "g", id="landscape-view")
    _fragment(landscape, "landscape")
    pond = _node(world, "g", id="pond")
    _fragment(pond, "water")
    if normalized["reviews"]:
        _fragment(pond, "pond-lilies")
    for index in range(_slots(normalized["reviews"], "ripples")):
        ripple = _node(
            pond,
            "g",
            id=f"ripple-{index}",
            transform=_position(
                subject, "ripple", index, 162 + index * 28, 263 + index % 2 * 5
            ),
        )
        _node(
            _motion(ripple, subject, "pond-ripple", index),
            "ellipse",
            rx=12,
            ry=2.4,
            fill="none",
            stroke="#b8dcd3",
            stroke_width="0.9",
        )
    for index in range(_slots(normalized["reviews"], "creatures")):
        creature = _node(
            pond,
            "g",
            id=f"creature-{index}",
            transform=_position(
                subject, "creature", index, 180 + index * 35, 262 + index % 2 * 6
            ),
        )
        _node(creature, "path", d="M-8 0Q0 -5 7 0Q0 5 -8 0L-11 -3V3Z", fill="#eedcb0")

    ground = _node(world, "g", id="ground")
    rocks = _node(ground, "g", transform=_position(subject, "rocks", 0, 0, 0))
    for fragment in ("rocks", "cattails", "fern-side"):
        _fragment(rocks, fragment)
    for index in range(_slots(normalized["issues"], "cover")):
        _placed_piece(
            ground,
            subject,
            "cover",
            index,
            "fern-side",
            (365 + index * 49, 274 - min(index, 4) * 3),
            (716, 246),
            0.45,
        )

    # Fork branches are independent of canopy slots, and point toward the light.
    branches = _node(world, "g", id="branches", transform=_growth_transform(scale))
    for index in range(_slots(normalized["forks"], "branches")):
        y = 240 - index * 14
        x = 500 - index % 3 * 28
        shape_id = f"fork-outline-{index}"
        _node(
            definitions,
            "path",
            id=shape_id,
            d=(
                f"M600 {y}Q550 {y - 8} {x} {y - 31}L{x} {y - 34}"
                f"Q554 {y - 12} 600 {y - 5}Z"
            ),
        )
        branch = _node(branches, "g", id=f"branch-{index}")
        _fragment(
            branch,
            shape_id,
            fill="#22301f",
            opacity="0.26",
            transform="translate(2.2 3)",
        )
        _fragment(branch, shape_id, fill="#463525")
    plant = _node(world, "g", id="plant", transform=_growth_transform(scale))
    for index in range(canopy_count // 2):
        _fragment(plant, f"canopy-back-{index % 6}")
    _fragment(plant, "tree-trunk")
    for index in range(canopy_count):
        leaf = _node(
            plant,
            "g",
            id=f"canopy-slot-{index}",
            transform=_position(subject, "canopy", index, 0, 0),
        )
        _fragment(_motion(leaf, subject, "leaf-sway", index), f"canopy-{index}")
    for index in range(_slots(normalized["prs"], "leaves")):
        x, y = CANOPY_CENTERS[index]
        extra = _node(
            plant,
            "g",
            id=f"extra-canopy-{index}",
            transform=(
                _position(subject, "extra-canopy", index, *EXTRA_CANOPY[index])
                + f" scale(0.55) translate({-x} {-y})"
            ),
        )
        _fragment(_motion(extra, subject, "leaf-sway", index + 13), f"canopy-{index}")

    seedlings = _node(world, "g", id="seedlings")
    for index, (x, y) in enumerate(
        [(110, 278), (370, 276), (430, 275), (500, 268), (745, 263), (810, 263)]
    ):
        if index >= _slots(normalized["forks"], "seedlings"):
            break
        _placed_piece(
            seedlings, subject, "seedling", index, "canopy-8", (x, y), (550, 112), 0.14
        )
    flowers = _node(world, "g", id="flowers")
    for index in range(_slots(normalized["stars"], "flowers")):
        flower = _node(
            flowers,
            "g",
            id=f"flower-slot-{index}",
            transform=_position(subject, "flower", index, 0, 0),
        )
        _fragment(flower, f"flower-{index}")
    mushrooms = _node(world, "g", id="mushrooms")
    targets = [
        (668, 256),
        (688, 256),
        (652, 258),
        (555, 261),
        (520, 264),
        (760, 262),
        (480, 274),
        (110, 278),
        (360, 275),
    ]
    origins = [(668, 256), (688, 256), (652, 258)]
    for index in range(_slots(normalized["issues"], "mushrooms")):
        _placed_piece(
            mushrooms,
            subject,
            "mushroom-slot",
            index,
            f"mushroom-{index % 3}",
            targets[index],
            origins[index % 3],
        )
    soil = _node(world, "g", id="soil")
    _fragment(soil, "soil-cutaway")
    roots = _node(world, "g", id="roots", transform=_growth_transform(scale))
    _fragment(roots, "tree-roots")
    for fragment in ("pebbles", "moss-rim", "ferns-front"):
        _fragment(world, fragment)
    fireflies = _node(world, "g", id="fireflies")
    positions = [
        (92, 96),
        (176, 150),
        (250, 104),
        (132, 196),
        (300, 196),
        (218, 222),
        (60, 150),
        (780, 214),
    ]
    for index in range(_slots(normalized["stars"], "fireflies")):
        item = _node(
            fireflies,
            "g",
            id=f"firefly-{index}",
            transform=_position(subject, "firefly", index, *positions[index]),
        )
        motion = _motion(item, subject, "firefly-travel", index)
        _node(motion, "circle", r=8, fill="url(#glow)")
        _node(motion, "circle", r=1.6, fill="#fffbe2")
    _node(
        root,
        "rect",
        x=0.5,
        y=0.5,
        width=899,
        height=359,
        rx=13.5,
        fill="none",
        stroke="#a9b08a",
    )
    identity = _node(root, "g", id="identity", fill="#3c4630", font_family="monospace")
    label = _node(identity, "text", x=26, y=31, font_size=23)
    label.text = f"{subject['login']} / terrarium"
    if len(subject["login"]) > 20:
        label.set("textLength", "620")
        label.set("lengthAdjust", "spacingAndGlyphs")
    _node(
        identity, "text", x=26, y=54, font_size=18
    ).text = f"Activity through {state['last_complete_activity_day']} UTC"
    _node(
        identity, "text", x=874, y=31, font_size=21, text_anchor="end"
    ).text = growth_stage.capitalize()
    return ET.tostring(root, encoding="utf-8", short_empty_elements=True) + b"\n"
