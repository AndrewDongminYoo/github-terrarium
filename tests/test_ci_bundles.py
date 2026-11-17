"""Bundle regression script contracts, including its own negative paths."""

import contextlib
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOL = Path(__file__).resolve().parents[1] / "tools" / "ci_bundles.py"
spec = importlib.util.spec_from_file_location("ci_bundles", TOOL)
ci_bundles = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci_bundles)

COMMIT = "0123456789abcdef0123456789abcdef01234567"


class CiBundlesTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.log = Path(directory.name) / "logs" / "ci-bundles.log"

    def main(self, *extra):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            status = ci_bundles.main(
                ["--log", str(self.log), "--source-commit", COMMIT, *extra]
            )
        return status, stdout.getvalue().splitlines()

    def test_every_fixture_and_the_tampered_bundle_pass(self):
        status, lines = self.main()

        self.assertEqual(status, 0)
        personas = sorted(p.stem for p in ci_bundles.FIXTURES.glob("*.json"))
        self.assertEqual(
            lines,
            [f"ok {name}: built, validated, rebuilt identically" for name in personas]
            + ["ok tampered: validate rejected a changed terrarium.svg with exit 1"],
        )
        self.assertEqual(self.log.read_text().splitlines(), lines)

    def test_removing_the_tamper_step_fails_the_script(self):
        with mock.patch.object(ci_bundles, "tamper", lambda path: None):
            status, lines = self.main()

        self.assertEqual(status, 1)
        self.assertEqual(lines[-1], "FAIL tampered: validate exited 0, expected 1")

    def test_a_rejection_for_another_reason_fails_the_script(self):
        def remove(path):
            Path(path).unlink()

        with mock.patch.object(ci_bundles, "tamper", remove):
            status, lines = self.main()

        self.assertEqual(status, 1)
        self.assertTrue(lines[-1].startswith("FAIL tampered: validate rejected"))

    def test_a_nondeterministic_rebuild_fails_the_script(self):
        original = ci_bundles.build

        def drifting(fixture, directory, commit):
            failure = original(fixture, directory, commit)
            if directory.name == "second":
                path = directory / "state.json"
                path.write_bytes(path.read_bytes() + b" ")
            return failure

        with mock.patch.object(ci_bundles, "build", drifting):
            status, lines = self.main()

        self.assertEqual(status, 1)
        self.assertIn("FAIL empty: rebuild is not byte-identical: state.json", lines)
        self.assertEqual(lines[-1], "FAIL tampered: no valid bundle to tamper with")

    def test_a_failing_build_fails_the_script(self):
        with tempfile.TemporaryDirectory() as fixtures:
            Path(fixtures, "broken.json").write_text("{}")
            status, lines = self.main("--fixtures", fixtures)

        self.assertEqual(status, 1)
        self.assertTrue(lines[0].startswith("FAIL broken: build exited 1: error:"))

    def test_an_empty_fixture_directory_fails_the_script(self):
        with tempfile.TemporaryDirectory() as fixtures:
            status, lines = self.main("--fixtures", fixtures)

        self.assertEqual(status, 1)
        self.assertEqual(lines, [f"FAIL no fixtures in {fixtures}"])

    def test_the_actions_commit_takes_precedence_over_head(self):
        with mock.patch.dict(os.environ, {"GITHUB_SHA": COMMIT}):
            self.assertEqual(ci_bundles.checked_out_commit(), COMMIT)

    def test_tamper_changes_exactly_one_byte(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "file"
            path.write_bytes(b"abcdef")
            ci_bundles.tamper(path)
            changed = path.read_bytes()

        self.assertEqual(len(changed), 6)
        self.assertEqual(sum(a != b for a, b in zip(changed, b"abcdef")), 1)


if __name__ == "__main__":
    unittest.main()
