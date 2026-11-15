import copy
import unittest

from github_terrarium.models import validate_snapshot


def snapshot():
    return {
        "schema_version": 1,
        "complete_snapshot": True,
        "subject": {"id": "U1", "login": "octocat"},
        "activity_start": "2026-11-13",
        "activity_end": "2026-11-15",
        "observed_on": "2026-11-15",
        "repositories": {"R1": {"stars": 3, "forks": 1}},
        "days": {
            "2026-11-13": {"prs": 0, "reviews": 0, "issues": 0},
            "2026-11-14": {"prs": 1, "reviews": 2, "issues": 3},
        },
    }


class SnapshotTests(unittest.TestCase):
    def test_valid_snapshot(self):
        value = snapshot()
        self.assertEqual(validate_snapshot(value), value)

    def test_rejects_unknown_days_and_open_day(self):
        for mutate in [
            lambda s: s["days"].pop("2026-11-13"),
            lambda s: s.update(activity_end="2026-11-16"),
            lambda s: s.update(complete_snapshot=False),
        ]:
            value = snapshot()
            mutate(value)
            with self.assertRaises(ValueError):
                validate_snapshot(value)

    def test_rejects_bad_counts_versions_and_unknown_fields(self):
        for mutate in [
            lambda s: s["days"]["2026-11-14"].update(prs=True),
            lambda s: s["repositories"]["R1"].update(stars=-1),
            lambda s: s.update(schema_version=2),
            lambda s: s.update(secret="unexpected"),
        ]:
            value = copy.deepcopy(snapshot())
            mutate(value)
            with self.assertRaises(ValueError):
                validate_snapshot(value)
