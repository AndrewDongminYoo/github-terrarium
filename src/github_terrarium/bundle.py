"""Canonical three-file output bundles, built offline and validated from disk."""

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from .models import canonical_json, fields, identifier, iso_day
from .render import RENDERER_VERSION, render
from .state import MAX_BYTES as STATE_MAX_BYTES
from .state import unique_object, validate_state
from .validate import MAX_BYTES as SVG_MAX_BYTES
from .validate import validate_svg

MANIFEST = "manifest.json"
STATE = "state.json"
SVG = "terrarium.svg"
OWNED = (MANIFEST, STATE, SVG)
MANIFEST_VERSION = 1
MANIFEST_MAX_BYTES = 64 * 1024
# Edit deliberately on a renderer change: dropping a version invalidates
# existing bundles that still record it.
SUPPORTED_RENDERERS = frozenset({3})
COMMIT = re.compile(r"[0-9a-f]{40}")
LIMITS = {MANIFEST: MANIFEST_MAX_BYTES, STATE: STATE_MAX_BYTES, SVG: SVG_MAX_BYTES}


def source_commit(value):
    """Return a full lowercase Git commit SHA or raise ValueError."""
    if not isinstance(value, str) or not COMMIT.fullmatch(value):
        raise ValueError("Source commit must be a full 40-character lowercase SHA")
    return value


def digest(raw):
    """The single hash function for bundle file bytes."""
    return hashlib.sha256(raw).hexdigest()


def build_files(state, commit):
    """Return validated canonical bundle bytes for one validated state."""
    validate_state(state)
    state_bytes = canonical_json(state).encode()
    svg = render(state)
    manifest = {
        "complete_activity_day": state["last_complete_activity_day"],
        "manifest_version": MANIFEST_VERSION,
        "renderer_version": RENDERER_VERSION,
        "schema_version": state["schema_version"],
        "scoring_version": state["scoring_version"],
        "sha256": {STATE: digest(state_bytes), SVG: digest(svg)},
        "source_commit": source_commit(commit),
        "stock_observation_day": state["last_popularity_observation_day"],
        "subject_id": state["subject"]["id"],
    }
    files = {MANIFEST: canonical_json(manifest).encode(), STATE: state_bytes, SVG: svg}
    validate_files(files)
    return files


def _json(raw, name):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError(f"Invalid or ambiguous JSON in {name}") from None


def _canonical(value, raw, name):
    if canonical_json(value).encode() != raw:
        raise ValueError(f"{name} is not canonical JSON")


def validate_files(files):
    """Validate bundle bytes as a whole; return the parsed manifest."""
    if not isinstance(files, dict) or set(files) != set(OWNED):
        raise ValueError("Bundle must contain exactly the three owned files")
    for name in OWNED:
        if not isinstance(files[name], bytes) or len(files[name]) > LIMITS[name]:
            raise ValueError(f"{name} exceeds its size budget")
    manifest = _json(files[MANIFEST], MANIFEST)
    fields(
        manifest,
        {
            "complete_activity_day",
            "manifest_version",
            "renderer_version",
            "schema_version",
            "scoring_version",
            "sha256",
            "source_commit",
            "stock_observation_day",
            "subject_id",
        },
    )
    _canonical(manifest, files[MANIFEST], MANIFEST)
    if type(manifest["manifest_version"]) is not int or (
        manifest["manifest_version"] != MANIFEST_VERSION
    ):
        raise ValueError("Unsupported manifest version")
    if type(manifest["renderer_version"]) is not int or (
        manifest["renderer_version"] not in SUPPORTED_RENDERERS
    ):
        raise ValueError("Unsupported renderer version")
    source_commit(manifest["source_commit"])
    identifier(manifest["subject_id"])
    iso_day(manifest["complete_activity_day"])
    iso_day(manifest["stock_observation_day"])
    hashes = manifest["sha256"]
    fields(hashes, {STATE, SVG})
    for name, value in hashes.items():
        if not isinstance(value, str) or digest(files[name]) != value:
            raise ValueError(f"Hash mismatch for {name}")

    state = validate_state(_json(files[STATE], STATE))
    _canonical(state, files[STATE], STATE)
    expected = {
        "complete_activity_day": state["last_complete_activity_day"],
        "schema_version": state["schema_version"],
        "scoring_version": state["scoring_version"],
        "stock_observation_day": state["last_popularity_observation_day"],
        "subject_id": state["subject"]["id"],
    }
    for key, value in expected.items():
        if manifest[key] != value or type(manifest[key]) is not type(value):
            raise ValueError(f"Manifest {key} does not match state")

    validate_svg(files[SVG])
    root = ET.fromstring(files[SVG])
    if root.get("data-renderer-version") != str(manifest["renderer_version"]):
        raise ValueError("Manifest renderer_version does not match SVG")
    return manifest


def read_bundle(directory):
    """Read the three owned regular files with bounded reads."""
    directory = Path(directory)
    files = {}
    for name in OWNED:
        path = directory / name
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError:
            raise ValueError(f"Bundle is missing {name}") from None
        if not stat.S_ISREG(mode):
            raise ValueError(f"{name} must be a regular file, not a link")
        with path.open("rb") as stream:
            files[name] = stream.read(LIMITS[name] + 1)
    return files


def validate_bundle(directory):
    return validate_files(read_bundle(directory))


def write_bundle(files, directory, *, previous):
    """Stage beside the destination, re-validate from disk, then replace.

    `previous` is the prior state the candidate was built from, or None for a
    bootstrap. A bootstrap refuses a destination that already holds any owned
    path, and an update replaces only a valid bundle whose state is exactly
    `previous`, so a local build can never silently reset an existing habitat
    or replace newer growth with a candidate built from stale state. Unrelated
    files in the destination are never touched. The three replacements are not
    atomic as a set; a torn bundle fails validation through its hashes.
    """
    directory = Path(directory)
    if directory.is_symlink():
        raise ValueError("Bundle directory must not be a symbolic link")
    if directory.exists() and not directory.is_dir():
        raise ValueError("Bundle path exists and is not a directory")
    existing = [n for n in OWNED if os.path.lexists(directory / n)]
    if previous is None and existing:
        raise ValueError("Bootstrap refuses a destination with existing bundle files")
    if existing:
        try:
            current = validate_bundle(directory)
        except ValueError as error:
            raise ValueError(f"Destination holds an invalid bundle: {error}") from None
        if current["subject_id"] != json.loads(files[MANIFEST])["subject_id"]:
            raise ValueError("Destination bundle belongs to a different subject")
        if (directory / STATE).read_bytes() != canonical_json(previous).encode():
            raise ValueError(
                "Supplied prior state is not the destination bundle's state"
            )
    if not directory.parent.is_dir():
        raise ValueError("Bundle directory parent does not exist")
    staging = Path(tempfile.mkdtemp(prefix=".bundle-", dir=directory.parent))
    try:
        for name in OWNED:
            (staging / name).write_bytes(files[name])
        manifest = validate_bundle(staging)
        directory.mkdir(exist_ok=True)
        for name in OWNED:
            os.replace(staging / name, directory / name)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return manifest
