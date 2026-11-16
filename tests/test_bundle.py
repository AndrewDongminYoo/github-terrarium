import contextlib
import copy
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from test_growth import snapshot

from github_terrarium import bundle
from github_terrarium.__main__ import main
from github_terrarium.bundle import (
    MANIFEST,
    OWNED,
    STATE,
    SVG,
    build_files,
    digest,
    validate_bundle,
    validate_files,
    write_bundle,
)
from github_terrarium.growth import advance
from github_terrarium.models import canonical_json
from github_terrarium.render import RENDERER_VERSION, render

COMMIT = "0123456789abcdef0123456789abcdef01234567"
PRIOR = advance(snapshot(prs=1))


def built():
    return build_files(advance(snapshot(prs=1)), COMMIT)


def with_manifest(files, **changes):
    manifest = json.loads(files[MANIFEST])
    manifest.update(changes)
    return {**files, MANIFEST: canonical_json(manifest).encode()}


def with_file(files, name, raw):
    """Replace one file and keep its manifest hash valid."""
    manifest = json.loads(files[MANIFEST])
    manifest["sha256"][name] = digest(raw)
    return {**files, name: raw, MANIFEST: canonical_json(manifest).encode()}


def run(*args):
    output, error = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
        code = main(list(args))
    return code, output.getvalue(), error.getvalue()


def snapshot_file(directory, name="snapshot.json", **options):
    path = Path(directory) / name
    path.write_text(json.dumps(snapshot(**options)))
    return str(path)


def contents(directory):
    return {p.name: p.read_bytes() for p in sorted(Path(directory).iterdir())}


class BuildTests(unittest.TestCase):
    def test_manifest_records_identity_dates_versions_and_hashes(self):
        files = built()
        state = json.loads(files[STATE])
        manifest = json.loads(files[MANIFEST])
        self.assertEqual(
            manifest,
            {
                "complete_activity_day": "2026-11-14",
                "manifest_version": 1,
                "renderer_version": 3,
                "schema_version": 1,
                "scoring_version": 1,
                "sha256": {STATE: digest(files[STATE]), SVG: digest(files[SVG])},
                "source_commit": COMMIT,
                "stock_observation_day": "2026-11-15",
                "subject_id": "U1",
            },
        )
        self.assertEqual(files[STATE], canonical_json(state).encode())
        self.assertEqual(files[SVG], render(state))
        self.assertEqual(
            files[MANIFEST], canonical_json(json.loads(files[MANIFEST])).encode()
        )

    def test_build_is_deterministic(self):
        self.assertEqual(built(), built())

    def test_current_renderer_is_supported(self):
        self.assertIn(RENDERER_VERSION, bundle.SUPPORTED_RENDERERS)

    def test_rejects_short_or_uppercase_commit(self):
        for commit in ("abc123", COMMIT.upper(), COMMIT + "0", None):
            with self.subTest(commit=commit), self.assertRaises(ValueError):
                build_files(advance(snapshot()), commit)


class ValidateTests(unittest.TestCase):
    def assertRejects(self, files, message):
        with self.assertRaisesRegex(ValueError, message):
            validate_files(files)

    def test_valid_bundle_passes(self):
        self.assertEqual(validate_files(built())["subject_id"], "U1")

    def test_tampered_file_fails_its_hash(self):
        files = built()
        for name in (STATE, SVG):
            with self.subTest(name=name):
                tampered = {**files, name: files[name].replace(b"U1", b"U2", 1)}
                self.assertRejects(tampered, f"Hash mismatch for {name}")

    def test_missing_or_extra_file(self):
        files = built()
        for name in OWNED:
            with self.subTest(missing=name):
                partial = {k: v for k, v in files.items() if k != name}
                self.assertRejects(partial, "exactly the three owned files")
        self.assertRejects({**files, "extra.txt": b""}, "exactly the three owned")

    def test_manifest_fields_must_match_state(self):
        files = built()
        for key, value in [
            ("subject_id", "U2"),
            ("complete_activity_day", "2026-11-13"),
            ("stock_observation_day", "2026-11-14"),
        ]:
            with self.subTest(key=key):
                changed = with_manifest(files, **{key: value})
                self.assertRejects(changed, f"Manifest {key} does not match state")

    def test_unsupported_versions(self):
        files = built()
        self.assertRejects(
            with_manifest(files, manifest_version=2), "Unsupported manifest version"
        )
        for value in (4, True, 3.0, "3"):
            with self.subTest(renderer=value):
                self.assertRejects(
                    with_manifest(files, renderer_version=value),
                    "Unsupported renderer version",
                )
        self.assertRejects(
            with_manifest(files, scoring_version=2), "scoring_version does not match"
        )

    def test_renderer_version_must_match_svg(self):
        files = with_manifest(built(), renderer_version=4)
        with patch.object(bundle, "SUPPORTED_RENDERERS", {3, 4}):
            self.assertRejects(files, "renderer_version does not match SVG")

    def test_non_canonical_state_is_rejected(self):
        files = built()
        compact = json.dumps(json.loads(files[STATE])).encode()
        self.assertRejects(with_file(files, STATE, compact), "not canonical JSON")

    def test_invalid_state_is_rejected(self):
        files = built()
        self.assertRejects(with_file(files, STATE, b"null\n"), "structured fields")

    def test_unsafe_svg_is_rejected_after_hash_check(self):
        files = built()
        unsafe = files[SVG].replace(b"</svg>", b"<script>alert(1)</script></svg>")
        with self.assertRaises(ValueError) as caught:
            validate_files(with_file(files, SVG, unsafe))
        self.assertNotIn("Hash mismatch", str(caught.exception))

    def test_malformed_manifest_shapes(self):
        files = built()
        for raw in (b"[]\n", b"{}\n", b"not json"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                validate_files({**files, MANIFEST: raw})
        self.assertRejects(
            with_manifest(files, sha256="abc"), "Unexpected or missing structured"
        )
        self.assertRejects(with_manifest(files, source_commit="abc"), "40-character")
        compact = json.dumps(json.loads(files[MANIFEST])).encode()
        self.assertRejects({**files, MANIFEST: compact}, "manifest.json is not canon")

    def test_symlinked_file_is_rejected(self):
        files = built()
        with tempfile.TemporaryDirectory() as directory:
            for name, raw in files.items():
                (Path(directory) / name).write_bytes(raw)
            self.assertEqual(validate_bundle(directory)["subject_id"], "U1")
            target = Path(directory) / "real.svg"
            os.replace(Path(directory) / SVG, target)
            os.symlink(target, Path(directory) / SVG)
            with self.assertRaisesRegex(ValueError, "regular file"):
                validate_bundle(directory)

    def test_oversized_file_is_rejected_on_bounded_read(self):
        with tempfile.TemporaryDirectory() as directory:
            for name, raw in built().items():
                (Path(directory) / name).write_bytes(raw)
            (Path(directory) / SVG).write_bytes(b" " * (bundle.SVG_MAX_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "terrarium.svg exceeds"):
                validate_bundle(directory)


class WriteTests(unittest.TestCase):
    def test_bootstrap_refuses_existing_bundle_and_keeps_bytes(self):
        with tempfile.TemporaryDirectory() as parent:
            destination = Path(parent) / "out"
            write_bundle(built(), destination, previous=None)
            before = contents(destination)
            for name in OWNED:
                with self.subTest(name=name):
                    with tempfile.TemporaryDirectory() as other:
                        single = Path(other) / "out"
                        single.mkdir()
                        (single / name).write_bytes(b"old")
                        with self.assertRaisesRegex(ValueError, "Bootstrap refuses"):
                            write_bundle(built(), single, previous=None)
                        self.assertEqual(contents(single), {name: b"old"})
            self.assertEqual(contents(destination), before)

    def test_failed_validation_leaves_destination_and_parent_unchanged(self):
        with tempfile.TemporaryDirectory() as parent:
            destination = Path(parent) / "out"
            write_bundle(built(), destination, previous=None)
            (destination / "README.md").write_text("unrelated\n")
            before = contents(destination)
            broken = {**built(), SVG: b"<svg/>"}
            with self.assertRaises(ValueError):
                write_bundle(broken, destination, previous=PRIOR)
            self.assertEqual(contents(destination), before)
            self.assertEqual(sorted(p.name for p in Path(parent).iterdir()), ["out"])

    def test_failed_bootstrap_creates_no_directory(self):
        with tempfile.TemporaryDirectory() as parent:
            with self.assertRaises(ValueError):
                write_bundle(
                    {**built(), SVG: b"<svg/>"}, Path(parent) / "out", previous=None
                )
            self.assertEqual(list(Path(parent).iterdir()), [])

    def test_update_preserves_unrelated_files(self):
        with tempfile.TemporaryDirectory() as parent:
            destination = Path(parent) / "out"
            write_bundle(built(), destination, previous=None)
            (destination / "README.md").write_text("unrelated\n")
            later = build_files(
                advance(snapshot(end=date(2026, 11, 16), prs=2), PRIOR), COMMIT
            )
            write_bundle(later, destination, previous=PRIOR)
            self.assertEqual((destination / "README.md").read_text(), "unrelated\n")
            self.assertEqual(
                validate_bundle(destination)["complete_activity_day"], "2026-11-15"
            )

    def test_update_refuses_a_different_subject(self):
        other = snapshot(prs=1)
        other["subject"] = {"id": "U2", "login": "hubot"}
        with tempfile.TemporaryDirectory() as parent:
            destination = Path(parent) / "out"
            write_bundle(built(), destination, previous=None)
            before = contents(destination)
            with self.assertRaisesRegex(ValueError, "different subject"):
                write_bundle(
                    build_files(advance(other), COMMIT), destination, previous=PRIOR
                )
            self.assertEqual(contents(destination), before)

    def test_update_refuses_a_stale_prior_state(self):
        newer = advance(snapshot(prs=2), PRIOR)
        with tempfile.TemporaryDirectory() as parent:
            destination = Path(parent) / "out"
            write_bundle(built(), destination, previous=None)
            write_bundle(build_files(newer, COMMIT), destination, previous=PRIOR)
            before = contents(destination)
            with self.assertRaisesRegex(ValueError, "not the destination bundle"):
                write_bundle(built(), destination, previous=PRIOR)
            self.assertEqual(contents(destination), before)

    def test_same_day_rerun_from_the_destination_state_succeeds(self):
        with tempfile.TemporaryDirectory() as parent:
            destination = Path(parent) / "out"
            write_bundle(built(), destination, previous=None)
            before = contents(destination)
            rerun = build_files(advance(snapshot(prs=1), PRIOR), COMMIT)
            write_bundle(rerun, destination, previous=PRIOR)
            self.assertEqual(contents(destination), before)

    def test_update_refuses_a_partial_destination(self):
        with tempfile.TemporaryDirectory() as parent:
            destination = Path(parent) / "out"
            destination.mkdir()
            (destination / STATE).write_bytes(built()[STATE])
            before = contents(destination)
            with self.assertRaisesRegex(ValueError, "invalid bundle.*missing"):
                write_bundle(built(), destination, previous=PRIOR)
            self.assertEqual(contents(destination), before)

    def test_symlinked_destination_is_rejected(self):
        with tempfile.TemporaryDirectory() as parent:
            real = Path(parent) / "real"
            real.mkdir()
            os.symlink(real, Path(parent) / "link")
            with self.assertRaisesRegex(ValueError, "symbolic link"):
                write_bundle(built(), Path(parent) / "link", previous=None)
            self.assertEqual(list(real.iterdir()), [])


class CLITests(unittest.TestCase):
    def test_bootstrap_update_and_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            first = snapshot_file(directory, prs=1)
            out = Path(directory) / "out"
            code, stdout, _ = run(
                "build",
                "--snapshot",
                first,
                "--bootstrap",
                "--bundle-dir",
                str(out),
                "--source-commit",
                COMMIT,
            )
            self.assertEqual(code, 0)
            self.assertEqual(stdout.encode(), (out / MANIFEST).read_bytes())
            state = Path(directory) / "prior-state.json"
            state.write_bytes((out / STATE).read_bytes())
            replay = Path(directory) / "replay"
            code, _, _ = run(
                "build",
                "--snapshot",
                first,
                "--state",
                str(state),
                "--bundle-dir",
                str(replay),
                "--source-commit",
                COMMIT,
            )
            self.assertEqual(code, 0)
            self.assertEqual(contents(replay), contents(out))
            later = snapshot_file(
                directory, "later.json", end=date(2026, 11, 16), prs=2
            )
            code, _, _ = run(
                "build",
                "--snapshot",
                later,
                "--state",
                str(out / STATE),
                "--bundle-dir",
                str(out),
                "--source-commit",
                COMMIT,
            )
            self.assertEqual(code, 0)
            self.assertNotEqual(contents(out), contents(replay))
            self.assertEqual(run("validate", "--bundle-dir", str(out))[0], 0)

    def test_invalid_supplied_state_never_bootstraps(self):
        with tempfile.TemporaryDirectory() as directory:
            source = snapshot_file(directory, prs=1)
            prior = Path(directory) / "state.json"
            out = Path(directory) / "out"
            for value in (None, False, 0, "", [], {}):
                with self.subTest(state=value):
                    prior.write_text(json.dumps(value))
                    original = prior.read_bytes()
                    code, stdout, stderr = run(
                        "build",
                        "--snapshot",
                        source,
                        "--state",
                        str(prior),
                        "--bundle-dir",
                        str(out),
                        "--source-commit",
                        COMMIT,
                    )
                    self.assertEqual((code, stdout), (1, ""))
                    self.assertIn("error:", stderr)
                    self.assertEqual(prior.read_bytes(), original)
                    self.assertFalse(out.exists())

    def test_validate_failure_prints_no_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            code, stdout, stderr = run("validate", "--bundle-dir", directory)
            self.assertEqual((code, stdout), (1, ""))
            self.assertIn("missing manifest.json", stderr)
            self.assertNotIn("Traceback", stderr)

    def test_bad_source_commit_is_a_usage_error(self):
        with tempfile.TemporaryDirectory() as directory:
            source = snapshot_file(directory)
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    main(
                        [
                            "build",
                            "--snapshot",
                            source,
                            "--bootstrap",
                            "--bundle-dir",
                            str(Path(directory) / "out"),
                            "--source-commit",
                            "HEAD",
                        ]
                    )
            self.assertEqual(caught.exception.code, 2)
            self.assertFalse((Path(directory) / "out").exists())

    def test_build_and_validate_as_separate_processes(self):
        fixture = Path(__file__).parent / "fixtures" / "reviews.json"
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "out"
            command = [sys.executable, "-m", "github_terrarium"]
            built_run = subprocess.run(
                [
                    *command,
                    "build",
                    "--snapshot",
                    str(fixture),
                    "--bootstrap",
                    "--bundle-dir",
                    str(out),
                    "--source-commit",
                    COMMIT,
                ],
                capture_output=True,
                check=False,
                cwd=directory,
            )
            self.assertEqual(built_run.returncode, 0, built_run.stderr)
            checked = subprocess.run(
                [*command, "validate", "--bundle-dir", str(out)],
                capture_output=True,
                check=False,
                cwd=directory,
            )
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertEqual(checked.stdout, built_run.stdout)
            manifest = copy.deepcopy(json.loads(checked.stdout))
            manifest["subject_id"] = "other"
            (out / MANIFEST).write_text(canonical_json(manifest))
            failed = subprocess.run(
                [*command, "validate", "--bundle-dir", str(out)],
                capture_output=True,
                check=False,
                cwd=directory,
            )
            self.assertEqual((failed.returncode, failed.stdout), (1, b""))
