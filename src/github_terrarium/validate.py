"""Offline validation of the generator's bounded SVG vocabulary."""

import math
import re
import xml.etree.ElementTree as ET
from collections import defaultdict, deque

from .config import LOGIN
from .models import iso_day
from .render import MOTION_CSS, RENDERER_VERSION, STAGES

NS = "{http://www.w3.org/2000/svg}"
MAX_BYTES = 200 * 1024
MAX_ELEMENTS = 1200
MAX_ANIMATIONS = 40
MAX_DEPTH = 32
MAX_EXPANSION = 10000
MAX_MAGNITUDE = 1_000_000
NUMBER = r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
TOKEN = re.compile(NUMBER + r"|[A-Za-z]|[ \t\r\n,]+")
IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_-]*"
COLOR = re.compile(r"#[0-9a-fA-F]{6}")
REFERENCE = re.compile(r"url\(#(" + IDENTIFIER + r")\)")
FAMILIES = {"leaf-sway", "firefly-travel", "pond-ripple"}
SHAPES = {"circle", "ellipse", "path", "rect", "use"}
PAINT = {"fill", "opacity", "stroke", "stroke-width", "stroke-linecap"}
COMMON = {"id", "transform"}
ATTRIBUTES = {
    "svg": {
        "viewBox",
        "role",
        "aria-labelledby",
        "data-art",
        "data-stage",
        "data-motion",
        "data-renderer-version",
    },
    "title": {"id"},
    "desc": {"id"},
    "style": set(),
    "defs": set(),
    "g": COMMON | PAINT | {"class", "style", "clip-path", "font-family"},
    "clipPath": {"id"},
    "linearGradient": {"id", "x1", "x2", "y1", "y2"},
    "radialGradient": {"id"},
    "stop": {"offset", "stop-color", "stop-opacity"},
    "rect": COMMON | PAINT | {"x", "y", "width", "height", "rx"},
    "ellipse": COMMON | PAINT | {"cx", "cy", "rx", "ry"},
    "circle": COMMON | PAINT | {"cx", "cy", "r"},
    "path": COMMON | PAINT | {"d"},
    "use": COMMON | PAINT | {"href"},
    "text": {"x", "y", "font-size", "text-anchor", "textLength", "lengthAdjust"},
}
REQUIRED = {
    "rect": {"width", "height"},
    "ellipse": {"rx", "ry"},
    "circle": {"r"},
    "path": {"d"},
    "use": {"href"},
    "stop": {"offset", "stop-color"},
    "linearGradient": {"id"},
    "radialGradient": {"id"},
    "clipPath": {"id"},
    "text": {"x", "y", "font-size"},
}
NONNEGATIVE = {
    "width",
    "height",
    "r",
    "rx",
    "ry",
    "stroke-width",
    "font-size",
    "textLength",
}
NUMERIC = NONNEGATIVE | {"x", "y", "cx", "cy", "x1", "x2", "y1", "y2"}


class _BoundedTree(ET.TreeBuilder):
    def __init__(self):
        super().__init__()
        self.count = 0
        self.depth = 0

    def start(self, tag, attrs):
        self.count += 1
        self.depth += 1
        if self.count > MAX_ELEMENTS:
            raise ValueError("SVG element budget exceeded")
        if self.depth > MAX_DEPTH:
            raise ValueError("SVG depth budget exceeded")
        return super().start(tag, attrs)

    def end(self, tag):
        self.depth -= 1
        return super().end(tag)

    def doctype(self, name, pubid, system):
        raise ValueError("SVG DTD and entity declarations are prohibited")

    def pi(self, target, text):
        raise ValueError("SVG processing instructions are prohibited")


def _number(value):
    if not re.fullmatch(NUMBER, value):
        raise ValueError("Invalid SVG number")
    number = float(value)
    if not math.isfinite(number) or abs(number) > MAX_MAGNITUDE:
        raise ValueError("Nonfinite or excessive SVG number")
    return number


def _tokens(value):
    if re.search(r"(^|[A-Za-z,])\s*,|,\s*($|[A-Za-z,])", value):
        raise ValueError("Malformed SVG numeric separator")
    tokens = []
    end = 0
    for match in TOKEN.finditer(value):
        if match.start() != end:
            raise ValueError("Invalid SVG geometry token")
        end = match.end()
        token = match.group()
        if not token[0].isspace() and token[0] != ",":
            tokens.append(token)
    if end != len(value):
        raise ValueError("Invalid SVG geometry token")
    return tokens


def _numbers(value):
    # Unlike compact path data, viewBox and transform arguments require an
    # explicit comma or ASCII whitespace between adjacent numbers.
    value = value.strip(" \t\r\n")
    if not value:
        return []
    tokens = re.split(r"[ \t\r\n]*,[ \t\r\n]*|[ \t\r\n]+", value)
    return [_number(token) for token in tokens]


def _path(value):
    tokens = _tokens(value)
    if not tokens or tokens[0] not in {"M", "m"}:
        raise ValueError("SVG path must begin with moveto")
    arities = {
        "m": 2,
        "l": 2,
        "h": 1,
        "v": 1,
        "c": 6,
        "s": 4,
        "q": 4,
        "t": 2,
        "a": 7,
        "z": 0,
    }
    index = 0
    while index < len(tokens):
        command = tokens[index].lower()
        if command not in arities:
            raise ValueError("Unsupported SVG path command")
        index += 1
        start = index
        while index < len(tokens) and tokens[index] not in "MmLlHhVvCcSsQqTtAaZz":
            _number(tokens[index])
            index += 1
        arguments = tokens[start:index]
        arity = arities[command]
        if (arity == 0 and arguments) or (
            arity and (not arguments or len(arguments) % arity)
        ):
            raise ValueError("Malformed SVG path arguments")
        if command == "a":
            for offset in range(0, len(arguments), 7):
                if any(_number(n) < 0 for n in arguments[offset : offset + 2]):
                    raise ValueError("Negative SVG arc radius")
                if any(n not in {"0", "1"} for n in arguments[offset + 3 : offset + 5]):
                    raise ValueError("Invalid SVG arc flag")


def _transform(value):
    function = re.compile(r"([A-Za-z]+)\(([^()]*)\)")
    separator = re.compile(r"(?:[ \t\r\n]+,?[ \t\r\n]*|,[ \t\r\n]*)")
    end = 0
    count = 0
    while end < len(value):
        if count:
            gap = separator.match(value, end)
            if not gap:
                raise ValueError("Malformed SVG transform separator")
            end = gap.end()
            if end == len(value):
                if "," in gap[0]:
                    raise ValueError("Malformed SVG transform separator")
                return
        else:
            end = re.compile(r"[ \t\r\n]*").match(value, end).end()
        # Match at the current cursor rather than searching every suffix of a
        # long invalid name: an unanchored search can take quadratic time.
        match = function.match(value, end)
        if not match:
            raise ValueError("Malformed SVG transform")
        if match[1] not in {"translate", "scale"} or len(_numbers(match[2])) not in {
            1,
            2,
        }:
            raise ValueError("Unsupported SVG transform")
        end = match.end()
        count += 1
    if not count:
        raise ValueError("Malformed SVG transform")


def _attributes(node, tag, references):
    if set(node.attrib) - ATTRIBUTES[tag] or REQUIRED.get(tag, set()) - set(
        node.attrib
    ):
        raise ValueError("Unsupported or missing SVG attribute")
    for name, value in node.attrib.items():
        if name == "id":
            if not re.fullmatch(IDENTIFIER, value):
                raise ValueError("Invalid SVG ID")
        elif name in NUMERIC:
            if _number(value) < 0 and name in NONNEGATIVE:
                raise ValueError("Negative SVG extent")
        elif name in {"opacity", "stop-opacity", "offset"}:
            if not 0 <= _number(value) <= 1:
                raise ValueError("Invalid SVG opacity or gradient offset")
        elif name in {"fill", "stroke", "stop-color"}:
            if COLOR.fullmatch(value) or (value == "none" and name != "stop-color"):
                continue
            match = REFERENCE.fullmatch(value)
            if not match or name == "stop-color":
                raise ValueError("Unsupported SVG paint")
            references[node].append((match[1], {"linearGradient", "radialGradient"}))
        elif name == "href":
            if not re.fullmatch("#" + IDENTIFIER, value):
                raise ValueError("Nonlocal SVG reference")
            references[node].append((value[1:], {"g", "path"}))
        elif name == "clip-path":
            match = REFERENCE.fullmatch(value)
            if not match:
                raise ValueError("Invalid SVG clip reference")
            references[node].append((match[1], {"clipPath"}))
        elif name == "d":
            _path(value)
        elif name == "transform":
            _transform(value)
        elif name == "class":
            classes = value.split()
            if (
                not classes
                or len(set(classes)) != len(classes)
                or set(classes) - FAMILIES - {"ambient"}
                or len(set(classes) & FAMILIES) > 1
            ):
                raise ValueError("Unsupported SVG animation class")
        elif name == "style":
            match = re.fullmatch(r"animation-delay:(" + NUMBER + r")s", value)
            if not match:
                raise ValueError("Unsupported SVG inline style")
            _number(match[1])
        elif name in {"font-family", "stroke-linecap", "text-anchor", "lengthAdjust"}:
            expected = {
                "font-family": "monospace",
                "stroke-linecap": "round",
                "text-anchor": "end",
                "lengthAdjust": "spacingAndGlyphs",
            }
            if value != expected[name]:
                raise ValueError("Unsupported SVG presentation value")


def _metadata(root, ids):
    expected = {
        "role": "img",
        "aria-labelledby": "scene-title scene-desc",
        "data-art": "papercut",
        "data-renderer-version": str(RENDERER_VERSION),
    }
    if any(root.get(k) != v for k, v in expected.items()) or _numbers(
        root.get("viewBox", "")
    ) != [0, 0, 900, 360]:
        raise ValueError("Invalid SVG root metadata or viewBox")
    if root.get("data-stage") not in STAGES or root.get("data-motion") not in {
        "active",
        "calm",
    }:
        raise ValueError("Invalid SVG stage or motion metadata")
    for tag in ("title", "desc"):
        nodes = root.findall(NS + tag)
        expected_id = "scene-title" if tag == "title" else "scene-desc"
        if (
            len(nodes) != 1
            or nodes[0].get("id") != expected_id
            or not (nodes[0].text or "").strip()
        ):
            raise ValueError("Missing accessible SVG title or description")
    identity = ids.get("identity")
    if (
        identity is None
        or root[-1] is not identity
        or identity.tag != NS + "g"
        or identity.attrib
        != {"id": "identity", "fill": "#3c4630", "font-family": "monospace"}
    ):
        raise ValueError("Missing or hidden SVG identity")
    if len(identity) != 3 or any(n.tag != NS + "text" for n in identity):
        raise ValueError("Missing visible SVG identity/date/stage text")
    login = (identity[0].text or "").removesuffix(" / terrarium")
    if not LOGIN.fullmatch(login) or identity[0].text != login + " / terrarium":
        raise ValueError("Invalid visible SVG login")
    for index, (x, y, size) in enumerate(((26, 31, 23), (26, 54, 18), (874, 31, 21))):
        attrs = {"x": str(x), "y": str(y), "font-size": str(size)}
        if index == 2:
            attrs["text-anchor"] = "end"
        if index == 0 and len(login) > 20:
            attrs.update(textLength="620", lengthAdjust="spacingAndGlyphs")
        if identity[index].attrib != attrs:
            raise ValueError("Hidden or misplaced SVG metadata")
    freshness = identity[1].text or ""
    match = re.fullmatch(
        r"Activity through ([0-9]{4}-[0-9]{2}-[0-9]{2}) UTC", freshness
    )
    if not match:
        raise ValueError("Missing visible SVG activity date")
    iso_day(match[1])
    if identity[2].text != root.get("data-stage").capitalize():
        raise ValueError("Inconsistent visible SVG stage")


def _references(nodes, ids, definitions, references):
    # Edges include child containment and typed fragment use. Bottom-up evaluation
    # detects cycles and bounds repeated expansion without recursion or a browser.
    dependencies = {node: list(node) for node in nodes}
    for node, targets in references.items():
        for name, tags in targets:
            target = ids.get(name)
            if (
                target is None
                or target not in definitions
                or target.tag.removeprefix(NS) not in tags
            ):
                raise ValueError("Unresolved or wrong-type SVG reference")
            dependencies[node].append(target)
    parents = defaultdict(list)
    pending = {}
    costs = dict.fromkeys(nodes, 1)
    for node, children in dependencies.items():
        pending[node] = len(children)
        for child in children:
            parents[child].append(node)
    ready = deque(n for n in nodes if not pending[n])
    visited = 0
    while ready:
        node = ready.popleft()
        visited += 1
        for parent in parents[node]:
            costs[parent] += costs[node]
            if costs[parent] > MAX_EXPANSION:
                raise ValueError("SVG reference expansion budget exceeded")
            pending[parent] -= 1
            if not pending[parent]:
                ready.append(parent)
    if visited != len(nodes):
        raise ValueError("SVG reference cycle")


def validate_svg(raw):
    """Accept current generated SVG bytes unchanged, or raise ValueError.

    This is a closed generator-format gate, not a general SVG sanitizer.
    It never opens files, URLs or sockets and never resolves external entities.
    """
    if not isinstance(raw, bytes):
        raise ValueError("SVG input must be UTF-8 bytes")
    if len(raw) > MAX_BYTES:
        raise ValueError("SVG byte budget exceeded")
    try:
        text = raw.decode("utf-8")
        # Do not let a byte parser autodetect UTF-16/32 or honor a conflicting
        # declaration after the UTF-8 check. ASCII-only UTF-16 can decode with NULs.
        if "\x00" in text:
            raise ValueError("Invalid UTF-8 SVG XML")
        declaration = re.match(r"\A\ufeff?<\?xml\s+[^?]*\?>", text)
        if declaration:
            encoding = re.search(r"\bencoding\s*=\s*(['\"])([^'\"]+)\1", declaration[0])
            if encoding and encoding[2].lower() not in {"utf-8", "utf8"}:
                raise ValueError("SVG XML declaration must use UTF-8")
        root = ET.fromstring(raw, parser=ET.XMLParser(target=_BoundedTree()))
    except (UnicodeError, ET.ParseError):
        raise ValueError("Invalid UTF-8 SVG XML") from None
    if root.tag != NS + "svg":
        raise ValueError("Invalid SVG root or namespace")
    nodes = list(root.iter())
    parents = {child: parent for parent in nodes for child in parent}
    defs = root.findall(NS + "defs")
    if len(defs) != 1:
        raise ValueError("SVG requires one root definitions block")
    definitions = set(defs[0].iter())
    ids = {}
    references = defaultdict(list)
    styles = []
    animations = 0
    containers = {
        "svg": {"title", "desc", "style", "defs", "g", "rect"},
        "defs": {"g", "path", "clipPath", "linearGradient", "radialGradient"},
        "g": SHAPES | {"g", "text"},
        "clipPath": {"rect", "path"},
        "linearGradient": {"stop"},
        "radialGradient": {"stop"},
    }
    for node in nodes:
        tag = node.tag.removeprefix(NS)
        if node.tag != NS + tag or tag not in ATTRIBUTES:
            raise ValueError("Unsupported SVG element or namespace")
        if any(
            child.tag.removeprefix(NS) not in containers.get(tag, set())
            for child in node
        ):
            raise ValueError("Unsupported SVG child placement")
        if (
            node is not root
            and tag in {"svg", "defs", "title", "desc", "style"}
            and parents[node] is not root
        ):
            raise ValueError("Unsupported nested SVG metadata")
        if (
            (node.text or "").strip() and tag not in {"title", "desc", "style", "text"}
        ) or (node.tail or "").strip():
            raise ValueError("Unexpected SVG character content")
        _attributes(node, tag, references)
        identifier = node.get("id")
        if identifier:
            if identifier in ids:
                raise ValueError("Duplicate SVG ID")
            ids[identifier] = node
        if tag == "style":
            styles.append(node)
            if (node.text or "").strip() != MOTION_CSS:
                raise ValueError("Unsupported SVG stylesheet")
        if set(node.get("class", "").split()) & FAMILIES:
            if node in definitions:
                raise ValueError("Animated SVG definitions are unsupported")
            animations += 1
        if tag in {"linearGradient", "radialGradient"}:
            offsets = [_number(n.get("offset", "")) for n in node]
            if len(offsets) < 2 or offsets != sorted(offsets):
                raise ValueError("Invalid SVG gradient stops")
    if len(styles) > 1:
        raise ValueError("Duplicate SVG stylesheet")
    if styles and animations > MAX_ANIMATIONS:
        raise ValueError("SVG animation budget exceeded")
    _metadata(root, ids)
    _references(nodes, ids, definitions, references)
