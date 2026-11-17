"""Online generation: read output, collect, grow, build, and publish once more.

Each attempt reads the remote output head and its validated bundle first, then
collects the interval that state requires, reconciles growth, builds and
validates the bundle, and publishes it over the head that was read. A conflict
discards that attempt's snapshot and candidate; the single retry starts over
from a fresh read and a fresh collection, even on the same UTC day. A bootstrap
retry that finds a branch created by another publisher fails with the
existing-branch error before it collects, and does not adopt or update that
habitat.
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
    # Stock read after UTC midnight belongs to the next day; never file it
    # under the day the collection started.
    if clock() != day:
        raise ValueError(
            "UTC date changed during collection; nothing was published, rerun"
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


def summary_markdown(result=None, *, code=0, message=None, token=None):
    """Return a Markdown job summary for a `generate` result or failure.

    A failure passes `code` and the one-line `message` the CLI printed. Only
    result fields and that message are written, and any `token` value is
    replaced by `***`.
    """
    if result is None:
        outcome = "failure"
        rows = [("Outcome", f"`{outcome}`"), ("Exit code", str(code))]
        line = " ".join(str(message).split())
        body = f"\n~~~text\n{line}\n~~~\n"
    else:
        outcome = result["outcome"]
        interval = result["activity_interval"]
        rows = [
            ("Outcome", f"`{outcome}`"),
            ("Subject ID", f"`{result['subject_id']}`"),
            ("Activity interval", f"{interval['start']} to {interval['end']}"),
            ("Recovered gap days", str(result["recovered_gap_days"])),
            ("Stock observation day", result["stock_observation_day"]),
            ("XP delta", str(result["xp_delta"])),
        ]
        rows += [
            (f"`{name}` bytes", str(size)) for name, size in result["bytes"].items()
        ]
        rows += [
            ("Output commit", f"`{result['commit']}`"),
            ("Attempts", str(result["attempts"])),
        ]
        body = ""
    table = "\n".join(f"| {name} | {value} |" for name, value in rows)
    text = (
        f"### Terrarium generation: {outcome}\n\n"
        f"| Field | Value |\n| --- | --- |\n{table}\n{body}\n"
    )
    if token:
        text = text.replace(token, "***")
    return text


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
