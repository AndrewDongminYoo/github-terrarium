"""Version-one scoring and immutable-input growth reconciliation."""

import copy
import math
from datetime import timedelta

from .models import count, iso_day, validate_snapshot

ACTIVITY = ("prs", "reviews", "issues")
STOCK = ("stars", "forks")
CAPS = {"stars": 500, "forks": 100, "prs": 30, "reviews": 60, "issues": 20}


def activity_xp(values):
    return sum(
        weight * min(count(values[key]), cap)
        for key, weight, cap in (("prs", 12, 5), ("reviews", 4, 10), ("issues", 3, 5))
    )


def popularity_xp(stars, forks):
    return 2 * min(count(stars), 20) + 5 * min(count(forks), 10)


def stage(xp):
    count(xp)
    for threshold, name in [
        (4000, "sanctuary"),
        (1500, "mature"),
        (500, "grove"),
        (100, "sprout"),
    ]:
        if xp >= threshold:
            return name
    return "seed"


def traits(values):
    return {
        key: min(1.0, math.log1p(count(values[key])) / math.log1p(cap))
        for key, cap in CAPS.items()
    }


def empty_day():
    return {
        "prs": None,
        "reviews": None,
        "issues": None,
        "new_star_units": 0,
        "new_fork_units": 0,
        "activity_xp_awarded": 0,
        "popularity_xp_awarded": 0,
    }


def advance(snapshot, previous=None, *, recover_through=None):
    """Reconcile one validated batch; recovery never awards popularity."""
    from .state import validate_state

    validate_snapshot(snapshot)
    start = iso_day(snapshot["activity_start"])
    end = iso_day(snapshot["activity_end"])
    observed = iso_day(snapshot["observed_on"])
    recovering = recover_through is not None
    if previous is None:
        if recovering or end != observed or (end - start).days != 30:
            raise ValueError(
                "Bootstrap requires exactly 30 completed days and current stock"
            )
        state = {
            "schema_version": 1,
            "scoring_version": 1,
            "subject": {**snapshot["subject"], "seed_version": 1},
            "last_complete_activity_day": (end - timedelta(days=1)).isoformat(),
            "last_popularity_observation_day": observed.isoformat(),
            "days": {},
            "repository_watermarks": {},
            "current_traits": {},
            "recovery_target": None,
        }
    else:
        validate_state(previous)
        state = copy.deepcopy(previous)
        if state["subject"]["id"] != snapshot["subject"]["id"]:
            raise ValueError("Subject identity mismatch")
        next_day = iso_day(state["last_complete_activity_day"]) + timedelta(days=1)
        popularity_day = iso_day(state["last_popularity_observation_day"])
        if end < next_day or observed < popularity_day:
            raise ValueError("Snapshot dates move backwards")
        if recovering:
            if not next_day <= end <= recover_through <= observed:
                raise ValueError(
                    "Recovery must advance toward a completed fixed cutoff"
                )
            if state["recovery_target"] not in (None, recover_through.isoformat()):
                raise ValueError("Recovery cutoff changed")
            if start > next_day:
                raise ValueError("Recovery batch leaves unknown activity days")
            state["recovery_target"] = (
                recover_through.isoformat() if end < recover_through else None
            )
        else:
            if state["recovery_target"] is not None:
                raise ValueError("Finish explicit recovery before normal updates")
            required_start = min(end - timedelta(days=30), next_day)
            if (end - required_start).days > 90:
                raise ValueError("Gap exceeds 90 days; use explicit recovery batches")
            if end != observed or start != required_start:
                raise ValueError(
                    "Snapshot must refresh the recent window and all missed days"
                )
        if start < min(iso_day(day) for day in state["days"]):
            raise ValueError("Snapshot predates this habitat's bootstrap")
        state["subject"]["login"] = snapshot["subject"]["login"]

    for day, values in snapshot["days"].items():
        record = state["days"].setdefault(day, empty_day())
        record.update(values)
        record["activity_xp_awarded"] = max(
            record["activity_xp_awarded"], activity_xp(values)
        )
    state["last_complete_activity_day"] = (end - timedelta(days=1)).isoformat()

    if not recovering:
        record = state["days"].setdefault(observed.isoformat(), empty_day())
        for repository, values in snapshot["repositories"].items():
            old = state["repository_watermarks"].get(repository, values)
            for metric, units in [
                ("stars", "new_star_units"),
                ("forks", "new_fork_units"),
            ]:
                record[units] += max(0, values[metric] - old[metric])
            state["repository_watermarks"][repository] = {
                key: max(old[key], values[key]) for key in STOCK
            }
        record["popularity_xp_awarded"] = popularity_xp(
            record["new_star_units"], record["new_fork_units"]
        )
        state["last_popularity_observation_day"] = observed.isoformat()
        state["current_traits"].update(
            {
                key: sum(repo[key] for repo in snapshot["repositories"].values())
                for key in STOCK
            }
        )
    recent_start = (end - timedelta(days=30)).isoformat()
    state["current_traits"].update(
        {
            key: sum(
                record[key]
                for day, record in state["days"].items()
                if recent_start <= day < end.isoformat()
            )
            for key in ACTIVITY
        }
    )
    return validate_state(state)
