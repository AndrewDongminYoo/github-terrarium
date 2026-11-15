import copy
import tempfile
import unittest
from pathlib import Path

from test_growth import snapshot

from github_terrarium.growth import advance
from github_terrarium.models import canonical_json
from github_terrarium.state import read_json, validate_state


class StateTests(unittest.TestCase):
    def test_size_guard_and_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "state.json"
            for data in [
                b"x" * (2 * 1024 * 1024 + 1),
                b'{"days":{},"days":{}}',
                b"\xff",
                b"not json",
            ]:
                file.write_bytes(data)
                with self.assertRaises(ValueError):
                    read_json(file)
            file.write_bytes(canonical_json(advance(snapshot())).encode("utf-16"))
            with self.assertRaises(ValueError):
                read_json(file)
            value = advance(snapshot())
            file.write_text(canonical_json(value))
            self.assertEqual(validate_state(read_json(file)), value)
        value = advance(snapshot())
        value["repository_watermarks"] = {
            str(i) + "x" * 190: {"stars": 0, "forks": 0} for i in range(10000)
        }
        with self.assertRaisesRegex(ValueError, "2 MiB"):
            validate_state(value)

    def test_versions_null_days_popularity_and_traits(self):
        state = advance(snapshot())
        for mutate in [
            lambda s: s.update(scoring_version=True),
            lambda s: s["subject"].update(seed_version=2),
            lambda s: s["days"]["2026-10-16"].update(reviews=None),
            lambda s: s["days"]["2026-11-15"].update(new_star_units=1),
            lambda s: s["current_traits"].update(stars=1000),
            lambda s: s.update(recovery_target="2026-11-15"),
        ]:
            value = copy.deepcopy(state)
            mutate(value)
            with self.assertRaises(ValueError):
                validate_state(value)
