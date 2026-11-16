import contextlib
import copy
import io
import json
import os
import subprocess
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from test_growth import snapshot, total
from test_publish import ENV, git

from github_terrarium import generate as generator
from github_terrarium import publish as publisher
from github_terrarium.__main__ import main
from github_terrarium.bundle import OWNED, STATE, SVG, build_files, validate_files
from github_terrarium.config import Config
from github_terrarium.growth import advance
from github_terrarium.models import canonical_json
from github_terrarium.publish import PublishConflict, ReadbackError

COMMIT = "0123456789abcdef0123456789abcdef01234567"
DAY = date(2026, 11, 15)
REPO = "octocat/github-terrarium"
CONFIG = Config("octocat", REPO)


class Collector:
    """A fake collection provider; `hooks[i]` runs before call `i` returns."""

    def __init__(self, *, stars=(10,), prs=1, subject="U1", hooks=()):
        self.stars = list(stars)
        self.prs = prs
        self.subject = subject
        self.hooks = list(hooks)
        self.calls = []
        self.snapshots = []

    def __call__(self, config, start, end, *, observed_on, expected_subject):
        index = len(self.calls)
        self.calls.append((config, start, end, observed_on, expected_subject))
        if index < len(self.hooks) and self.hooks[index]:
            self.hooks[index]()
        value = snapshot(
            end=end,
            start=start,
            prs=self.prs,
            stars=self.stars[min(index, len(self.stars) - 1)],
        )
        value["observed_on"] = observed_on.isoformat()
        value["subject"]["id"] = self.subject
        self.snapshots.append(value)
        return copy.deepcopy(value)


class Remote:
    """A local bare remote with plumbing helpers, mixed into each test case."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.remote = self.root / "remote.git"
        git("init", "--bare", "--quiet", str(self.remote))
        self.url = self.remote.as_uri()

    def rgit(self, *args, data=None):
        return git(f"--git-dir={self.remote}", *args, data=data)

    def head(self):
        result = subprocess.run(
            ["git", f"--git-dir={self.remote}", "rev-parse", "--verify", "-q"]
            + ["refs/heads/output"],
            env=ENV,
            capture_output=True,
        )
        return result.stdout.decode().strip() or None

    def owned(self, commit=None):
        commit = commit or self.head()
        return {
            name: self.rgit("cat-file", "blob", f"{commit}:{name}") for name in OWNED
        }

    def state(self, commit=None):
        return json.loads(self.owned(commit)[STATE])

    def parent(self, commit):
        return self.rgit("rev-parse", f"{commit}^").decode().strip()

    def seed(self, files, parent=None):
        lines = []
        for name, raw in files.items():
            sha = self.rgit("hash-object", "-w", "--stdin", data=raw).decode().strip()
            lines.append(f"100644 blob {sha}\t{name}")
        tree = self.rgit("mktree", data=("\n".join(lines) + "\n").encode())
        args = ["-p", parent] if parent else []
        commit = (
            self.rgit("commit-tree", tree.decode().strip(), *args, "-m", "seed")
            .decode()
            .strip()
        )
        self.rgit("update-ref", "refs/heads/output", commit)
        return commit

    def generate(self, collector, *, day=DAY, bootstrap=False, commit=COMMIT):
        return generator.generate(
            CONFIG,
            REPO,
            commit,
            bootstrap=bootstrap,
            remote=self.url,
            clock=lambda: day,
            collector=collector,
        )

    def bootstrap(self, day=DAY, stars=10):
        return self.generate(Collector(stars=(stars,)), day=day, bootstrap=True)

    def other_publisher(self, stars, day=DAY):
        """Return a hook that publishes a newer bundle as another writer."""
        published = []

        def hook():
            head = self.head()
            prior = self.state(head)
            start = min(
                day - timedelta(days=30),
                date.fromisoformat(prior["last_complete_activity_day"])
                + timedelta(days=1),
            )
            files = build_files(
                advance(snapshot(end=day, start=start, prs=1, stars=stars), prior),
                COMMIT,
            )
            bundle = self.root / f"other-{len(list(self.root.iterdir()))}"
            bundle.mkdir()
            for name, raw in files.items():
                (bundle / name).write_bytes(raw)
            result = publisher.publish(bundle, REPO, head, remote=self.url)
            published.append(result["commit"])

        return hook, published

    def assert_valid_remote(self, commit):
        self.assertEqual(self.head(), commit)
        validate_files(self.owned(commit))


class GenerateTests(Remote, unittest.TestCase):
    def test_bootstrap_publishes_a_root_bundle(self):
        collector = Collector()
        result = self.generate(collector, bootstrap=True)
        state = self.state()
        self.assertEqual(
            result,
            {
                "activity_interval": {
                    "end": "2026-11-15",
                    "start": "2026-10-16",
                },
                "attempts": 1,
                "bytes": {
                    STATE: len(self.owned()[STATE]),
                    SVG: len(self.owned()[SVG]),
                },
                "commit": self.head(),
                "outcome": "published",
                "recovered_gap_days": 0,
                "stock_observation_day": "2026-11-15",
                "subject_id": "U1",
                "xp_delta": total(state),
            },
        )
        self.assertEqual(
            [call[1:] for call in collector.calls],
            [(date(2026, 10, 16), DAY, DAY, None)],
        )
        self.assertEqual(state, advance(collector.snapshots[0]))
        self.assert_valid_remote(result["commit"])

    def test_absent_branch_requires_bootstrap(self):
        collector = Collector()
        with self.assertRaisesRegex(ValueError, "rerun with --bootstrap"):
            self.generate(collector)
        self.assertEqual(collector.calls, [])
        self.assertIsNone(self.head())

    def test_bootstrap_refuses_existing_branch(self):
        first = self.bootstrap()["commit"]
        collector = Collector()
        with self.assertRaisesRegex(ValueError, "existing output branch"):
            self.generate(collector, bootstrap=True)
        self.assertEqual(collector.calls, [])
        self.assert_valid_remote(first)

    def test_different_day_advance_and_recovered_gap(self):
        first = self.bootstrap()["commit"]
        collector = Collector()
        result = self.generate(collector, day=DAY + timedelta(days=1))
        self.assertEqual(result["outcome"], "published")
        self.assertEqual(
            result["activity_interval"],
            {"end": "2026-11-16", "start": "2026-10-17"},
        )
        self.assertEqual(result["recovered_gap_days"], 0)
        self.assertEqual(result["stock_observation_day"], "2026-11-16")
        self.assertEqual(collector.calls[0][4], "U1")
        self.assertEqual(self.parent(result["commit"]), first)
        later = self.generate(Collector(), day=DAY + timedelta(days=41))
        self.assertEqual(
            later["activity_interval"],
            {"end": "2026-12-26", "start": "2026-11-16"},
        )
        self.assertEqual(later["recovered_gap_days"], 10)
        self.assertGreater(later["xp_delta"], 0)
        self.assert_valid_remote(later["commit"])

    def test_same_day_rerun_with_newer_popularity_publishes(self):
        first = self.bootstrap(stars=10)["commit"]
        result = self.generate(Collector(stars=(15,)))
        self.assertEqual(result["outcome"], "published")
        self.assertEqual(result["xp_delta"], 10)
        self.assertEqual(result["stock_observation_day"], "2026-11-15")
        self.assertEqual(self.parent(result["commit"]), first)
        self.assertEqual(self.state()["repository_watermarks"]["R1"]["stars"], 15)

    def test_identical_rerun_is_no_change(self):
        first = self.bootstrap()["commit"]
        result = self.generate(Collector())
        self.assertEqual(result["outcome"], "no-change")
        self.assertEqual(result["commit"], first)
        self.assertEqual(result["xp_delta"], 0)
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(self.head(), first)

    def test_identity_mismatch_fails_and_keeps_output(self):
        first = self.bootstrap()["commit"]
        collector = Collector(subject="U2")
        with self.assertRaisesRegex(ValueError, "Subject identity mismatch"):
            self.generate(collector)
        self.assertEqual(collector.calls[0][4], "U1")
        self.assert_valid_remote(first)

    def test_conflict_recollects_against_the_latest_state(self):
        first = self.bootstrap(stars=10)["commit"]
        hook, published = self.other_publisher(stars=20)
        collector = Collector(stars=(12, 15), hooks=(hook,))
        result = self.generate(collector)
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(len(collector.calls), 2)
        self.assertIsNot(collector.snapshots[0], collector.snapshots[1])
        self.assertNotEqual(collector.snapshots[0], collector.snapshots[1])
        self.assertEqual(self.parent(published[0]), first)
        self.assertEqual(self.parent(result["commit"]), published[0])
        newer = self.state(published[0])
        self.assertEqual(
            self.owned()[STATE],
            canonical_json(advance(collector.snapshots[1], newer)).encode(),
        )
        state = self.state()
        self.assertEqual(state["repository_watermarks"]["R1"]["stars"], 20)
        self.assertEqual(
            state["days"]["2026-11-15"]["new_star_units"],
            newer["days"]["2026-11-15"]["new_star_units"],
        )
        self.assertEqual(result["xp_delta"], total(state) - total(newer))
        self.assert_valid_remote(result["commit"])

    def test_second_conflict_fails_and_keeps_newer_output(self):
        self.bootstrap()
        first, published = self.other_publisher(stars=20)
        second, _ = self.other_publisher(stars=30)
        collector = Collector(hooks=(first, second))
        with self.assertRaisesRegex(PublishConflict, "moved again"):
            self.generate(collector)
        self.assertEqual(len(collector.calls), 2)
        self.assertEqual(self.state()["repository_watermarks"]["R1"]["stars"], 30)
        self.assertEqual(self.parent(self.head()), published[0])
        validate_files(self.owned())

    def test_failed_recollection_keeps_newer_output(self):
        self.bootstrap()
        hook, published = self.other_publisher(stars=20)

        def fail():
            raise ValueError("Collection failed")

        collector = Collector(hooks=(hook, fail))
        with self.assertRaisesRegex(ValueError, "Collection failed"):
            self.generate(collector)
        self.assertEqual(len(collector.calls), 2)
        self.assert_valid_remote(published[0])

    def test_conflict_during_read_retries_from_a_fresh_read(self):
        first = self.bootstrap()["commit"]
        real = generator.read_output
        reads = []

        def read(*args, **kwargs):
            reads.append(args)
            if len(reads) == 1:
                raise PublishConflict("moved during fetch")
            return real(*args, **kwargs)

        collector = Collector(stars=(15,))
        with patch.object(generator, "read_output", side_effect=read):
            result = self.generate(collector)
        self.assertEqual(len(reads), 2)
        self.assertEqual(len(collector.calls), 1)
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(self.parent(result["commit"]), first)

    def test_readback_failure_is_not_retried(self):
        self.bootstrap()
        collector = Collector(stars=(15,))
        with patch.object(publisher, "_read_back", side_effect=ValueError("transport")):
            with self.assertRaises(ReadbackError):
                self.generate(collector)
        self.assertEqual(len(collector.calls), 1)

    def test_corrupt_or_missing_remote_bundle_never_bootstraps(self):
        valid = build_files(advance(snapshot(prs=1)), COMMIT)
        for files in (
            {**valid, STATE: b"{}\n"},
            {**valid, STATE: b"null\n"},
            {"README.md": b"not a bundle\n"},
        ):
            for bootstrap in (False, True):
                with self.subTest(files=sorted(files), bootstrap=bootstrap):
                    commit = self.seed(files)
                    collector = Collector()
                    with self.assertRaisesRegex(
                        ValueError, "Existing output is invalid"
                    ):
                        self.generate(collector, bootstrap=bootstrap)
                    self.assertEqual(collector.calls, [])
                    self.assertEqual(self.head(), commit)

    def test_unfinished_recovery_state_is_refused(self):
        state = advance(snapshot(prs=1))
        state["recovery_target"] = (DAY + timedelta(days=5)).isoformat()
        commit = self.seed(build_files(state, COMMIT))
        collector = Collector()
        with self.assertRaisesRegex(
            ValueError, "Finish explicit recovery.*--recover-through"
        ):
            self.generate(collector, day=DAY + timedelta(days=1))
        self.assertEqual(collector.calls, [])
        self.assertEqual(self.head(), commit)

    def test_gap_over_ninety_days_fails_before_collection(self):
        first = self.bootstrap(day=DAY - timedelta(days=100))["commit"]
        collector = Collector()
        with self.assertRaisesRegex(
            ValueError, "Gap exceeds 90 days.*--recover-through"
        ):
            self.generate(collector)
        self.assertEqual(collector.calls, [])
        self.assert_valid_remote(first)

    def test_output_newer_than_clock_fails_before_collection(self):
        first = self.bootstrap()["commit"]
        collector = Collector()
        with self.assertRaisesRegex(ValueError, "newer than the current UTC date"):
            self.generate(collector, day=DAY - timedelta(days=1))
        self.assertEqual(collector.calls, [])
        self.assertEqual(self.head(), first)


class GenerateCommandTests(Remote, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.config = self.root / "terrarium.toml"
        self.config.write_text('login = "octocat"\n')
        environment = patch.dict(os.environ, {"GITHUB_SHA": COMMIT})
        environment.start()
        self.addCleanup(environment.stop)
        for name in ("GH_TOKEN", "GITHUB_TOKEN"):
            os.environ.pop(name, None)

    def run_cli(self, collector, *extra, clock=DAY):
        output, error = io.StringIO(), io.StringIO()
        with (
            patch.object(generator, "collector_for", return_value=collector),
            patch.object(generator, "today", return_value=clock),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(error),
        ):
            code = main(
                [
                    "generate",
                    "--config",
                    str(self.config),
                    "--repository",
                    REPO,
                    "--remote",
                    self.url,
                    *extra,
                ]
            )
        return code, output.getvalue(), error.getvalue()

    def test_cli_success_prints_one_canonical_summary(self):
        code, out, err = self.run_cli(
            Collector(), "--bootstrap", clock=date(2026, 1, 15)
        )
        self.assertEqual((code, err), (0, ""))
        result = json.loads(out)
        self.assertEqual(out, canonical_json(result))
        self.assertEqual(
            result["activity_interval"],
            {"end": "2026-01-15", "start": "2025-12-16"},
        )
        self.assertEqual(result["commit"], self.head())
        manifest = json.loads(self.owned()["manifest.json"])
        self.assertEqual(manifest["source_commit"], COMMIT)

    def test_cli_usage_errors_exit_two(self):
        cases = [
            ({}, ("--source-commit", COMMIT[:-1])),
            ({}, ("--source-commit", COMMIT.upper())),
            ({"GITHUB_SHA": "nope"}, ()),
        ]
        for env, extra in cases:
            with self.subTest(env=env, extra=extra):
                with (
                    patch.dict(os.environ, env),
                    contextlib.redirect_stderr(io.StringIO()),
                    self.assertRaises(SystemExit) as raised,
                ):
                    self.run_cli(Collector(), *extra)
                self.assertEqual(raised.exception.code, 2)
        os.environ.pop("GITHUB_SHA")
        with (
            contextlib.redirect_stderr(io.StringIO()) as error,
            self.assertRaises(SystemExit) as raised,
        ):
            main(["generate", "--config", str(self.config), "--repository", REPO])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("GITHUB_SHA", error.getvalue())
        with (
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as raised,
        ):
            main(["generate", "--config", "x", "--repository", "nope"])
        self.assertEqual(raised.exception.code, 2)

    def test_cli_failures_print_nothing_and_leave_checkout_intact(self):
        self.bootstrap()
        source = self.root / "source"
        source.mkdir()
        git("init", "--quiet", str(source))
        (source / "tracked.txt").write_text("one\n")
        git("-C", str(source), "add", "tracked.txt")
        git("-C", str(source), "commit", "--quiet", "--no-gpg-sign", "-m", "init")
        (source / "tracked.txt").write_text("dirty\n")
        (source / "untracked.txt").write_text("secret\n")
        before = {
            p: p.read_bytes()
            for p in (
                source / ".git" / "HEAD",
                source / ".git" / "index",
                source / ".git" / "config",
                source / "tracked.txt",
                source / "untracked.txt",
            )
        }
        refs = git("-C", str(source), "show-ref")
        first, _ = self.other_publisher(stars=20)
        second, published = self.other_publisher(stars=30)

        def fail():
            raise ValueError("Collection failed")

        recollect, newer = self.other_publisher(stars=40)
        cwd = os.getcwd()
        os.chdir(source)
        try:
            with patch.dict(os.environ, {"GIT_DIR": str(source / ".git")}):
                conflict = self.run_cli(Collector(hooks=(first, second)))
                failure = self.run_cli(Collector(hooks=(recollect, fail)))
        finally:
            os.chdir(cwd)
        self.assertEqual(conflict[:2], (3, ""))
        self.assertRegex(conflict[2], r"\Aconflict: [^\n]+\n\Z")
        self.assertEqual(failure[:2], (1, ""))
        self.assertEqual(failure[2], "error: Collection failed\n")
        self.assertEqual({p: p.read_bytes() for p in before}, before)
        self.assertEqual(git("-C", str(source), "show-ref"), refs)
        self.assert_valid_remote(newer[0])
        self.assertEqual(self.parent(newer[0]), published[0])


if __name__ == "__main__":
    unittest.main()
