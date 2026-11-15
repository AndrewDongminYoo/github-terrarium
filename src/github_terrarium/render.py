"""Static botanical SVG from validated growth state; no clock or network reads."""

import copy
import hashlib
import math
import xml.etree.ElementTree as ET
from importlib.resources import files

from .growth import stage, traits
from .state import validate_state

RENDERER_VERSION = 1
# Maximum optional objects, independent of unbounded activity/stock counts.
SLOTS = {
    "branches": 6,
    "cover": 12,
    "creatures": 4,
    "fireflies": 8,
    "flowers": 12,
    "leaves": 8,
    "mushrooms": 9,
    "ripples": 6,
    "seedlings": 6,
}
STAGES = {
    "seed": (30, 2),
    "sprout": (65, 4),
    "grove": (104, 8),
    "mature": (142, 12),
    "sanctuary": (174, 16),
}
ANCHORS = {"plant": (430, 254), "pond": (620, 267)}


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


def _use(parent, name, x, y, width, height):
    return _node(parent, "use", href=f"#{name}", x=x, y=y, width=width, height=height)


def render(state):
    """Return canonical UTF-8 SVG bytes without mutating the validated state.

    State already carries logical dates and identity. Renderer version 1 has no
    animation: the static geometry is also the fallback for later motion work.
    """
    validate_state(state)
    subject = state["subject"]
    normalized = traits(state["current_traits"])
    xp = sum(
        day["activity_xp_awarded"] + day["popularity_xp_awarded"]
        for day in state["days"].values()
    )
    growth_stage = stage(xp)
    root = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "viewBox": "0 0 900 360",
            "role": "img",
            "aria-labelledby": "scene-title scene-desc",
            "data-stage": growth_stage,
            "data-renderer-version": str(RENDERER_VERSION),
        },
    )
    _node(
        root, "title", id="scene-title"
    ).text = f"{subject['login']}'s GitHub terrarium"
    _node(root, "desc", id="scene-desc").text = (
        f"A {growth_stage} habitat for public GitHub user {subject['id']}. "
        f"Activity complete through {state['last_complete_activity_day']} UTC. "
        "Stars bring flowers and fireflies; forks add branches and seedlings; "
        "pull requests add leaves; reviews enrich the pond; issues add mushrooms."
    )
    asset = ET.fromstring(
        files("github_terrarium.art").joinpath("botanical.svg").read_bytes()
    )
    definitions = copy.deepcopy(asset[0])
    for node in definitions.iter():
        node.tag = node.tag.removeprefix("{http://www.w3.org/2000/svg}")
    root.append(definitions)
    background = _node(root, "g", id="background")
    _node(background, "rect", width=900, height=360, fill="#f4f0e5")
    _node(
        background,
        "ellipse",
        cx=450,
        cy=299,
        rx=350,
        ry=17,
        fill="#d7d6c2",
        opacity="0.55",
    )
    vessel = _node(root, "g", id="vessel")
    bowl = "M177 56H723L777 232Q796 295 725 300H175Q104 295 123 232Z"
    _node(
        vessel,
        "path",
        d=bowl,
        fill="url(#glass-tint)",
        stroke="#a1b6a8",
        stroke_width="2",
    )
    _node(
        vessel,
        "path",
        d="M177 56Q450 42 723 56Q450 70 177 56Z",
        fill="#e2e8d7",
        stroke="#a1b6a8",
        stroke_width="2",
    )
    _node(
        vessel,
        "path",
        d="M163 138L140 220M151 129L147 145M735 121L765 223",
        fill="none",
        stroke="#ffffff",
        stroke_width="4",
        opacity="0.65",
        stroke_linecap="round",
    )
    soil = _node(root, "g", id="soil")
    _node(
        soil,
        "path",
        d="M129 254Q450 238 771 254Q776 296 725 300H175Q124 296 129 254Z",
        fill="#715a43",
    )
    _node(
        soil,
        "path",
        d="M132 270Q450 257 768 270L763 280Q450 266 137 281Z",
        fill="#a08862",
    )
    _node(
        soil,
        "path",
        d="M130 253Q450 237 770 253L768 263Q450 248 132 263Z",
        fill="#8e9970",
    )
    for index in range(16):
        pebble = _node(
            soil,
            "g",
            transform=_position(subject, "soil", index, 160 + index * 38, 284),
        )
        _node(pebble, "ellipse", rx="3", ry="1.5", fill="#c3aa7b")

    plant = _node(
        root, "g", id="plant", transform="translate(%s %s)" % ANCHORS["plant"]
    )
    height, leaves = STAGES[growth_stage]
    _node(plant, "ellipse", cx=0, cy=1, rx=10, ry=4, fill="#b69a60")
    _node(
        plant,
        "path",
        d=f"M0 0Q-12 {-height // 2} 0 {-height}",
        fill="none",
        stroke="#496748",
        stroke_width="4",
        stroke_linecap="round",
    )
    for index in range(leaves + _slots(normalized["prs"], "leaves")):
        # Each leaf has a fixed slot. Extra PR leaves do not shift existing ones.
        y = -18 - (index % leaves) * (height - 18) / max(1, leaves - 1)
        if index >= leaves:
            y = -height * (index - leaves + 0.5) / SLOTS["leaves"]
        side = -1 if index % 2 == 0 else 1
        leaf = _node(
            plant,
            "g",
            id=f"plant-leaf-{index}",
            transform=(
                _position(subject, "leaf", index, side * 2, round(y, 2))
                + f" scale({side} 1) rotate(-18)"
            ),
        )
        _use(leaf, "leaf", 0, -16, 35, 18)
    branches = _node(
        root, "g", id="branches", transform="translate(%s %s)" % ANCHORS["plant"]
    )
    for index in range(_slots(normalized["forks"], "branches")):
        side = -1 if index % 2 == 0 else 1
        branch = _node(
            branches,
            "g",
            id=f"branch-{index}",
            transform=_position(subject, "branch", index, 0, 0),
        )
        _node(
            branch,
            "path",
            d=f"M0 0Q{side * 33} {-24 - index * 9} {side * 60} {-44 - index * 10}",
            fill="none",
            stroke="#698350",
            stroke_width="2.5",
        )
        leaf = _node(
            branch,
            "g",
            transform=f"translate({side * 60} {-44 - index * 10}) scale({side} 1)",
        )
        _use(leaf, "leaf", 0, -16, 28, 16)

    pond = _node(root, "g", id="pond", transform="translate(%s %s)" % ANCHORS["pond"])
    _node(pond, "ellipse", rx=91, ry=20, fill="#bdb58c")
    _node(pond, "ellipse", cy=-2, rx=82, ry=15, fill="url(#pond-water)")
    _node(
        pond,
        "path",
        d="M-56 -6Q-19 -17 38 -9",
        fill="none",
        stroke="#d3e4c9",
        stroke_width="2",
        opacity="0.75",
    )
    for index in range(_slots(normalized["reviews"], "ripples")):
        ripple = _node(
            pond,
            "g",
            id=f"ripple-{index}",
            transform=_position(
                subject, "ripple", index, -56 + index * 21, -1 + index % 2 * 5
            ),
        )
        _node(ripple, "ellipse", rx=8, ry=2, fill="none", stroke="#d0dfbc")
    for index in range(_slots(normalized["reviews"], "creatures")):
        creature = _node(
            pond,
            "g",
            id=f"creature-{index}",
            transform=_position(
                subject, "creature", index, -40 + index * 25, -4 + index % 2 * 7
            ),
        )
        _use(creature, "pond-creature", -10, -5, 20, 10)

    ground = _node(root, "g", id="ground")
    for index in range(8 + _slots(normalized["issues"], "cover")):
        cover = _node(
            ground,
            "g",
            id=f"cover-{index}",
            transform=_position(
                subject, "cover", index, 163 + index * 28, 252 + index % 3 * 3
            ),
        )
        _node(
            cover,
            "path",
            d=(
                "M0 2Q-12 -14 -15 -10Q-4 -7 0 2Q-1 -17 5 -19"
                "Q7 -8 0 2Q12 -12 15 -8Q9 -5 0 2Z"
            ),
            fill="#71885a",
        )
    for feature, metric, symbol in (
        ("seedlings", "forks", "seedling"),
        ("flowers", "stars", "flower"),
        ("mushrooms", "issues", "mushroom"),
    ):
        group = _node(root, "g", id=feature)
        for index in range(_slots(normalized[metric], feature)):
            x = {"seedlings": 215, "flowers": 172, "mushrooms": 220}[feature]
            spacing = {"seedlings": 47, "flowers": 33, "mushrooms": 34}[feature]
            y = 251 - index % 3 * 6
            item = _node(
                group,
                "g",
                id=f"{feature}-{index}",
                transform=_position(subject, feature, index, x + index * spacing, y),
            )
            if feature == "flowers":
                _node(
                    item,
                    "path",
                    d="M0 4Q-6 -15 0 -28",
                    fill="none",
                    stroke="#71885a",
                    stroke_width="2",
                )
                _use(item, symbol, -10, -39, 20, 20)
            elif feature == "seedlings":
                _use(item, symbol, -18, -32, 36, 38)
            else:
                _use(item, symbol, -14, -24, 28, 30)
    fireflies = _node(root, "g", id="fireflies")
    for index in range(_slots(normalized["stars"], "fireflies")):
        item = _node(
            fireflies,
            "g",
            id=f"firefly-{index}",
            transform=_position(
                subject, "firefly", index, 232 + index * 61, 116 + index % 3 * 29
            ),
        )
        _node(item, "circle", r=6, fill="#e8ca76", opacity="0.18")
        _node(item, "circle", r=2, fill="#c9a74c")
    identity = _node(root, "g", id="identity", fill="#3c5146", font_family="serif")
    _node(
        identity, "text", x=32, y=29, font_size=25
    ).text = f"{subject['login']} / terrarium"
    _node(
        identity, "text", x=868, y=29, font_size=25, text_anchor="end"
    ).text = growth_stage.capitalize()
    _node(
        identity, "text", x=32, y=337, font_size=25
    ).text = f"Activity through {state['last_complete_activity_day']} UTC"
    _node(
        identity, "text", x=868, y=337, font_size=20, text_anchor="end"
    ).text = "PUBLIC GITHUB ACTIVITY"
    return ET.tostring(root, encoding="utf-8", short_empty_elements=True) + b"\n"
