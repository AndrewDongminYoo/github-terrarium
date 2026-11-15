"""Strict persistent-state validation and bounded, duplicate-safe JSON loading."""

import json
from datetime import date, timedelta
from pathlib import Path

from .config import LOGIN
from .growth import ACTIVITY, STOCK, activity_xp, popularity_xp
from .models import canonical_json, count, fields, identifier, iso_day

MAX_BYTES = 2 * 1024 * 1024


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def read_json(file):
    with Path(file).open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("JSON file exceeds 2 MiB budget")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError("Invalid or ambiguous JSON file") from None


def validate_state(state):
    try:
        if len(canonical_json(state).encode()) > MAX_BYTES:
            raise ValueError("State exceeds 2 MiB budget; migration required")
    except (TypeError, RecursionError):
        raise ValueError("Invalid state structure") from None
    fields(
        state,
        {
            "schema_version",
            "scoring_version",
            "subject",
            "last_complete_activity_day",
            "last_popularity_observation_day",
            "days",
            "repository_watermarks",
            "current_traits",
            "recovery_target",
        },
    )
    for key in ("schema_version", "scoring_version"):
        if type(state[key]) is not int or state[key] != 1:
            raise ValueError("Unsupported state or scoring version")
    subject = state["subject"]
    fields(subject, {"id", "login", "seed_version"})
    identifier(subject["id"])
    if not isinstance(subject["login"], str) or not LOGIN.fullmatch(subject["login"]):
        raise ValueError("Invalid subject login")
    if type(subject["seed_version"]) is not int or subject["seed_version"] != 1:
        raise ValueError("Unsupported seed version")
    last = iso_day(state["last_complete_activity_day"])
    observed = iso_day(state["last_popularity_observation_day"])
    if last == date.max:
        raise ValueError("Completed activity date has no representable exclusive end")
    if observed > last and (observed - last).days != 1:
        raise ValueError("Popularity observation is beyond the next activity day")
    target = state["recovery_target"]
    if target is not None and iso_day(target) <= last + timedelta(days=1):
        raise ValueError("Recovery target must follow the completed interval")
    days = state["days"]
    if not isinstance(days, dict) or not days:
        raise ValueError("Missing daily history")
    completed = []
    for key, record in days.items():
        day = iso_day(key)
        fields(
            record,
            {
                *ACTIVITY,
                "new_star_units",
                "new_fork_units",
                "activity_xp_awarded",
                "popularity_xp_awarded",
            },
        )
        for field in (
            "new_star_units",
            "new_fork_units",
            "activity_xp_awarded",
            "popularity_xp_awarded",
        ):
            count(record[field])
        if record["activity_xp_awarded"] > 115 or record[
            "popularity_xp_awarded"
        ] != popularity_xp(record["new_star_units"], record["new_fork_units"]):
            raise ValueError("Invalid daily XP award")
        if day <= last:
            for metric in ACTIVITY:
                count(record[metric])
            if record["activity_xp_awarded"] < activity_xp(record):
                raise ValueError("Activity award is below observed counts")
            completed.append(day)
        elif (
            day != observed
            or any(record[key] is not None for key in ACTIVITY)
            or record["activity_xp_awarded"] != 0
        ):
            raise ValueError("Invalid popularity-only activity day")
        if day > observed and (record["new_star_units"] or record["new_fork_units"]):
            raise ValueError("Popularity units after last observation")
    if (
        not completed
        or (last - min(completed)).days + 1 != len(completed)
        or max(completed) != last
        or len(completed) < 30
    ):
        raise ValueError("Missing completed activity history")
    if observed.isoformat() not in days:
        raise ValueError("Missing popularity observation record")
    watermarks = state["repository_watermarks"]
    if not isinstance(watermarks, dict):
        raise ValueError("Invalid repository watermarks")
    for key, values in watermarks.items():
        identifier(key)
        fields(values, STOCK)
        for value in values.values():
            count(value)
    current = state["current_traits"]
    fields(current, {*ACTIVITY, *STOCK})
    for value in current.values():
        count(value)
    for metric in STOCK:
        if current[metric] > sum(repo[metric] for repo in watermarks.values()):
            raise ValueError("Stock traits exceed repository high-water marks")
    recent_start = last - timedelta(days=29)
    for key in ACTIVITY:
        expected = sum(
            days[day.isoformat()][key]
            for day in completed
            if recent_start <= day <= last
        )
        if current[key] != expected:
            raise ValueError("Recent activity traits do not match daily history")
    return state
