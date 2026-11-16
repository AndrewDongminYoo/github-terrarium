"""Rendering contracts: bounded scenes, stable identity, and isolated traits."""

import copy
import json
import os
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

from github_terrarium.growth import advance
from github_terrarium.render import render

FIXTURES = Path(__file__).parent / "fixtures"
NS = "{http://www.w3.org/2000/svg}"


def habitat(persona="empty"):
    return advance(json.loads((FIXTURES / f"{persona}.json").read_text()))


def awarded(xp):
    state = habitat()
    first = min(state["days"])
    for offset in range(1, 11):
        key = (date.fromisoformat(first) - timedelta(days=offset)).isoformat()
        state["days"][key] = copy.deepcopy(state["days"][first])
    for key in sorted(state["days"]):
        if key <= state["last_complete_activity_day"]:
            award = min(115, xp)
            state["days"][key]["activity_xp_awarded"] = award
            xp -= award
    assert xp == 0
    return state


class RenderTests(unittest.TestCase):
    def scene(self, state):
        raw = render(state)
        self.assertIsInstance(raw, bytes)
        self.assertTrue(raw.startswith(b"<svg"), "Renderer must emit a complete SVG")
        self.assertTrue(raw.endswith(b"\n"))
        return raw, ET.fromstring(raw)

    def group(self, root, name):
        result = root.find(f".//*[@id='{name}']")
        self.assertIsNotNone(result, name)
        return result

    def test_zero_scene_is_complete_accessible_and_uses_completed_date(self):
        state = habitat()
        before = copy.deepcopy(state)
        raw, root = self.scene(state)
        self.assertEqual(root.tag, NS + "svg")
        self.assertEqual(root.get("viewBox"), "0 0 900 360")
        for name in ("title", "desc"):
            self.assertTrue(root.find(NS + name).text)
        for name in ("landscape-view", "soil", "plant", "pond", "ground", "background"):
            self.assertGreater(len(list(self.group(root, name))), 0)
        background = self.group(root, "background").find(NS + "rect")
        self.assertEqual(background.get("width"), "900")
        self.assertEqual(background.get("height"), "360")
        self.assertEqual(background.get("fill"), "#f8dc8c")
        label = "".join(self.group(root, "identity").itertext())
        self.assertIn("octocat", label)
        self.assertIn("2026-11-14", label)
        self.assertNotIn("2026-11-15", label)
        self.assertEqual(state, before)
        self.assertIsNotNone(root.find(NS + "style"))

    def test_personas_are_distinct_and_bounded_self_contained_svg(self):
        outputs = set()
        for persona in ("empty", "popularity", "pull-requests", "reviews", "issues"):
            with self.subTest(persona=persona):
                raw, root = self.scene(habitat(persona))
                outputs.add(raw)
                self.assertLessEqual(len(raw), 200 * 1024)
                self.assertLessEqual(len(list(root.iter())), 1200)
                ids = [node.get("id") for node in root.iter() if node.get("id")]
                self.assertEqual(len(ids), len(set(ids)))
                for node in root.iter():
                    self.assertNotIn(node.tag, {NS + "script", NS + "foreignObject"})
                    for key, value in node.attrib.items():
                        self.assertFalse(key.lower().startswith("on"))
                        if key.endswith("href"):
                            self.assertTrue(value.startswith("#"))
                            self.assertIn(value[1:], ids)
                        if value.startswith("url("):
                            self.assertIn(value[5:-1], ids)
        self.assertEqual(len(outputs), 5)

    def test_every_stage_boundary_changes_the_main_plant(self):
        geometries = {}
        for xp, expected in (
            (0, "seed"),
            (99, "seed"),
            (100, "sprout"),
            (499, "sprout"),
            (500, "grove"),
            (1499, "grove"),
            (1500, "mature"),
            (3999, "mature"),
            (4000, "sanctuary"),
        ):
            with self.subTest(xp=xp):
                _, root = self.scene(awarded(xp))
                self.assertEqual(root.get("data-stage"), expected)
                plant = ET.tostring(self.group(root, "plant"))
                if expected in geometries:
                    self.assertEqual(plant, geometries[expected])
                geometries[expected] = plant
        self.assertEqual(len(set(geometries.values())), 5)

    def test_trait_changes_do_not_rearrange_other_features(self):
        baseline = awarded(4000)
        _, root = self.scene(baseline)
        groups = (
            "flowers",
            "fireflies",
            "branches",
            "seedlings",
            "plant",
            "pond",
            "mushrooms",
            "ground",
            "landscape-view",
            "soil",
        )
        for metric, affected in (
            ("stars", {"flowers", "fireflies"}),
            ("forks", {"branches", "seedlings"}),
            ("prs", {"plant"}),
            ("reviews", {"pond"}),
            ("issues", {"mushrooms", "ground"}),
        ):
            changed = copy.deepcopy(baseline)
            if metric in ("stars", "forks"):
                changed["current_traits"][metric] = 1000
                changed["repository_watermarks"]["R1"][metric] = 1000
            else:
                for key, record in changed["days"].items():
                    if key <= changed["last_complete_activity_day"]:
                        record[metric] = 1
                        record["activity_xp_awarded"] = max(
                            record["activity_xp_awarded"], 12
                        )
                changed["current_traits"][metric] = 30
            _, other = self.scene(changed)
            for name in groups:
                before = ET.tostring(self.group(root, name))
                after = ET.tostring(self.group(other, name))
                if name in affected:
                    self.assertNotEqual(before, after, (metric, name))
                else:
                    self.assertEqual(before, after, (metric, name))

    def test_above_cap_saturation_does_not_add_geometry(self):
        for metric, cap in (
            ("stars", 500),
            ("forks", 100),
            ("prs", 30),
            ("reviews", 60),
            ("issues", 20),
        ):
            scenes = []
            for value in (cap, cap * 10):
                state = awarded(4000)
                if metric in ("stars", "forks"):
                    state["current_traits"][metric] = value
                    state["repository_watermarks"]["R1"][metric] = value
                else:
                    state["days"]["2026-11-14"][metric] = value
                    state["days"]["2026-11-14"]["activity_xp_awarded"] = 115
                    state["current_traits"][metric] = value
                _, root = self.scene(state)
                scenes.append(root)
            for name in (
                "flowers",
                "fireflies",
                "branches",
                "seedlings",
                "plant",
                "pond",
                "mushrooms",
                "ground",
            ):
                self.assertEqual(
                    ET.tostring(self.group(scenes[0], name)),
                    ET.tostring(self.group(scenes[1], name)),
                )

    def test_login_rename_keeps_scene_and_subject_changes_vary_it(self):
        state = habitat("reviews")
        _, original = self.scene(state)
        state["subject"]["login"] = "renamed-user"
        _, renamed = self.scene(state)
        for name in ("landscape-view", "soil", "plant", "pond", "ground"):
            self.assertEqual(
                ET.tostring(self.group(original, name)),
                ET.tostring(self.group(renamed, name)),
            )
        state["subject"]["id"] = "U2"
        _, other = self.scene(state)
        self.assertNotEqual(
            ET.tostring(self.group(original, "ground")),
            ET.tostring(self.group(other, "ground")),
        )

    def test_xml_special_subject_identifier_is_escaped(self):
        state = habitat()
        state["subject"]["id"] = "U<&>\"'"
        raw, root = self.scene(state)
        self.assertIn(state["subject"]["id"], root.find(NS + "desc").text)
        self.assertIn(b"&lt;", raw)
        state["subject"]["login"] = '<script>alert("x")</script>'
        with self.assertRaises(ValueError):
            render(state)

    def test_long_login_has_bounded_identity_extent_without_losing_text(self):
        state = habitat()
        state["subject"]["login"] = "W" * 39
        _, root = self.scene(state)
        label = self.group(root, "identity").find(NS + "text")
        self.assertIn(state["subject"]["login"], label.text)
        self.assertIsNotNone(
            label.get("textLength"), "Long valid logins must have a bounded text extent"
        )
        self.assertLessEqual(float(label.get("textLength")), 620)
        self.assertEqual(label.get("lengthAdjust"), "spacingAndGlyphs")

    def test_invalid_state_and_versions_fail_before_rendering(self):
        for key, value in (
            ("schema_version", 2),
            ("scoring_version", 2),
            ("days", {}),
            ("current_traits", {}),
        ):
            state = habitat()
            state[key] = value
            with self.assertRaises(ValueError):
                render(state)
        state = habitat()
        state["subject"]["seed_version"] = 2
        with self.assertRaises(ValueError):
            render(state)

    def test_two_fresh_processes_and_mapping_order_produce_identical_bytes(self):
        state = habitat("popularity")
        expected = render(state)
        self.assertEqual(expected, render(dict(reversed(list(state.items())))))
        command = [
            sys.executable,
            "-c",
            (
                "import json,sys; from github_terrarium.render import render; "
                "sys.stdout.buffer.write(render(json.load(sys.stdin)))"
            ),
        ]
        for hash_seed in ("1", "789"):
            output = subprocess.check_output(
                command,
                input=json.dumps(state).encode(),
                env={**os.environ, "PYTHONHASHSEED": hash_seed},
            )
            self.assertEqual(output, expected)
