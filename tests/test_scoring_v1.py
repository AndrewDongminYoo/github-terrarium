"""Release regression tests that freeze scoring version 1 (decision in #20).

Changing any value pinned here requires a new scoring version with an explicit
migration or refusal; do not update these literals to match a new formula.
"""

import unittest
from datetime import date, timedelta
from pathlib import Path

from github_terrarium.growth import (
    CAPS,
    activity_xp,
    advance,
    popularity_xp,
    stage,
    traits,
)
from github_terrarium.models import day_range
from github_terrarium.state import read_json

FIXTURES = Path(__file__).parent / "fixtures"
# Normalized traits are compared after rounding to this many decimal places.
PRECISION = 6
# (metric, weight, per-day cap) for the daily activity award.
ACTIVITY_TERMS = [("issues", 3, 5), ("prs", 12, 5), ("reviews", 4, 10)]
# (positional argument, weight, per-day cap) for the daily popularity award.
POPULARITY_TERMS = [(0, 2, 20), (1, 5, 10)]
STAGE_BOUNDARIES = [
    (0, "seed"),
    (99, "seed"),
    (100, "sprout"),
    (499, "sprout"),
    (500, "grove"),
    (1499, "grove"),
    (1500, "mature"),
    (3999, "mature"),
    (4000, "sanctuary"),
]
TRAIT_CAPS = {"forks": 100, "issues": 20, "prs": 30, "reviews": 60, "stars": 500}
# Literal values derived from scoring version 1 on 2026-11-17; never regenerate.
PERSONAS = {
    "empty": {
        "activity_xp": 0,
        "popularity_xp": 0,
        "stage": "seed",
        "traits": {
            "forks": 0.0,
            "issues": 0.0,
            "prs": 0.0,
            "reviews": 0.0,
            "stars": 0.0,
        },
    },
    "issues": {
        "activity_xp": 450,
        "popularity_xp": 0,
        "stage": "sprout",
        "traits": {
            "forks": 0.0,
            "issues": 1.0,
            "prs": 0.0,
            "reviews": 0.0,
            "stars": 0.0,
        },
    },
    "popularity": {
        "activity_xp": 0,
        "popularity_xp": 0,
        "stage": "seed",
        "traits": {
            "forks": 1.0,
            "issues": 0.0,
            "prs": 0.0,
            "reviews": 0.0,
            "stars": 1.0,
        },
    },
    "pull-requests": {
        "activity_xp": 1800,
        "popularity_xp": 0,
        "stage": "mature",
        "traits": {
            "forks": 0.0,
            "issues": 0.0,
            "prs": 1.0,
            "reviews": 0.0,
            "stars": 0.0,
        },
    },
    "reviews": {
        "activity_xp": 1200,
        "popularity_xp": 0,
        "stage": "grove",
        "traits": {
            "forks": 0.0,
            "issues": 0.0,
            "prs": 0.0,
            "reviews": 1.0,
            "stars": 0.0,
        },
    },
}
# The persona fixtures saturate every nonzero trait, so pin the curve below caps.
MID_TRAITS = {
    "inputs": {"forks": 2, "issues": 3, "prs": 4, "reviews": 5, "stars": 10},
    "expected": {
        "forks": 0.238046,
        "issues": 0.45534,
        "prs": 0.468679,
        "reviews": 0.435859,
        "stars": 0.385724,
    },
}


def quiet():
    return {"issues": 0, "prs": 0, "reviews": 0}


def rounded(values):
    return {key: round(value, PRECISION) for key, value in values.items()}


class ScoringVersionOneConstantsTests(unittest.TestCase):
    def test_activity_weights_and_per_day_caps(self):
        for metric, weight, cap in ACTIVITY_TERMS:
            with self.subTest(metric=metric):
                self.assertEqual(activity_xp({**quiet(), metric: 1}), weight)
                self.assertEqual(activity_xp({**quiet(), metric: cap}), weight * cap)
                self.assertEqual(
                    activity_xp({**quiet(), metric: cap + 1}), weight * cap
                )

    def test_popularity_weights_and_per_day_caps(self):
        for position, weight, cap in POPULARITY_TERMS:
            with self.subTest(position=position):

                def award(units, position=position):
                    arguments = [0, 0]
                    arguments[position] = units
                    return popularity_xp(*arguments)

                self.assertEqual(award(1), weight)
                self.assertEqual(award(cap), weight * cap)
                self.assertEqual(award(cap + 1), weight * cap)

    def test_daily_maxima(self):
        self.assertEqual(
            activity_xp({"issues": 10**6, "prs": 10**6, "reviews": 10**6}), 115
        )
        self.assertEqual(popularity_xp(10**6, 10**6), 90)

    def test_stage_thresholds_at_each_boundary(self):
        for xp, name in STAGE_BOUNDARIES:
            with self.subTest(xp=xp):
                self.assertEqual(stage(xp), name)

    def test_trait_caps(self):
        self.assertEqual(CAPS, TRAIT_CAPS)
        for metric, cap in TRAIT_CAPS.items():
            with self.subTest(metric=metric):
                below = {**dict.fromkeys(TRAIT_CAPS, 0), metric: cap - 1}
                at = {**dict.fromkeys(TRAIT_CAPS, 0), metric: cap}
                self.assertLess(traits(below)[metric], 1.0)
                self.assertEqual(traits(at)[metric], 1.0)

    def test_trait_curve_below_caps(self):
        self.assertEqual(rounded(traits(MID_TRAITS["inputs"])), MID_TRAITS["expected"])

    def test_bootstrap_writes_version_one(self):
        end = date(2026, 11, 15)
        start = end - timedelta(days=30)
        state = advance(
            {
                "schema_version": 1,
                "complete_snapshot": True,
                "subject": {"id": "U1", "login": "octocat"},
                "activity_start": start.isoformat(),
                "activity_end": end.isoformat(),
                "observed_on": end.isoformat(),
                "repositories": {},
                "days": {day: quiet() for day in day_range(start, end)},
            }
        )
        self.assertEqual(state["schema_version"], 1)
        self.assertEqual(state["scoring_version"], 1)


class ScoringVersionOnePersonaTests(unittest.TestCase):
    def test_persona_goldens_after_bootstrap(self):
        self.assertEqual(
            sorted(PERSONAS), sorted(path.stem for path in FIXTURES.glob("*.json"))
        )
        for name, expected in PERSONAS.items():
            with self.subTest(persona=name):
                state = advance(read_json(FIXTURES / (name + ".json")))
                days = state["days"].values()
                activity = sum(day["activity_xp_awarded"] for day in days)
                popularity = sum(day["popularity_xp_awarded"] for day in days)
                self.assertEqual(activity, expected["activity_xp"])
                self.assertEqual(popularity, expected["popularity_xp"])
                self.assertEqual(stage(activity + popularity), expected["stage"])
                self.assertEqual(
                    rounded(traits(state["current_traits"])), expected["traits"]
                )


if __name__ == "__main__":
    unittest.main()
