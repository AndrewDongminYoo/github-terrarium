"""Negative-first contracts for the offline, closed-vocabulary SVG validator."""

import copy
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

from test_motion import resting
from test_render import NS, awarded, habitat

from github_terrarium.render import MOTION_CSS, render
from github_terrarium.validate import validate_svg


def element(tag, **attrs):
    return ET.Element(NS + tag, attrs)


def minimal():
    root = element(
        "svg",
        viewBox="0 0 900 360",
        role="img",
        **{
            "aria-labelledby": "scene-title scene-desc",
            "data-art": "papercut",
            "data-stage": "seed",
            "data-motion": "active",
            "data-renderer-version": "3",
        },
    )
    ET.SubElement(root, NS + "title", id="scene-title").text = "Test habitat"
    ET.SubElement(root, NS + "desc", id="scene-desc").text = "Public activity"
    ET.SubElement(root, NS + "style").text = MOTION_CSS
    ET.SubElement(root, NS + "defs")
    background = ET.SubElement(root, NS + "g", id="background")
    ET.SubElement(background, NS + "rect", width="900", height="360", fill="#f8dc8c")
    identity = ET.SubElement(
        root, NS + "g", id="identity", fill="#3c4630", **{"font-family": "monospace"}
    )
    for text, attrs in (
        ("octocat / terrarium", {"x": "26", "y": "31", "font-size": "23"}),
        (
            "Activity through 2026-11-14 UTC",
            {"x": "26", "y": "54", "font-size": "18"},
        ),
        (
            "Seed",
            {"x": "874", "y": "31", "font-size": "21", "text-anchor": "end"},
        ),
    ):
        ET.SubElement(identity, NS + "text", attrs).text = text
    return root


def raw(root):
    return ET.tostring(root, encoding="utf-8")


def add(root, node):
    root.find(NS + "g").append(node)
    return root


class SVGValidationTests(unittest.TestCase):
    def rejects(self, root, message=None):
        with self.assertRaisesRegex(ValueError, message or ".+"):
            validate_svg(raw(root))

    def test_generated_personas_stages_and_fallbacks_pass_without_mutation(self):
        states = [
            habitat(p)
            for p in ("empty", "popularity", "pull-requests", "reviews", "issues")
        ]
        states += [awarded(xp) for xp in (0, 100, 500, 1500, 4000)]
        state = resting()
        state["days"]["2026-11-14"].update(
            prs=30, reviews=60, issues=20, activity_xp_awarded=115
        )
        state["current_traits"].update(prs=31, reviews=60, issues=20)
        states.append(state)
        states.append(resting(7))
        state = copy.deepcopy(state)
        state["subject"]["login"] = "W" * 39
        states.append(state)
        renamed = copy.deepcopy(state)
        renamed["subject"]["id"] = 'U<&>"'
        states.append(renamed)
        for state in states:
            image = render(state)
            self.assertIsNone(validate_svg(image))
            self.assertEqual(image, render(state))
        tree = ET.fromstring(image)
        tree.remove(tree.find(NS + "style"))
        self.assertIsNone(validate_svg(raw(tree)))

    def test_invalid_bytes_xml_namespace_root_and_viewbox_are_rejected(self):
        for image in (b"", b"\xff", b"<svg", raw(minimal()).decode(), b"\x00<svg/>"):
            with self.subTest(image=repr(image)[:30]), self.assertRaises(ValueError):
                validate_svg(image)
        for tag in ("svg", "{https://example.invalid}svg", NS + "g"):
            tree = minimal()
            tree.tag = tag
            self.rejects(tree)
        for box in (
            "0 0 901 360",
            "0 0 900 NaN",
            "0 0 900",
            "0 0 900 360 extra",
            "0+0+900+360",
        ):
            tree = minimal()
            tree.set("viewBox", box)
            self.rejects(tree)

    def test_dtd_entity_and_processing_instruction_paths_fail_without_io(self):
        image = raw(minimal())
        declarations = (
            b'<!DOCTYPE svg SYSTEM "https://example.invalid/external.dtd">',
            b'<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]>',
            b'<!DOCTYPE svg [<!ENTITY x "expanded">]>',
            b'<!DOCTYPE svg [<!ENTITY % x SYSTEM "https://example.invalid/a">%x;]>',
            b'<?xml-stylesheet href="https://example.invalid/style.css"?>',
        )
        with (
            patch(
                "socket.socket", side_effect=AssertionError("Network used")
            ) as socket,
            patch(
                "urllib.request.urlopen", side_effect=AssertionError("URL opened")
            ) as url,
        ):
            validate_svg(image)
            for declaration in declarations:
                with (
                    self.subTest(declaration=declaration),
                    self.assertRaises(ValueError),
                ):
                    validate_svg(declaration + image)
            socket.assert_not_called()
            url.assert_not_called()

    def test_only_utf8_xml_declarations_are_accepted(self):
        image = raw(minimal())
        validate_svg(b'<?xml version="1.0" encoding="UTF-8"?>' + image)
        for image in (
            b'<?xml version="1.0" encoding="UTF-16"?>' + image,
            b'<?xml version="1.0" encoding="ISO-8859-1"?>' + image,
            image.decode().encode("utf-16-le"),
            image.decode().encode("utf-32-be"),
        ):
            with self.subTest(prefix=image[:40]), self.assertRaises(ValueError):
                validate_svg(image)

    def test_foreign_elements_events_and_namespace_attributes_are_rejected(self):
        for tag in (
            "script",
            "foreignObject",
            "image",
            "a",
            "animate",
            "set",
            "filter",
        ):
            self.rejects(add(minimal(), element(tag)))
        self.rejects(add(minimal(), ET.Element("{http://www.w3.org/1999/xhtml}div")))
        for attr in (
            "onload",
            "ONLOAD",
            "{urn:foreign}onload",
            "{http://www.w3.org/XML/1998/namespace}base",
        ):
            tree = minimal()
            tree.set(attr, "https://example.invalid/")
            self.rejects(tree)
        tree = minimal()
        tree.find(
            NS + "desc"
        ).text = "A script and url(https://example.invalid) are plain text."
        validate_svg(raw(tree))

    def test_stylesheet_and_inline_style_cannot_add_urls_or_new_animations(self):
        for css in (
            '@import "https://example.invalid/x.css";',
            r'@\69mport "https://example.invalid/x.css";',
            "@font-face {src:url(data:font/woff;base64,AA)}",
            "path {fill:url(javascript:alert(1))}",
            ".extra {animation:leaf-sway 1s infinite}",
            MOTION_CSS + "\ntext {display:none}",
        ):
            tree = minimal()
            tree.find(NS + "style").text = css
            self.rejects(tree)
        for style in (
            "animation:leaf-sway 1s infinite",
            "animation-delay:-1s;background:url(https://example.invalid)",
            r"animation-\64elay:-1s",
            "animation-delay:NaNs",
            "animation-delay:1e999s",
        ):
            self.rejects(add(minimal(), element("g", style=style)))

    def test_duplicate_unresolved_external_and_wrong_type_references_fail(self):
        self.rejects(add(minimal(), element("g", id="identity")))
        for href in (
            "#missing",
            "https://example.invalid/x.svg#x",
            "data:image/svg+xml,x",
            "javascript:alert(1)",
            "//example.invalid/x",
            "file:///tmp/a",
            "%23background",
        ):
            self.rejects(add(minimal(), element("use", href=href)), "SVG reference")
        tree = minimal()
        node = element(
            "use", **{"{http://www.w3.org/1999/xlink}href": "https://example.invalid/x"}
        )
        self.rejects(add(tree, node))
        for attrs in ({"fill": "url(#identity)"}, {"clip-path": "url(#scene-title)"}):
            self.rejects(add(minimal(), element("g", **attrs)))
        image = raw(add(minimal(), element("use", href="#background")))
        image = image.replace(b'href="#background"', b'href="&#x6a;avascript:alert(1)"')
        with self.assertRaises(ValueError):
            validate_svg(image)

    def test_malformed_and_nonfinite_geometry_is_rejected(self):
        for d in (
            "M0",
            "L0 0",
            "M0 0L1",
            "M0 0Q1 2 3",
            "M0 0A1 1 0 2 0 2 2",
            "M0 0A-1 2 0 0 0 2 2",
            "M0 0Z1 2",
            "M0,,0",
            "M0 0LNaN 2",
            "M0 0L1e999 2",
            "M0 0X1 2",
            "M0 0,",
        ):
            self.rejects(
                add(minimal(), element("path", d=d)),
                "SVG (path|arc|number|numeric|geometry)",
            )
        for transform in (
            "translate(1,)",
            "scale()",
            "matrix(1 0)",
            "translate(NaN 0)",
            "scale(1e999)",
            "translate(0 0) junk",
            "scale(1.2.3)",
            "translate(1-2)",
            "translate(1)\u00a0scale(2)",
            "translate(1\u00a02)",
            "translate(1)scale(2)",
        ):
            self.rejects(
                add(minimal(), element("g", transform=transform)),
                "SVG (number|numeric|transform)",
            )
        for name, value in (
            ("r", "-1"),
            ("r", "inf"),
            ("cx", "1e999"),
            ("opacity", "1.1"),
            ("r", "1px"),
        ):
            attrs = {"r": "1", name: value}
            self.rejects(
                add(minimal(), element("circle", **attrs)),
                "SVG (number|extent|opacity)",
            )
        for transform in ("translate(1, 2) scale(.5)", "translate(-1 2) scale(1,2)"):
            validate_svg(raw(add(minimal(), element("g", transform=transform))))

    def test_large_malformed_transform_does_not_trigger_quadratic_search(self):
        image = raw(add(minimal(), element("g", transform="a" * 180000)))
        self.assertLess(len(image), 200 * 1024)
        command = [
            sys.executable,
            "-c",
            "import sys\nfrom github_terrarium.validate import validate_svg\n"
            "try:\n validate_svg(sys.stdin.buffer.read())\n"
            "except ValueError:\n pass\nelse:\n raise SystemExit('Not rejected')\n",
        ]
        subprocess.run(command, input=image, check=True, timeout=5)

    def test_accessible_and_visible_identity_date_and_stage_are_required(self):
        for tag in ("title", "desc"):
            tree = minimal()
            tree.find(NS + tag).text = " "
            self.rejects(tree)
        for mutate in (
            lambda group: group.set("opacity", "0"),
            lambda group: group.set("transform", "translate(10000 0)"),
            lambda group: group.set("fill", "none"),
            lambda group: group[0].set("font-size", "0"),
            lambda group: group[0].set("x", "10000"),
            lambda group: group[0].set("textLength", "0"),
            lambda group: setattr(group[1], "text", "Activity through 2026-02-30 UTC"),
            lambda group: setattr(group[2], "text", "Unknown"),
        ):
            tree = minimal()
            mutate(tree[-1])
            self.rejects(tree)
        tree = minimal()
        identity = tree[-1]
        tree.remove(identity)
        tree.find(NS + "defs").append(identity)
        self.rejects(tree)

    def test_exact_byte_element_and_actual_animation_budgets(self):
        image = raw(minimal())
        self.assertIsNone(validate_svg(image + b" " * (200 * 1024 - len(image))))
        with self.assertRaisesRegex(ValueError, "byte budget"):
            validate_svg(image + b" " * (200 * 1024 + 1 - len(image)))
        tree = minimal()
        for _ in range(1200 - len(list(tree.iter()))):
            add(tree, element("g"))
        validate_svg(raw(tree))
        self.rejects(add(tree, element("g")), "element budget")
        tree = minimal()
        for _ in range(40):
            add(tree, element("g", **{"class": "leaf-sway"}))
        validate_svg(raw(tree))
        self.rejects(
            add(tree, element("g", **{"class": "leaf-sway"})), "animation budget"
        )
        tree.remove(tree.find(NS + "style"))
        validate_svg(raw(tree))

    def test_reference_cycles_reuse_expansion_and_animated_defs_are_rejected(self):
        tree = minimal()
        defs = tree.find(NS + "defs")
        a = ET.SubElement(defs, NS + "g", id="a")
        b = ET.SubElement(defs, NS + "g", id="b")
        ET.SubElement(a, NS + "use", href="#b")
        ET.SubElement(b, NS + "use", href="#a")
        self.rejects(tree, "cycle")
        tree = minimal()
        defs = tree.find(NS + "defs")
        ET.SubElement(defs, NS + "path", id="level-0", d="M0 0L1 1")
        for index in range(1, 16):
            group = ET.SubElement(defs, NS + "g", id=f"level-{index}")
            for _ in range(2):
                ET.SubElement(group, NS + "use", href=f"#level-{index - 1}")
        self.rejects(tree, "expansion budget")
        tree = minimal()
        ET.SubElement(
            tree.find(NS + "defs"), NS + "g", {"id": "animated", "class": "leaf-sway"}
        )
        self.rejects(tree)

    def test_depth_budget_stops_nested_input_during_construction(self):
        tree = minimal()
        parent = tree.find(NS + "g")
        for _ in range(30):
            parent = ET.SubElement(parent, NS + "g")
        validate_svg(raw(tree))
        ET.SubElement(parent, NS + "g")
        self.rejects(tree, "depth")
