"""Browser-free gallery contracts: fixtures, page structure, and verdict logic."""

import importlib.util
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zlib
from html.parser import HTMLParser
from pathlib import Path

from github_terrarium.validate import validate_svg

TOOL = Path(__file__).resolve().parents[1] / "tools" / "gallery.py"
spec = importlib.util.spec_from_file_location("gallery", TOOL)
gallery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gallery)


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def parse(path):
    parser = Elements()
    parser.feed(path.read_text())
    return parser.tags


def png(rows, channels=3, filters=None):
    """Encode test pixel rows with the given per-row PNG filter bytes."""
    width = len(rows[0]) // channels
    body = b""
    previous = bytes(len(rows[0]))
    for index, row in enumerate(rows):
        kind = (filters or [0] * len(rows))[index]
        encoded = bytearray(row)
        for i in range(len(row)):
            left = row[i - channels] if i >= channels else 0
            up = previous[i]
            corner = previous[i - channels] if i >= channels else 0
            estimate = left + up - corner
            distances = [abs(estimate - v) for v in (left, up, corner)]
            predicted = [
                0,
                left,
                up,
                (left + up) // 2,
                (left, up, corner)[distances.index(min(distances))],
            ][kind]
            encoded[i] = (row[i] - predicted) & 255
        body += bytes([kind]) + bytes(encoded)
        previous = row

    def chunk(kind, data):
        crc = zlib.crc32(kind + data)
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    color = 2 if channels == 3 else 6
    header = struct.pack(">IIBBBBB", width, len(rows), 8, color, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(body))
        + chunk(b"IEND", b"")
    )


def frame(width=90, height=36, changed=()):
    rows = [bytearray([200, 220, 180] * width) for _ in range(height)]
    for x, y in changed:
        rows[y][x * 3 : x * 3 + 3] = bytes([10, 20, 30])
    return png([bytes(row) for row in rows])


def metrics(**image):
    return {
        "background": "rgb(255, 255, 255)",
        "clientWidth": 360,
        "scrollWidth": 360,
        "images": [
            {
                "clipped": False,
                "height": 131.2,
                "left": 16,
                "loaded": True,
                "name": "richest",
                "right": 344,
                "width": 328,
                **image,
            }
        ],
    }


class GalleryFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.states = gallery.fixtures()
        cls.directory = tempfile.TemporaryDirectory()
        cls.out = Path(cls.directory.name)
        cls.summary = gallery.build(cls.out)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_fixture_set_covers_personas_stages_and_special_states(self):
        expected = {f"persona-{name}" for name in gallery.PERSONAS} | {
            f"stage-{name}"
            for name in ("seed", "sprout", "grove", "mature", "sanctuary")
        }
        expected |= {"richest", "renamed", "calm"}
        self.assertEqual(set(self.summary), expected)
        for name in ("seed", "sprout", "grove", "mature", "sanctuary"):
            self.assertEqual(self.summary[f"stage-{name}"]["stage"], name)
            self.assertEqual(self.summary[f"stage-{name}"]["motion"], "active")
        self.assertEqual(self.summary["calm"]["motion"], "calm")

    def test_special_states_are_grown_not_edited(self):
        richest = self.summary["richest"]
        self.assertEqual(richest["stage"], "sanctuary")
        self.assertEqual(set(richest["traits"].values()), {1.0})
        self.assertEqual(
            richest["animated_groups"],
            max(item["animated_groups"] for item in self.summary.values()),
        )
        renamed = self.states["renamed"]["subject"]
        self.assertEqual(renamed["id"], "U1")
        self.assertEqual(renamed["login"], gallery.RENAMED_LOGIN)
        self.assertGreater(len(gallery.RENAMED_LOGIN), 20)
        self.assertIn(gallery.RENAMED_LOGIN, self.summary["renamed"]["title"])
        calm = self.states["calm"]
        last = calm["last_complete_activity_day"]
        recent = sorted(day for day in calm["days"] if day <= last)[-7:]
        for day in recent:
            self.assertEqual(
                [calm["days"][day][key] for key in ("prs", "reviews", "issues")],
                [0, 0, 0],
            )

    def test_every_gallery_svg_validates_and_build_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as other:
            gallery.build(other)
            for path in sorted(self.out.rglob("*")):
                if path.is_file():
                    twin = Path(other) / path.relative_to(self.out)
                    self.assertEqual(path.read_bytes(), twin.read_bytes(), path.name)
        for name in self.summary:
            validate_svg((self.out / "svg" / f"{name}.svg").read_bytes())

    def test_identity_region_covers_the_stretched_long_label(self):
        root = ET.fromstring((self.out / "svg" / "renamed.svg").read_bytes())
        label = next(
            node
            for node in root.iter("{http://www.w3.org/2000/svg}text")
            if node.text and node.text.startswith(gallery.RENAMED_LOGIN)
        )
        left, _, right, _ = gallery.TEXT_REGIONS["identity"]
        start = float(label.get("x"))
        self.assertLessEqual(left, start)
        self.assertGreaterEqual(right, start + float(label.get("textLength")))

    def test_gallery_embeds_every_fixture_through_img_only(self):
        tags = parse(self.out / "index.html")
        images = [attrs for tag, attrs in tags if tag == "img"]
        self.assertEqual(
            [image["data-fixture"] for image in images], list(self.summary)
        )
        for image in images:
            self.assertEqual(image["src"], f"svg/{image['data-fixture']}.svg")
            self.assertEqual((image["width"], image["height"]), ("900", "360"))
            self.assertTrue(image["alt"])
        names = {tag for tag, _ in tags}
        self.assertFalse(names & {"svg", "object", "embed", "iframe", "script"})
        self.assertIn(
            (
                "meta",
                {"name": "viewport", "content": "width=device-width, initial-scale=1"},
            ),
            tags,
        )

    def test_controls_break_exactly_one_property(self):
        static = (self.out / "svg" / "control-static.svg").read_bytes()
        ignored = (self.out / "svg" / "control-reduced-ignored.svg").read_bytes()
        validate_svg(static)
        self.assertNotIn(b"<style>", static)
        self.assertIn(b"<style>", ignored)
        self.assertNotIn(b"prefers-reduced-motion", ignored)
        richest = (self.out / "svg" / "richest.svg").read_bytes()
        for raw in (static, ignored):
            self.assertEqual(
                len(list(ET.fromstring(raw).iter())),
                len(list(ET.fromstring(richest).iter())) - (raw == static),
            )
        for name in gallery.LAYOUT_CONTROLS:
            sources = [
                a["src"] for t, a in parse(self.out / f"{name}.html") if t == "img"
            ]
            self.assertEqual(sources, ["svg/richest.svg"])
        with self.assertRaises(ValueError):
            gallery.controls(static)


class GalleryVerdictTests(unittest.TestCase):
    def test_png_decoder_reverses_every_filter(self):
        rows = [
            bytes((x * 7 + y * 13 + c) % 256 for x in range(5) for c in range(4))
            for y in range(5)
        ]
        for channels in (3, 4):
            sample = [row[: 5 * channels] for row in rows]
            raw = png(sample, channels, filters=[0, 1, 2, 3, 4])
            self.assertEqual(gallery.png_pixels(raw), (5, 5, channels, sample))
        with self.assertRaises(ValueError):
            gallery.png_pixels(b"not a png")

    def test_compare_counts_changes_and_text_regions(self):
        same = gallery.compare(frame(), frame())
        self.assertEqual(
            same, {"changed": 0, "regions": dict.fromkeys(gallery.TEXT_REGIONS, 0)}
        )
        ambient = gallery.compare(frame(), frame(changed=[(40, 20), (41, 20)]))
        self.assertEqual(ambient["changed"], 2)
        self.assertEqual(sum(ambient["regions"].values()), 0)
        # viewBox (850, 20) is inside the stage label at 1/10 scale.
        label = gallery.compare(frame(), frame(changed=[(85, 2)]))
        self.assertEqual(label["regions"]["stage"], 1)
        with self.assertRaises(ValueError):
            gallery.compare(frame(), frame(width=80))

    def test_motion_verdict_fails_on_static_normal_moving_reduced_or_text(self):
        still = {"changed": 0, "regions": {"identity": 0}}
        moving = {"changed": 9, "regions": {"identity": 0}}
        text = {"changed": 9, "regions": {"identity": 3}}
        self.assertEqual(gallery.motion_verdict("normal", moving), [])
        self.assertEqual(gallery.motion_verdict("reduced", still), [])
        self.assertTrue(gallery.motion_verdict("normal", still))
        self.assertTrue(gallery.motion_verdict("reduced", moving))
        self.assertEqual(
            gallery.motion_verdict("normal", text), ["text regions changed: identity"]
        )

    def test_layout_verdict_fails_on_overflow_clipping_and_partial_images(self):
        self.assertEqual(gallery.layout_verdict(metrics()), [])
        cases = [
            {"scrollWidth": 1216},
            {"right": 1216},
            {"clipped": True},
            {"height": 40},
            {"loaded": False},
        ]
        for change in cases:
            with self.subTest(change=change):
                value = metrics()
                if "scrollWidth" in change:
                    value.update(change)
                else:
                    value["images"][0].update(change)
                self.assertTrue(gallery.layout_verdict(value))

    def test_classify_marks_only_declared_gaps_pending(self):
        moving = {"richest": {"changed": 9, "regions": {"identity": 0}}}
        controls = {"control-overflow": ["overflow"], "control-reduced-ignored": ["x"]}
        result = gallery.classify(
            "webkit", "reduced", "light", True, metrics(), moving, controls
        )
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["failures"], [])
        self.assertTrue(result["pending"])
        failed = gallery.classify(
            "chromium", "reduced", "light", True, metrics(), moving, controls
        )
        self.assertEqual(failed["status"], "failed")
        undelivered = gallery.classify(
            "webkit", "reduced", "light", False, metrics(), moving, controls
        )
        self.assertEqual(undelivered["status"], "failed")
        silent = gallery.classify(
            "chromium",
            "normal",
            "light",
            False,
            metrics(),
            moving,
            {"control-static": []},
        )
        self.assertEqual(
            silent["failures"], ["control-static passed; its assertion cannot fail"]
        )
        passed = gallery.classify(
            "chromium",
            "normal",
            "light",
            False,
            metrics(),
            moving,
            {"control-static": ["x"]},
        )
        self.assertEqual(passed["status"], "passed")
        wrong_host = gallery.classify(
            "chromium",
            "normal",
            "dark",
            False,
            metrics(),
            moving,
            {"control-static": ["x"]},
        )
        self.assertEqual(wrong_host["status"], "failed")
        self.assertIn("host page background", wrong_host["failures"][0])


if __name__ == "__main__":
    unittest.main()
