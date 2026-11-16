"""Online generation: read output, collect, grow, build, and publish once more.

Each attempt reads the remote output head and its validated bundle first, then
collects the interval that state requires, reconciles growth, builds and
validates the bundle, and publishes it over the head that was read. A conflict
discards that attempt's snapshot and candidate; the single retry starts over
from a fresh read and a fresh collection, even on the same UTC day.
"""

import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .bundle import STATE, SVG, build_files, write_bundle
from .github import GraphQLClient
from .growth import GAP_TOO_LONG, RECOVERY_UNFINISHED, advance
from .models import iso_day
from .normalize import collect
from .publish import ABSENT, PublishConflict, publish, read_output

ATTEMPTS = 2
WINDOW = 30
RECOVERY = "; run grow --recover-through batches"


def today():
    return datetime.now(UTC).date()


def collector_for(token):
    """Return the production collector; each call uses a fresh API client."""

    def run(config, start, end, *, observed_on, expected_subject):
        return collect(
            config,
            start,
            end,
            GraphQLClient(token or ""),
            observed_on=observed_on,
            expected_subject=expected_subject,
        )

    return run


def _xp(state):
    if state is None:
        return 0
    return sum(
        d["activity_xp_awarded"] + d["popularity_xp_awarded"]
        for d in state["days"].values()
    )


def _interval(previous, day):
    """Return the required activity start for `previous` collected on `day`."""
    start = day - timedelta(days=WINDOW)
    if previous is None:
        return start
    next_day = iso_day(previous["last_complete_activity_day"]) + timedelta(days=1)
    if next_day > day or iso_day(previous["last_popularity_observation_day"]) > day:
        raise ValueError("Existing output is newer than the current UTC date")
    start = min(start, next_day)
    if (day - start).days > 90:
        raise ValueError(GAP_TOO_LONG + RECOVERY)
    return start


def _attempt(config, repo, commit, *, bootstrap, remote, token, clock, collector):
    head, owned = read_output(repo, remote=remote, token=token)
    if head is None and not bootstrap:
        raise ValueError(
            "Output branch is absent; rerun with --bootstrap to create the habitat"
        )
    if head is not None and bootstrap:
        raise ValueError("Bootstrap refuses an existing output branch")
    previous = None if head is None else json.loads(owned[STATE])
    if previous is not None and previous["recovery_target"] is not None:
        raise ValueError(RECOVERY_UNFINISHED + RECOVERY)
    day = clock()
    start = _interval(previous, day)
    snapshot = collector(
        config,
        start,
        day,
        observed_on=day,
        expected_subject=None if previous is None else previous["subject"]["id"],
    )
    state = advance(snapshot, previous)
    files = build_files(state, commit)
    with tempfile.TemporaryDirectory(prefix="terrarium-generate-") as directory:
        bundle_dir = Path(directory) / "bundle"
        write_bundle(files, bundle_dir, previous=None)
        result = publish(
            bundle_dir,
            repo,
            head or ABSENT,
            bootstrap=head is None,
            remote=remote,
            token=token,
        )
    return {
        "activity_interval": {"end": day.isoformat(), "start": start.isoformat()},
        "bytes": {STATE: len(files[STATE]), SVG: len(files[SVG])},
        "commit": result["commit"],
        "outcome": result["outcome"],
        "recovered_gap_days": (day - start).days - WINDOW,
        "stock_observation_day": state["last_popularity_observation_day"],
        "subject_id": state["subject"]["id"],
        "xp_delta": _xp(state) - _xp(previous),
    }


def generate(
    config,
    repo,
    commit,
    *,
    bootstrap=False,
    remote=None,
    token=None,
    clock=None,
    collector=None,
):
    """Generate and publish one bundle, retrying exactly once after a conflict.

    Raises PublishConflict when the second attempt also conflicts, and
    ValueError for every other failure; a failure never writes over the remote
    output head. Returns a summary whose `outcome` is `published` or
    `no-change`.
    """
    clock = clock or today
    collector = collector or collector_for(token)
    for attempt in range(1, ATTEMPTS + 1):
        try:
            summary = _attempt(
                config,
                repo,
                commit,
                bootstrap=bootstrap,
                remote=remote,
                token=token,
                clock=clock,
                collector=collector,
            )
        except PublishConflict:
            if attempt == ATTEMPTS:
                raise PublishConflict(
                    "Output head moved again after recollection; nothing was published"
                ) from None
            continue
        return {**summary, "attempts": attempt}
