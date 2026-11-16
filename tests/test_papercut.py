"""Paper-cut composition and reusable-art integration contracts."""

import unittest
import xml.etree.ElementTree as ET

from test_render import NS, awarded, habitat

from github_terrarium.render import render


class PapercutTests(unittest.TestCase):
    def test_reference_art_is_assembled_without_vessel_or_mockup_labels(self):
        root = ET.fromstring(render(habitat()))
        self.assertEqual(root.get("data-art"), "papercut")
        self.assertIsNone(root.find(".//*[@id='vessel']"))
        for name in ("plant", "roots", "pond", "soil", "ground", "landscape-view"):
            group = root.find(f".//*[@id='{name}']")
            self.assertIsNotNone(group, name)
            self.assertGreater(len(group), 0)
        self.assertNotIn("MOCKUP", "".join(root.itertext()))
        self.assertNotIn("2026-11-15 UTC", "".join(root.itertext()))
        gradients = [
            n
            for n in root.iter()
            if n.tag in {NS + "linearGradient", NS + "radialGradient"}
        ]
        self.assertEqual({n.get("id") for n in gradients}, {"sky", "sun", "glow"})
        self.assertGreater(len(root.findall(".//" + NS + "use")), 20)
        for node in root.iter():
            self.assertNotIn(
                node.tag,
                {NS + "filter", NS + "image", NS + "foreignObject", NS + "script"},
            )

    def test_earned_growth_expands_tree_and_roots_without_moving_landscape(self):
        scenes = [
            ET.fromstring(render(awarded(xp))) for xp in (0, 100, 500, 1500, 4000)
        ]
        for name in ("plant", "roots"):
            groups = [r.find(f".//*[@id='{name}']") for r in scenes]
            self.assertTrue(all(g is not None for g in groups))
            self.assertEqual(len({ET.tostring(g) for g in groups}), 5)
        for name in ("soil", "landscape-view", "pond", "ground"):
            groups = [r.find(f".//*[@id='{name}']") for r in scenes]
            self.assertEqual(len({ET.tostring(g) for g in groups}), 1, name)
