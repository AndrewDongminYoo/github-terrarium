"""Ambient motion contracts without changing growth or scene geometry."""

import copy
import unittest
import xml.etree.ElementTree as ET
from datetime import date, timedelta

from test_render import NS, awarded

from github_terrarium.render import render


def resting(inactive_days=7, metric="prs"):
    state = awarded(4000)
    day = (
        date.fromisoformat(state["last_complete_activity_day"])
        - timedelta(days=inactive_days)
    ).isoformat()
    state["days"][day][metric] = 1
    state["days"][day]["activity_xp_awarded"] = 115
    state["current_traits"].update(stars=500, forks=100)
    state["repository_watermarks"]["R1"].update(stars=500, forks=100)
    state["current_traits"][metric] = 1
    return state


def geometry(root):
    root = copy.deepcopy(root)
    root.attrib.pop("data-motion", None)
    root.remove(root.find(NS + "style"))
    return ET.tostring(root)


class MotionTests(unittest.TestCase):
    def test_seven_completed_days_not_runs_or_popularity_determine_calm(self):
        for metric in ("prs", "reviews", "issues"):
            for inactive_days, expected in (
                (0, "active"),
                (6, "active"),
                (7, "calm"),
                (8, "calm"),
            ):
                with self.subTest(metric=metric, inactive_days=inactive_days):
                    state = resting(inactive_days, metric)
                    before = copy.deepcopy(state)
                    raw = render(state)
                    self.assertEqual(ET.fromstring(raw).get("data-motion"), expected)
                    self.assertEqual(render(state), raw)
                    self.assertEqual(state, before)

    def test_calm_changes_only_motion_mode_not_earned_scene(self):
        active = ET.fromstring(render(resting(6)))
        calm = ET.fromstring(render(resting(7)))
        self.assertEqual(active.get("data-stage"), "sanctuary")
        self.assertEqual(calm.get("data-stage"), "sanctuary")
        self.assertIsNotNone(active.find(NS + "style"))
        self.assertEqual(geometry(active), geometry(calm))

    def test_every_motion_group_has_visible_static_children_and_fixed_outer_pose(self):
        root = ET.fromstring(render(resting(metric="reviews")))
        motions = [n for n in root.iter() if "ambient" in n.get("class", "").split()]
        self.assertTrue(motions, "Expected animated groups in a populated habitat")
        families = set()
        parents = {child: parent for parent in root.iter() for child in parent}
        for group in motions:
            families.update(set(group.get("class").split()) - {"ambient"})
            self.assertEqual(group.tag, NS + "g")
            self.assertNotIn("transform", group.attrib)
            self.assertIn("transform", parents[group].attrib)
            self.assertGreater(len(group), 0)
            self.assertNotIn("opacity", group.attrib)
            self.assertNotIn("display", group.attrib)
            self.assertNotIn("visibility", group.attrib)
            self.assertRegex(group.get("style", ""), r"^animation-delay:-\d+\.\d{2}s$")
        self.assertEqual(families, {"leaf-sway", "firefly-travel", "pond-ripple"})
        self.assertLessEqual(len(motions), 40)
        css = root.find(NS + "style").text
        self.assertIn("prefers-reduced-motion: reduce", css)
        self.assertIn("animation: none", css)
        self.assertIn("transition: none", css)
        self.assertIn('[data-motion="calm"]', css)
        for family in families:
            self.assertIn("." + family, css)
        # Removing CSS leaves all render geometry intact and nonempty.
        root.remove(root.find(NS + "style"))
        self.assertEqual(
            len([n for n in root.iter() if n.tag == NS + "use"]),
            len(
                [
                    n
                    for n in ET.fromstring(render(resting(metric="reviews"))).iter()
                    if n.tag == NS + "use"
                ]
            ),
        )

    def test_saturated_scene_bounds_all_three_motion_families(self):
        state = resting()
        state["days"]["2026-11-14"].update(
            prs=30, reviews=60, issues=20, activity_xp_awarded=115
        )
        state["current_traits"].update(prs=31, reviews=60, issues=20)
        raw = render(state)
        root = ET.fromstring(raw)
        groups = [n for n in root.iter() if "ambient" in n.get("class", "").split()]
        self.assertEqual(len(groups), 38)
        self.assertLessEqual(len(raw), 200 * 1024)
        self.assertLessEqual(len(list(root.iter())), 1200)

    def test_missing_or_unknown_activity_is_rejected_not_treated_as_rest(self):
        for mutation in ("missing", "null"):
            state = resting()
            if mutation == "missing":
                del state["days"]["2026-11-12"]
            else:
                state["days"]["2026-11-12"]["prs"] = None
            with self.assertRaises(ValueError):
                render(state)
