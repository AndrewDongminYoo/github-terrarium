"""Offline bundle regression: build, validate, rebuild, and reject a tampered SVG.

For every persona fixture, `build --bootstrap` runs twice into fresh directories
and `validate` runs on each; both commands must exit 0 and the two bundles must
be byte-identical. One valid bundle is then copied, one byte of its SVG is
flipped without updating the manifest, and `validate` must exit 1 with no
stdout and a hash-mismatch error. The script exits 0 only when every positive
and negative expectation holds, prints one line per check, and writes the same
lines to a log file.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from github_terrarium.bundle import OWNED, SVG, source_commit

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
DEFAULT_LOG = ROOT / "work" / "ci-bundles.log"
TAMPER_ERROR = f"Hash mismatch for {SVG}"


def cli(*args):
    """Run the package CLI and return the completed process."""
    return subprocess.run(
        [sys.executable, "-m", "github_terrarium", *map(str, args)],
        capture_output=True,
        text=True,
        check=False,
    )


def checked_out_commit():
    """Return the SHA from GITHUB_SHA or, outside Actions, the checked-out HEAD."""
    value = os.environ.get("GITHUB_SHA")
    if not value:
        value = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    return source_commit(value)


def build(fixture, directory, commit):
    """Bootstrap-build and validate one bundle; return a failure or None."""
    built = cli(
        "build",
        "--snapshot",
        fixture,
        "--bootstrap",
        "--bundle-dir",
        directory,
        "--source-commit",
        commit,
    )
    if built.returncode != 0:
        return f"build exited {built.returncode}: {built.stderr.strip()}"
    validated = cli("validate", "--bundle-dir", directory)
    if validated.returncode != 0:
        return f"validate exited {validated.returncode}: {validated.stderr.strip()}"
    return None


def differing(first, second):
    """Return the owned file names whose bytes differ between two bundles."""
    return [
        name
        for name in OWNED
        if (Path(first) / name).read_bytes() != (Path(second) / name).read_bytes()
    ]


def tamper(path):
    """Flip one byte in the middle of a file in place."""
    raw = bytearray(Path(path).read_bytes())
    raw[len(raw) // 2] ^= 0x01
    Path(path).write_bytes(bytes(raw))


def check_fixture(fixture, work, commit):
    """Return (bundle directory or None, failure or None) for one fixture."""
    first = work / fixture.stem / "first"
    second = work / fixture.stem / "second"
    first.parent.mkdir()
    for directory in (first, second):
        failure = build(fixture, directory, commit)
        if failure:
            return None, failure
    changed = differing(first, second)
    if changed:
        return None, f"rebuild is not byte-identical: {', '.join(changed)}"
    return first, None


def check_tampered(bundle, work):
    """Require validate to reject a copy whose SVG no longer matches its hash."""
    copy = work / "tampered"
    shutil.copytree(bundle, copy)
    tamper(copy / SVG)
    result = cli("validate", "--bundle-dir", copy)
    if result.returncode != 1:
        return f"validate exited {result.returncode}, expected 1"
    if result.stdout:
        return "validate printed to stdout on rejection"
    if TAMPER_ERROR not in result.stderr:
        return f"validate rejected for another reason: {result.stderr.strip()}"
    return None


def run(fixtures, work, commit):
    """Return (status, lines) for every fixture and the negative case."""
    lines = []
    status = 0
    bundle = None
    for fixture in fixtures:
        directory, failure = check_fixture(fixture, work, commit)
        if failure:
            status = 1
            lines.append(f"FAIL {fixture.stem}: {failure}")
        else:
            bundle = bundle or directory
            lines.append(f"ok {fixture.stem}: built, validated, rebuilt identically")
    if bundle is None:
        status = 1
        lines.append("FAIL tampered: no valid bundle to tamper with")
    else:
        failure = check_tampered(bundle, work)
        if failure:
            status = 1
            lines.append(f"FAIL tampered: {failure}")
        else:
            lines.append(f"ok tampered: validate rejected a changed {SVG} with exit 1")
    return status, lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fixtures", type=Path, default=FIXTURES)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument(
        "--source-commit",
        type=source_commit,
        help="full commit SHA (default: GITHUB_SHA, then git rev-parse HEAD)",
    )
    args = parser.parse_args(argv)
    fixtures = sorted(args.fixtures.glob("*.json"))
    commit = args.source_commit or checked_out_commit()
    with tempfile.TemporaryDirectory() as work:
        if fixtures:
            status, lines = run(fixtures, Path(work), commit)
        else:
            status, lines = 1, [f"FAIL no fixtures in {args.fixtures}"]
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.log.write_text("".join(f"{line}\n" for line in lines))
    for line in lines:
        print(line)
    return status


if __name__ == "__main__":
    sys.exit(main())
