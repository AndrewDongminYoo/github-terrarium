import copy
import unittest
from datetime import date, timedelta

from github_terrarium.growth import activity_xp, advance, popularity_xp, stage, traits
from github_terrarium.models import canonical_json, day_range
from github_terrarium.state import validate_state


def snapshot(end=date(2026, 11, 15), start=None, prs=0, stars=10, forks=2):
    start = start or end - timedelta(days=30)
    return {
        "schema_version": 1,
        "complete_snapshot": True,
        "subject": {"id": "U1", "login": "octocat"},
        "activity_start": start.isoformat(),
        "activity_end": end.isoformat(),
        "observed_on": end.isoformat(),
        "repositories": {"R1": {"stars": stars, "forks": forks}},
        "days": {
            day: {"prs": prs, "reviews": 0, "issues": 0}
            for day in day_range(start, end)
        },
    }


def total(state):
    return sum(
        d["activity_xp_awarded"] + d["popularity_xp_awarded"]
        for d in state["days"].values()
    )


class GrowthTests(unittest.TestCase):
    def test_formula_and_stage_boundaries(self):
        self.assertEqual(activity_xp({"prs": 2, "reviews": 3, "issues": 1}), 39)
        self.assertEqual(activity_xp({"prs": 500, "reviews": 500, "issues": 500}), 115)
        self.assertEqual(popularity_xp(3, 1), 11)
        self.assertEqual(popularity_xp(500, 500), 90)
        for xp, expected in [
            (0, "seed"),
            (99, "seed"),
            (100, "sprout"),
            (499, "sprout"),
            (500, "grove"),
            (1499, "grove"),
            (1500, "mature"),
            (3999, "mature"),
            (4000, "sanctuary"),
        ]:
            self.assertEqual(stage(xp), expected)

    def test_bootstrap_and_byte_identical_replay(self):
        value = snapshot(prs=1)
        state = advance(value)
        self.assertEqual(total(state), 360)
        self.assertEqual(state["days"]["2026-11-15"]["prs"], None)
        self.assertEqual(canonical_json(advance(value, state)), canonical_json(state))
        self.assertEqual(
            state["repository_watermarks"]["R1"], {"stars": 10, "forks": 2}
        )

    def test_same_day_caps_and_stock_drop_recovery(self):
        state = advance(snapshot())
        for stars in [13, 8, 13, 200, 400]:
            state = advance(snapshot(stars=stars), state)
        self.assertEqual(total(state), 40)
        self.assertEqual(state["days"]["2026-11-15"]["new_star_units"], 390)
        self.assertEqual(state["repository_watermarks"]["R1"]["stars"], 400)

    def test_new_removed_renamed_repository_retains_watermark(self):
        state = advance(snapshot())
        value = snapshot(stars=15)
        value["repositories"]["NEW"] = {"stars": 900, "forks": 100}
        state = advance(value, state)
        self.assertEqual(total(state), 10)
        empty = snapshot()
        empty["repositories"] = {}
        state = advance(empty, state)
        self.assertEqual(state["current_traits"]["stars"], 0)
        state = advance(value, state)
        self.assertEqual(total(state), 10)

    def test_activity_corrections_never_reduce_or_duplicate_awards(self):
        state = advance(snapshot(prs=1))
        state = advance(snapshot(prs=0), state)
        self.assertEqual(total(state), 360)
        self.assertEqual(state["current_traits"]["prs"], 0)
        state = advance(snapshot(prs=2), state)
        self.assertEqual(total(state), 720)
        state = advance(snapshot(prs=2), state)
        self.assertEqual(total(state), 720)

    def test_next_day_and_missed_days_preserve_continuity(self):
        state = advance(snapshot(prs=1))
        value = snapshot(
            end=date(2026, 12, 30), start=date(2026, 11, 15), prs=1, stars=13, forks=3
        )
        state = advance(value, state)
        self.assertEqual(total(state), 75 * 12 + 11)
        self.assertEqual(state["current_traits"]["prs"], 30)
        self.assertEqual(state["days"]["2026-11-15"]["prs"], 1)
        self.assertEqual(state["days"]["2026-12-30"]["popularity_xp_awarded"], 11)

    def test_rejects_identity_backward_partial_and_short_bootstrap(self):
        state = advance(snapshot())
        candidates = []
        for mutate in [
            lambda s: s["subject"].update(id="OTHER"),
            lambda s: s.update(complete_snapshot=False),
            lambda s: s["days"].pop("2026-10-16"),
        ]:
            value = snapshot()
            mutate(value)
            candidates.append(value)
        candidates.append(snapshot(end=date(2026, 11, 14)))
        for value in candidates:
            with self.assertRaises(ValueError):
                advance(value, state)
        with self.assertRaises(ValueError):
            advance(snapshot(start=date(2026, 11, 14)))

    def test_rename_keeps_identity_and_input_unchanged(self):
        state = advance(snapshot())
        original = copy.deepcopy(state)
        value = snapshot()
        value["subject"]["login"] = "renamed"
        result = advance(value, state)
        self.assertEqual(state, original)
        self.assertEqual(result["subject"]["id"], "U1")
        self.assertEqual(result["subject"]["login"], "renamed")

    def test_gap_requires_explicit_recovery_without_popularity_history(self):
        state = advance(snapshot())
        today = date(2027, 3, 15)
        current = snapshot(end=today, prs=1, stars=100)
        with self.assertRaisesRegex(ValueError, "recovery"):
            advance(current, state)
        batch = snapshot(
            end=date(2027, 1, 15), start=date(2026, 11, 15), prs=1, stars=100
        )
        batch["observed_on"] = today.isoformat()
        state = advance(batch, state, recover_through=today)
        self.assertEqual(state["last_popularity_observation_day"], "2026-11-15")
        self.assertEqual(state["repository_watermarks"]["R1"]["stars"], 10)
        self.assertEqual(state["recovery_target"], "2027-03-15")
        with self.assertRaises(ValueError):
            advance(current, state)
        final = snapshot(end=today, start=date(2027, 1, 15), prs=1, stars=100)
        state = advance(final, state, recover_through=today)
        self.assertIsNone(state["recovery_target"])
        self.assertEqual(total(state), 120 * 12)
        state = advance(current, state)
        self.assertEqual(total(state), 120 * 12 + 40)

    def test_validation_rejects_corrupt_state(self):
        state = advance(snapshot())
        for mutate in [
            lambda s: s.update(schema_version=2),
            lambda s: s["days"].pop("2026-10-16"),
            lambda s: s["days"]["2026-11-15"].update(prs=0),
            lambda s: s["days"]["2026-10-16"].update(activity_xp_awarded=116),
            lambda s: s["current_traits"].update(prs=100),
            lambda s: s.update(secret="no"),
        ]:
            value = copy.deepcopy(state)
            mutate(value)
            with self.assertRaises(ValueError):
                validate_state(value)

    def test_traits_bounded(self):
        result = traits(
            {"stars": 500, "forks": 100, "prs": 30, "reviews": 60, "issues": 20}
        )
        self.assertEqual(set(result.values()), {1.0})
        self.assertEqual(set(traits(dict.fromkeys(result, 0)).values()), {0.0})

    def test_recovery_replays_and_cutoff_guard(self):
        state = advance(snapshot())
        cutoff = date(2027, 3, 15)
        batch = snapshot(end=date(2027, 1, 15), start=date(2026, 11, 15), prs=1)
        batch["observed_on"] = cutoff.isoformat()
        state = advance(batch, state, recover_through=cutoff)
        self.assertEqual(
            canonical_json(advance(batch, state, recover_through=cutoff)),
            canonical_json(state),
        )
        with self.assertRaises(ValueError):
            advance(batch, state, recover_through=date(2027, 2, 1))
        final = snapshot(end=cutoff, start=date(2027, 1, 15))
        state = advance(final, state, recover_through=cutoff)
        self.assertEqual(
            canonical_json(advance(final, state, recover_through=cutoff)),
            canonical_json(state),
        )

    def test_activity_caps_apply_to_day_across_runs(self):
        state = advance(snapshot())
        value = snapshot()
        value["days"]["2026-11-14"] = {"prs": 4, "reviews": 8, "issues": 4}
        state = advance(value, state)
        value["days"]["2026-11-14"] = {"prs": 10, "reviews": 20, "issues": 10}
        state = advance(value, state)
        self.assertEqual(total(state), 115)
        self.assertEqual(total(advance(value, state)), 115)

    def test_repository_rename_cannot_copy_high_star_credit(self):
        from test_normalize import FixtureClient

        from github_terrarium.config import Config
        from github_terrarium.normalize import collect

        client = FixtureClient()
        repository_name = "popular-original"
        stars = 10000

        def transform(query, variables, user):
            if "repositories" in user:
                node = user["repositories"]["nodes"][0]
                node.update(name=repository_name, stargazerCount=stars)
            for connection in user.get("contributionsCollection", {}).values():
                connection["nodes"] = []
            return user

        client.transform = transform

        def observed():
            return collect(
                Config("octocat", "owner/terrarium"),
                date(2026, 10, 16),
                date(2026, 11, 15),
                client,
                observed_on=date(2026, 11, 15),
            )

        state = advance(observed())
        self.assertEqual(total(state), 0)
        stars = 10003
        state = advance(observed(), state)
        self.assertEqual(total(state), 6)
        for repository_name in ["renamed", "renamed-again", "popular-original"]:
            state = advance(observed(), state)
            self.assertEqual(total(state), 6)
            self.assertEqual(set(state["repository_watermarks"]), {"R1"})
            self.assertEqual(state["repository_watermarks"]["R1"]["stars"], 10003)

    def test_fixture_personas(self):
        from pathlib import Path

        from github_terrarium.state import read_json

        expected = {
            "empty": 0,
            "popularity": 0,
            "pull-requests": 1800,
            "reviews": 1200,
            "issues": 450,
        }
        for name, xp in expected.items():
            state = advance(
                read_json(Path(__file__).parent / "fixtures" / (name + ".json"))
            )
            self.assertEqual(total(state), xp, name)
            self.assertTrue(
                all(0 <= v <= 1 for v in traits(state["current_traits"]).values())
            )

    def test_old_corrections_require_explicit_recovery(self):
        state = advance(snapshot())
        state = advance(snapshot(end=date(2026, 12, 15)), state)
        old = snapshot(end=date(2026, 12, 15), start=date(2026, 10, 16))
        old["days"]["2026-10-16"]["prs"] = 5
        with self.assertRaises(ValueError):
            advance(old, state)
        state = advance(old, state, recover_through=date(2026, 12, 15))
        self.assertEqual(total(state), 60)
