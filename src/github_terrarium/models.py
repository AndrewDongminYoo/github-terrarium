"""Validated, deterministic public collection snapshots."""

import json
from datetime import date, timedelta

from .config import LOGIN


def fields(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError("Unexpected or missing structured fields")


def identifier(value):
    if not isinstance(value, str) or not value or len(value) > 200:
        raise ValueError("Invalid public identifier")
    if any(ord(char) < 33 or ord(char) > 126 for char in value):
        raise ValueError("Invalid public identifier")
    return value


def count(value):
    if type(value) is not int or not 0 <= value <= 10**12:
        raise ValueError("Expected bounded nonnegative integer")
    return value


def iso_day(value):
    if not isinstance(value, str):
        raise ValueError("Expected ISO date")
    result = date.fromisoformat(value)
    if result.isoformat() != value:
        raise ValueError("Expected canonical ISO date")
    return result


def day_range(start, end):
    return [(start + timedelta(days=i)).isoformat() for i in range((end - start).days)]


def canonical_json(value):
    return json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"


def validate_snapshot(snapshot):
    fields(
        snapshot,
        {
            "schema_version",
            "complete_snapshot",
            "subject",
            "activity_start",
            "activity_end",
            "observed_on",
            "repositories",
            "days",
        },
    )
    if type(snapshot["schema_version"]) is not int or snapshot["schema_version"] != 1:
        raise ValueError("Unsupported snapshot version")
    if snapshot["complete_snapshot"] is not True:
        raise ValueError("Only complete snapshots can update growth")
    subject = snapshot["subject"]
    fields(subject, {"id", "login"})
    identifier(subject["id"])
    if not isinstance(subject["login"], str) or not LOGIN.fullmatch(subject["login"]):
        raise ValueError("Invalid subject login")
    start = iso_day(snapshot["activity_start"])
    end = iso_day(snapshot["activity_end"])
    observed = iso_day(snapshot["observed_on"])
    if not 0 < (end - start).days <= 90 or end > observed:
        raise ValueError("Invalid completed activity interval")
    fields(snapshot["days"], day_range(start, end))
    for counts in snapshot["days"].values():
        fields(counts, {"prs", "reviews", "issues"})
        for value in counts.values():
            count(value)
    repos = snapshot["repositories"]
    if not isinstance(repos, dict) or len(repos) > 10000:
        raise ValueError("Invalid repository collection")
    for key, stock in repos.items():
        identifier(key)
        fields(stock, {"stars", "forks"})
        for value in stock.values():
            count(value)
    if len(canonical_json(snapshot).encode()) > 2 * 1024 * 1024:
        raise ValueError("Snapshot exceeds size budget")
    return snapshot
