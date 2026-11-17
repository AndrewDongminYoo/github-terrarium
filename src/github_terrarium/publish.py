"""Publish or restore a validated bundle on the `output` branch with isolated Git.

Every Git call runs against a temporary bare repository with system, global,
and inherited `GIT_*` settings removed, so the source checkout's HEAD, index,
worktree, hooks, and configuration are never read or changed.
"""

import base64
import json
import os
import re
import subprocess
import tempfile

from .bundle import (
    LIMITS,
    OWNED,
    STATE,
    digest,
    read_bundle,
    source_commit,
    validate_files,
)
from .config import LOGIN, REPOSITORY

BRANCH = "output"
REF = f"refs/heads/{BRANCH}"
ABSENT = "absent"
SHA = re.compile(r"[0-9a-f]{40}")
IDENTITY = {
    "GIT_AUTHOR_NAME": "github-terrarium",
    "GIT_AUTHOR_EMAIL": "github-terrarium@users.noreply.github.com",
    "GIT_COMMITTER_NAME": "github-terrarium",
    "GIT_COMMITTER_EMAIL": "github-terrarium@users.noreply.github.com",
}
TIMEOUT = 120


class PublishConflict(ValueError):
    """The remote output head is not the expected parent."""


class ReadbackError(ValueError):
    """The push succeeded but the remote did not read back as published."""


def expected_parent(value):
    """Return a full lowercase commit SHA or `absent`, or raise ValueError."""
    if value != ABSENT and not (isinstance(value, str) and SHA.fullmatch(value)):
        raise ValueError("Expected parent must be a full lowercase SHA or 'absent'")
    return value


def repository(value):
    """Return an explicit owner/name repository identity or raise ValueError."""
    parts = value.split("/") if isinstance(value, str) else []
    if (
        len(parts) != 2
        or not LOGIN.fullmatch(parts[0])
        or not REPOSITORY.fullmatch(parts[1])
        or parts[1] in {".", ".."}
    ):
        raise ValueError("Repository must be explicit owner/name")
    return value


class _Git:
    """One temporary bare repository with a sanitized environment."""

    def __init__(self, directory, token):
        self.directory = str(directory)
        self.token = token
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(IDENTITY)
        env.update(
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_TERMINAL_PROMPT="0",
        )
        if token:
            basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
            env.update(
                GIT_CONFIG_COUNT="1",
                GIT_CONFIG_KEY_0="http.https://github.com/.extraheader",
                GIT_CONFIG_VALUE_0=f"AUTHORIZATION: basic {basic}",
            )
        self.env = env
        self("init", "--bare", "--quiet", ".", git_dir=False)

    def _redact(self, text):
        if self.token:
            text = text.replace(self.token, "***")
        return text.strip().splitlines()[-1] if text.strip() else "no output"

    def run(self, *args, data=None, git_dir=True):
        prefix = ["git", f"--git-dir={self.directory}"] if git_dir else ["git"]
        try:
            return subprocess.run(
                [*prefix, *args],
                cwd=self.directory,
                env=self.env,
                input=data,
                capture_output=True,
                timeout=TIMEOUT,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ValueError(f"git {args[0]} did not complete: {type(error).__name__}")

    def __call__(self, *args, data=None, git_dir=True):
        result = self.run(*args, data=data, git_dir=git_dir)
        if result.returncode != 0:
            message = self._redact(result.stderr.decode("utf-8", "replace"))
            raise ValueError(f"git {args[0]} failed: {message}")
        return result.stdout


def _remote_head(git, remote):
    """Return the remote output head, None when absent; a lookup error raises."""
    result = git.run("ls-remote", "--exit-code", remote, REF)
    if result.returncode == 2:
        return None
    if result.returncode != 0:
        message = git._redact(result.stderr.decode("utf-8", "replace"))
        raise ValueError(f"Output branch lookup failed: {message}")
    lines = [line.split("\t") for line in result.stdout.decode().splitlines()]
    matches = [sha for sha, *name in lines if name == [REF]]
    if len(matches) != 1 or not SHA.fullmatch(matches[0]):
        raise ValueError("Output branch lookup returned an unexpected answer")
    return matches[0]


def _fetch(git, remote, expected):
    """Fetch the remote output branch and require its head to be `expected`.

    A failed fetch is a conflict only when a fresh lookup confirms the head was
    deleted or moved; otherwise, including a failed lookup, the fetch error
    stands, so authentication and transport failures stay ordinary failures.
    """
    try:
        git("fetch", "--quiet", "--no-tags", remote, f"+{REF}:refs/heads/fetched")
    except ValueError:
        try:
            head = _remote_head(git, remote)
        except ValueError:
            head = expected
        if head is None:
            raise PublishConflict(
                f"Output head {expected} was deleted during fetch"
            ) from None
        if head != expected:
            raise PublishConflict(
                f"Output head moved from {expected} during fetch"
            ) from None
        raise
    head = git("rev-parse", "--verify", "refs/heads/fetched^{commit}").decode()
    if head.strip() != expected:
        raise PublishConflict(f"Output head moved from {expected} during fetch")
    return expected


def _tree(git, commit):
    """Return the root tree entries of `commit` as {name: (mode, type, sha)}."""
    entries = {}
    for entry in git("ls-tree", "-z", commit).split(b"\0"):
        if entry:
            meta, name = entry.split(b"\t", 1)
            mode, kind, sha = meta.decode().split(" ")
            entries[name.decode("utf-8", "surrogateescape")] = (mode, kind, sha)
    return entries


def _read_owned(git, commit, entries, label="Existing output"):
    """Read the three owned files of an output commit with bounded reads."""
    files = {}
    for name in OWNED:
        if name not in entries:
            raise ValueError(f"{label} is missing {name}")
        mode, kind, sha = entries[name]
        if mode != "100644" or kind != "blob":
            raise ValueError(f"{label} {name} is not a regular file")
        size = int(git("cat-file", "-s", sha))
        if size > LIMITS[name]:
            raise ValueError(f"{label} {name} exceeds its size budget")
        files[name] = git("cat-file", "blob", sha)
    return files


def _require_growth(prior, state):
    """Require `state` to keep every day, award, and watermark of `prior`.

    Reconciliation only adds days, raises awards and units through maxima or
    additions, and raises watermarks. A same-day re-run may still change state
    (stars rise or activity counts are corrected), so the same checks apply at
    equal and later dates: the candidate must be a superset that never lowers
    a value, and a reset or rebuilt habitat cannot replace published growth.
    """
    for day, record in prior["days"].items():
        current = state["days"].get(day)
        if current is None:
            raise ValueError(f"Candidate drops existing day {day}")
        for key in (
            "activity_xp_awarded",
            "new_fork_units",
            "new_star_units",
            "popularity_xp_awarded",
        ):
            if current[key] < record[key]:
                raise ValueError(f"Candidate lowers {key} on {day}")
    for repo, marks in prior["repository_watermarks"].items():
        current = state["repository_watermarks"].get(repo)
        if current is None or any(current[k] < marks[k] for k in marks):
            raise ValueError(f"Candidate lowers repository watermark {repo}")


def _commit(git, files, entries, parent, message):
    """Write one commit replacing only the owned paths in `entries`."""
    lines = [
        f"{mode} {kind} {sha}\t{name}"
        for name, (mode, kind, sha) in entries.items()
        if name not in OWNED
    ]
    for name in OWNED:
        sha = git("hash-object", "-w", "--no-filters", "--stdin", data=files[name])
        lines.append(f"100644 blob {sha.decode().strip()}\t{name}")
    data = b"".join(
        line.encode("utf-8", "surrogateescape") + b"\0" for line in sorted(lines)
    )
    tree = git("mktree", "-z", "--missing", data=data).decode().strip()
    parents = ["-p", parent] if parent else []
    return (
        git("commit-tree", "--no-gpg-sign", tree, *parents, "-m", message)
        .decode()
        .strip()
    )


def _push(git, remote, commit, parent):
    """Push `commit` only while the remote head is still `parent`.

    The lease binds the update to `parent` (an empty lease requires an absent
    branch), so a head moved, rewound, or deleted after the lookup is rejected.
    `commit` descends from `parent` or is a root commit over an absent branch,
    so an accepted update is always a fast-forward or a branch creation.
    """
    lease = f"--force-with-lease={REF}:{parent or ''}"
    result = git.run(
        "push", "--porcelain", "--no-verify", lease, remote, f"{commit}:{REF}"
    )
    if result.returncode == 0:
        return
    for line in result.stdout.decode("utf-8", "replace").splitlines():
        if line.startswith("!") and "\t[rejected]" in line:
            raise PublishConflict("Output head moved; the push was rejected")
    # A head moved inside the receive phase fails the ref transaction as
    # `[remote rejected]`, like a hook or protection rule; a fresh lookup
    # tells them apart, and a failed lookup leaves the push error standing.
    try:
        head = _remote_head(git, remote)
    except ValueError:
        head = parent
    if head != parent:
        raise PublishConflict("Output head moved; the push was rejected")
    message = git._redact(
        result.stderr.decode("utf-8", "replace")
        + result.stdout.decode("utf-8", "replace")
    )
    raise ValueError(f"Output push failed: {message}")


def _read_back(remote, token, commit):
    """Return the remote head and its owned files from a fresh repository."""
    with tempfile.TemporaryDirectory(prefix="terrarium-readback-") as directory:
        git = _Git(directory, token)
        head = _remote_head(git, remote)
        if head != commit:
            return head, None
        _fetch(git, remote, commit)
        return head, _read_owned(git, commit, _tree(git, commit))


def read_output(repo, *, remote=None, token=None):
    """Return the remote output head and its validated owned files.

    Returns `(None, None)` when the branch is absent. An existing head whose
    bundle is missing or invalid raises ValueError and never reads as absent;
    a head moved or deleted during the fetch raises PublishConflict.
    """
    repo = repository(repo)
    remote = remote or f"https://github.com/{repo}.git"
    with tempfile.TemporaryDirectory(prefix="terrarium-read-") as directory:
        git = _Git(directory, token)
        head = _remote_head(git, remote)
        if head is None:
            return None, None
        _fetch(git, remote, head)
        try:
            files = _read_owned(git, head, _tree(git, head))
            validate_files(files)
        except ValueError as error:
            raise ValueError(f"Existing output is invalid: {error}") from None
        return head, files


def publish(bundle_dir, repo, parent, *, bootstrap=False, remote=None, token=None):
    """Publish `bundle_dir` over the expected output `parent`; return a result.

    `parent` is a full commit SHA or `absent`; `absent` requires `bootstrap`.
    Raises PublishConflict when the remote head is not `parent`, ReadbackError
    when the push succeeded but the remote did not read back as published,
    and ValueError for every other failure.
    """
    repo = repository(repo)
    parent = expected_parent(parent)
    if (parent == ABSENT) != bool(bootstrap):
        raise ValueError("Bootstrap requires --expected-parent absent and vice versa")
    remote = remote or f"https://github.com/{repo}.git"
    files = read_bundle(bundle_dir)
    candidate = validate_files(files)
    state = json.loads(files[STATE])
    if state["recovery_target"] is not None:
        raise ValueError("Candidate state has an unfinished recovery_target")
    hashes = {name: digest(files[name]) for name in OWNED}

    with tempfile.TemporaryDirectory(prefix="terrarium-publish-") as directory:
        git = _Git(directory, token)
        head = _remote_head(git, remote)
        if bootstrap:
            if head is not None:
                raise ValueError("Bootstrap refuses an existing output branch")
            entries, base = {}, None
        else:
            if head is None:
                raise ValueError("Output branch is absent; bootstrap is required")
            if head != parent:
                raise PublishConflict(f"Output head is {head}, expected {parent}")
            base = _fetch(git, remote, parent)
            entries = _tree(git, base)
            try:
                owned = _read_owned(git, base, entries)
                existing = validate_files(owned)
            except ValueError as error:
                raise ValueError(f"Existing output is invalid: {error}") from None
            prior = json.loads(owned[STATE])
            if existing["subject_id"] != candidate["subject_id"]:
                raise ValueError("Candidate belongs to a different subject")
            for key in (
                "last_complete_activity_day",
                "last_popularity_observation_day",
            ):
                if state[key] < prior[key]:
                    raise ValueError(f"Candidate {key} precedes existing output")
            _require_growth(prior, state)
            if owned == files:
                return {
                    "commit": base,
                    "outcome": "no-change",
                    "parent": base,
                    "sha256": hashes,
                }
        message = (
            f"Publish terrarium through {candidate['complete_activity_day']}\n\n"
            f"Source-Commit: {candidate['source_commit']}\n"
        )
        commit = _commit(git, files, entries, base, message)
        _push(git, remote, commit, base)

    try:
        head, published = _read_back(remote, token, commit)
    except ValueError as error:
        raise ReadbackError(f"Pushed {commit} but readback failed: {error}") from None
    if head != commit:
        raise ReadbackError(f"Pushed {commit} but the remote head reads {head}")
    if {name: digest(raw) for name, raw in published.items()} != hashes:
        raise ReadbackError(f"Pushed {commit} but remote file hashes differ")
    return {"commit": commit, "outcome": "published", "parent": base, "sha256": hashes}


def restore(repo, source, parent, *, remote=None, token=None):
    """Restore the bundle at `source` as a new child of the output head `parent`.

    `source` must be a commit in the history of `parent` that holds a valid
    bundle for the head's subject; its bytes are written unchanged, so dates
    may move backwards here and only here. Raises PublishConflict when the
    remote head is absent or not `parent` (never retried), ReadbackError when
    the push succeeded but the remote did not read back as restored, and
    ValueError for every other refusal.
    """
    repo = repository(repo)
    source = source_commit(source)
    parent = source_commit(parent)
    remote = remote or f"https://github.com/{repo}.git"

    with tempfile.TemporaryDirectory(prefix="terrarium-restore-") as directory:
        git = _Git(directory, token)
        head = _remote_head(git, remote)
        if head is None:
            raise PublishConflict(f"Output branch is absent, expected {parent}")
        if head != parent:
            raise PublishConflict(f"Output head is {head}, expected {parent}")
        _fetch(git, remote, parent)
        if (
            git.run("cat-file", "-e", f"{source}^{{commit}}").returncode != 0
            or git.run("merge-base", "--is-ancestor", source, parent).returncode != 0
        ):
            raise ValueError(f"Restore source {source} is not in the output history")
        entries = _tree(git, parent)
        try:
            owned = _read_owned(git, parent, entries)
            existing = validate_files(owned)
        except ValueError as error:
            raise ValueError(f"Existing output is invalid: {error}") from None
        try:
            files = _read_owned(git, source, _tree(git, source), "Bundle")
            historical = validate_files(files)
        except ValueError as error:
            raise ValueError(
                f"Historical bundle at {source} is invalid: {error}"
            ) from None
        if historical["subject_id"] != existing["subject_id"]:
            raise ValueError("Historical bundle belongs to a different subject")
        if json.loads(files[STATE])["recovery_target"] is not None:
            raise ValueError("Historical state has an unfinished recovery_target")
        hashes = {name: digest(files[name]) for name in OWNED}
        if owned == files:
            return {
                "commit": parent,
                "outcome": "no-change",
                "parent": parent,
                "restored_from": source,
                "sha256": hashes,
            }
        message = (
            f"Restore terrarium bundle from {source[:12]}\n\nRestored-From: {source}\n"
        )
        commit = _commit(git, files, entries, parent, message)
        _push(git, remote, commit, parent)

    try:
        head, published = _read_back(remote, token, commit)
        if head == commit:
            validate_files(published)
    except ValueError as error:
        raise ReadbackError(f"Pushed {commit} but readback failed: {error}") from None
    if head != commit:
        raise ReadbackError(f"Pushed {commit} but the remote head reads {head}")
    if {name: digest(raw) for name, raw in published.items()} != hashes:
        raise ReadbackError(f"Pushed {commit} but remote file hashes differ")
    return {
        "commit": commit,
        "outcome": "restored",
        "parent": parent,
        "restored_from": source,
        "sha256": hashes,
    }
