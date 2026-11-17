import contextlib
import io
import json
import unittest
from datetime import timedelta
from unittest.mock import patch

from test_generate import DAY, REPO, Collector, Remote
from test_growth import total
from test_publish import COMMIT, FIRST, SECOND, run, subject

from github_terrarium import publish as publisher
from github_terrarium.bundle import MANIFEST, OWNED, STATE, SVG, build_files, digest
from github_terrarium.growth import advance
from github_terrarium.models import canonical_json


def reversion(files, **changes):
    """Return `files` with manifest or state fields changed and hashes kept valid."""
    manifest = json.loads(files[MANIFEST])
    state = json.loads(files[STATE])
    for key, value in changes.items():
        if key in state:
            state[key] = value
        manifest[key] = value
    state_bytes = canonical_json(state).encode()
    manifest["sha256"][STATE] = digest(state_bytes)
    return {
        **files,
        MANIFEST: canonical_json(manifest).encode(),
        STATE: state_bytes,
    }


class RestoreTests(Remote, unittest.TestCase):
    def commit(self, files, parent=None, ref="refs/heads/output"):
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
        if ref:
            self.rgit("update-ref", ref, commit)
        return commit

    def restore(self, source, parent):
        return run(
            "restore",
            "--repository",
            REPO,
            "--from-commit",
            source,
            "--expected-parent",
            parent,
            "--remote",
            self.url,
        )

    def files(self, commit):
        files = {}
        for entry in self.rgit("ls-tree", "-r", "-z", commit).split(b"\0"):
            if entry:
                meta, name = entry.split(b"\t", 1)
                sha = meta.decode().split(" ")[2]
                files[name.decode()] = self.rgit("cat-file", "blob", sha)
        return files

    def assert_refused(self, source, parent, code, message):
        before = self.head()
        result, out, err = self.restore(source, parent)
        self.assertEqual((result, out), (code, ""))
        self.assertIn(message, err)
        self.assertEqual(self.head(), before)

    def test_restores_historical_bytes_as_a_new_child(self):
        old = self.commit({**FIRST, "README.md": b"old\n"})
        head = self.commit(
            {**SECOND, "README.md": b"keep\n", "extra.txt": b"x"}, parent=old
        )
        code, out, err = self.restore(old, head)
        self.assertEqual((code, err), (0, ""))
        result = json.loads(out)
        self.assertEqual(out, canonical_json(result))
        self.assertEqual(
            result,
            {
                "commit": self.head(),
                "outcome": "restored",
                "parent": head,
                "restored_from": old,
                "sha256": {name: digest(FIRST[name]) for name in OWNED},
            },
        )
        self.assertEqual(
            self.files(result["commit"]),
            {**FIRST, "README.md": b"keep\n", "extra.txt": b"x"},
        )
        parents = self.rgit("rev-list", "--parents", "-n1", result["commit"]).split()
        self.assertEqual([p.decode() for p in parents[1:]], [head])
        self.assertEqual(self.rgit("rev-list", "--count", f"{head}..output"), b"1\n")
        self.assertEqual(
            self.rgit("rev-list", "output").decode().split(),
            [result["commit"], head, old],
        )
        message = self.rgit("log", "-1", "--format=%B", result["commit"]).decode()
        self.assertTrue(message.startswith(f"Restore terrarium bundle from {old[:12]}"))
        self.assertIn(f"Restored-From: {old}", message)

    def test_identical_bundle_is_no_change(self):
        old = self.commit(FIRST)
        middle = self.commit(SECOND, parent=old)
        head = self.commit({**FIRST, "README.md": b"x\n"}, parent=middle)
        for source in (old, head):
            with self.subTest(source=source):
                code, out, err = self.restore(source, head)
                self.assertEqual((code, err), (0, ""))
                result = json.loads(out)
                self.assertEqual(
                    (result["outcome"], result["commit"], result["parent"]),
                    ("no-change", head, head),
                )
                self.assertEqual(result["restored_from"], source)
                self.assertEqual(self.head(), head)

    def test_refuses_a_different_subject(self):
        old = self.commit(subject("U2"))
        head = self.commit(SECOND, parent=old)
        self.assert_refused(old, head, 1, "different subject")

    def test_refuses_missing_or_corrupt_historical_bundles(self):
        cases = {
            "missing state": (
                {k: v for k, v in FIRST.items() if k != STATE},
                "is invalid: Bundle is missing state.json",
            ),
            "tampered svg": ({**FIRST, SVG: FIRST[SVG] + b" "}, "Hash mismatch"),
            "corrupt manifest": ({**FIRST, MANIFEST: b"{"}, "Invalid or ambiguous"),
        }
        for case, (files, message) in cases.items():
            with self.subTest(case=case):
                old = self.commit(files)
                head = self.commit(SECOND, parent=old)
                self.assert_refused(old, head, 1, f"Historical bundle at {old}")
                self.assert_refused(old, head, 1, message)

    def test_refuses_unsupported_versions(self):
        cases = {
            "renderer": (reversion(FIRST, renderer_version=2), "renderer version"),
            "manifest": (reversion(FIRST, manifest_version=2), "manifest version"),
            "scoring": (reversion(FIRST, scoring_version=2), "state or scoring"),
            "schema": (reversion(FIRST, schema_version=2), "state or scoring"),
        }
        for case, (files, message) in cases.items():
            with self.subTest(case=case):
                old = self.commit(files)
                head = self.commit(SECOND, parent=old)
                self.assert_refused(
                    old, head, 1, f"Historical bundle at {old} is invalid: Unsupported"
                )
                self.assert_refused(old, head, 1, message)

    def test_refuses_unfinished_historical_recovery(self):
        state = {**json.loads(FIRST[STATE]), "recovery_target": "2026-12-31"}
        old = self.commit(build_files(state, COMMIT))
        head = self.commit(SECOND, parent=old)
        self.assert_refused(old, head, 1, "unfinished recovery_target")

    def test_refuses_a_commit_outside_the_output_history(self):
        other = self.commit(FIRST, ref="refs/heads/main")
        head = self.commit(SECOND)
        self.assert_refused(other, head, 1, "not in the output history")
        self.assert_refused("f" * 40, head, 1, "not in the output history")
        later = self.commit(FIRST, parent=head, ref=None)
        self.assert_refused(later, head, 1, "not in the output history")

    def test_refuses_a_fetched_commit_that_is_not_an_ancestor(self):
        other = self.commit(FIRST, ref="refs/heads/main")
        head = self.commit(SECOND)
        real = publisher._fetch

        def fetch_all(git, remote, expected):
            result = real(git, remote, expected)
            git("fetch", "--quiet", "--no-tags", remote, "refs/heads/main")
            return result

        with patch.object(publisher, "_fetch", side_effect=fetch_all):
            self.assert_refused(other, head, 1, "not in the output history")

    def test_refuses_an_invalid_current_head(self):
        old = self.commit(FIRST)
        head = self.commit({**SECOND, STATE: b"null\n"}, parent=old)
        self.assert_refused(old, head, 1, "Existing output is invalid")

    def test_stale_expected_parent_is_a_conflict(self):
        old = self.commit(FIRST)
        head = self.commit(SECOND, parent=old)
        self.assert_refused(old, old, 3, f"Output head is {head}, expected {old}")

    def test_absent_branch_is_a_conflict(self):
        self.assert_refused(COMMIT, COMMIT, 3, "Output branch is absent")
        self.assertIsNone(self.head())

    def test_rejected_push_is_a_conflict_without_retry(self):
        old = self.commit(FIRST)
        head = self.commit(SECOND, parent=old)
        other = self.commit(SECOND, parent=head, ref=None)
        real = publisher._push
        calls = []

        def race(git, remote, commit, parent):
            calls.append(commit)
            self.rgit("update-ref", "refs/heads/output", other, head)
            return real(git, remote, commit, parent)

        with patch.object(publisher, "_push", side_effect=race):
            code, out, err = self.restore(old, head)
        self.assertEqual((code, out), (3, ""))
        self.assertIn("push was rejected", err)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.head(), other)

    def test_readback_failure_names_the_pushed_commit(self):
        old = self.commit(FIRST)
        head = self.commit(SECOND, parent=old)

        def tampered(remote, token, commit):
            return commit, {**FIRST, SVG: FIRST[SVG] + b" "}

        with patch.object(publisher, "_read_back", side_effect=tampered):
            code, out, err = self.restore(old, head)
        self.assertEqual((code, out), (1, ""))
        self.assertRegex(err, r"Pushed [0-9a-f]{40} but readback failed")

    def test_usage_errors_exit_two(self):
        for args in (("absent", COMMIT), (COMMIT, "absent"), (COMMIT[:-1], COMMIT)):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    self.restore(*args)
                self.assertEqual(raised.exception.code, 2)

    def test_generate_after_restore_follows_recovery_rules(self):
        first = self.bootstrap(stars=10)["commit"]
        restored_state = self.state(first)
        second = self.generate(Collector(stars=(20,)), day=DAY + timedelta(days=1))
        self.assertEqual(self.state()["repository_watermarks"]["R1"]["stars"], 20)
        result = publisher.restore(REPO, first, second["commit"], remote=self.url)
        self.assertEqual(result["outcome"], "restored")
        self.assertEqual(self.state(), restored_state)

        later = DAY + timedelta(days=3)
        collector = Collector(stars=(20,))
        generated = self.generate(collector, day=later)
        self.assertEqual(generated["outcome"], "published")
        self.assertEqual(generated["recovered_gap_days"], 0)
        self.assertEqual(self.parent(generated["commit"]), result["commit"])
        self.assertEqual(
            [call[1:] for call in collector.calls],
            [(later - timedelta(days=30), later, later, "U1")],
        )
        state = self.state()
        self.assertEqual(state, advance(collector.snapshots[0], restored_state))
        self.assertEqual(generated["xp_delta"], total(state) - total(restored_state))
        days = state["days"]
        self.assertEqual(days["2026-11-16"]["new_star_units"], 0)
        self.assertEqual(days["2026-11-16"]["popularity_xp_awarded"], 0)
        self.assertEqual(days["2026-11-17"]["popularity_xp_awarded"], 0)
        self.assertGreater(days[later.isoformat()]["popularity_xp_awarded"], 0)
        self.assertEqual(
            sum(d["new_star_units"] for d in days.values())
            - sum(d["new_star_units"] for d in restored_state["days"].values()),
            10,
        )
        self.assert_valid_remote(generated["commit"])

    def test_generate_after_restore_recovers_the_gap_from_the_restored_day(self):
        first = self.bootstrap(stars=10)["commit"]
        restored_state = self.state(first)
        second = self.generate(Collector(stars=(20,)), day=DAY + timedelta(days=1))
        restored = publisher.restore(REPO, first, second["commit"], remote=self.url)

        late = DAY + timedelta(days=100)
        collector = Collector(stars=(20,))
        with self.assertRaisesRegex(
            ValueError, "Gap exceeds 90 days.*--recover-through"
        ):
            self.generate(collector, day=late)
        self.assertEqual(collector.calls, [])
        self.assertEqual(self.head(), restored["commit"])

        later = DAY + timedelta(days=40)
        collector = Collector(stars=(20,))
        generated = self.generate(collector, day=later)
        self.assertEqual(
            generated["activity_interval"],
            {"end": later.isoformat(), "start": "2026-11-15"},
        )
        self.assertEqual(generated["recovered_gap_days"], 10)
        self.assertEqual(self.parent(generated["commit"]), restored["commit"])
        self.assertEqual(self.state(), advance(collector.snapshots[0], restored_state))
        self.assert_valid_remote(generated["commit"])


if __name__ == "__main__":
    unittest.main()
