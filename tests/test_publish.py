import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from test_growth import snapshot

from github_terrarium import publish as publisher
from github_terrarium.__main__ import main
from github_terrarium.bundle import MANIFEST, OWNED, STATE, SVG, build_files, digest
from github_terrarium.growth import advance
from github_terrarium.models import canonical_json

COMMIT = "0123456789abcdef0123456789abcdef01234567"
PRIOR = advance(snapshot(prs=1))
FIRST = build_files(PRIOR, COMMIT)
SECOND = build_files(advance(snapshot(end=date(2026, 11, 16), prs=2), PRIOR), COMMIT)
ENV = {
    **{k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
    "GIT_AUTHOR_NAME": "fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_NAME": "fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}


def git(*args, data=None):
    return subprocess.run(
        ["git", *args], input=data, env=ENV, capture_output=True, check=True
    ).stdout


def run(*args):
    output, error = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
        code = main(list(args))
    return code, output.getvalue(), error.getvalue()


def subject(identifier):
    value = snapshot(prs=1)
    value["subject"]["id"] = identifier
    return build_files(advance(value), COMMIT)


class PublishTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.remote = self.root / "remote.git"
        git("init", "--bare", "--quiet", str(self.remote))
        self.url = self.remote.as_uri()

    def rgit(self, *args, data=None):
        return git(f"--git-dir={self.remote}", *args, data=data)

    def blob(self, raw):
        return self.rgit("hash-object", "-w", "--stdin", data=raw).decode().strip()

    def seed(self, files, parent=None, ref="refs/heads/output"):
        """Commit {name: bytes or None-for-subtree} directly into the remote."""
        lines = [f"100644 blob {self.blob(raw)}\t{name}" for name, raw in files.items()]
        sub = self.rgit(
            "mktree", data=f"100644 blob {self.blob(b'n')}\tnote.txt\n".encode()
        )
        lines.append(f"040000 tree {sub.decode().strip()}\tnotes")
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

    def head(self):
        result = subprocess.run(
            [
                "git",
                f"--git-dir={self.remote}",
                "rev-parse",
                "--verify",
                "-q",
                "refs/heads/output",
            ],
            env=ENV,
            capture_output=True,
        )
        return result.stdout.decode().strip() or None

    def tree(self, commit):
        files = {}
        for entry in self.rgit("ls-tree", "-r", "-z", commit).split(b"\0"):
            if entry:
                meta, name = entry.split(b"\t", 1)
                sha = meta.decode().split(" ")[2]
                files[name.decode()] = self.rgit("cat-file", "blob", sha)
        return files

    def bundle(self, files, name="bundle"):
        directory = self.root / name
        directory.mkdir()
        for key, raw in files.items():
            (directory / key).write_bytes(raw)
        return str(directory)

    def publish(self, files, parent, *extra):
        return run(
            "publish",
            "--bundle-dir",
            self.bundle(files, name=f"bundle-{len(list(self.root.iterdir()))}"),
            "--repository",
            "octocat/github-terrarium",
            "--expected-parent",
            parent,
            "--remote",
            self.url,
            *extra,
        )

    def test_bootstrap_creates_root_commit_on_absent_branch(self):
        code, out, err = self.publish(FIRST, "absent", "--bootstrap")
        self.assertEqual((code, err), (0, ""))
        result = json.loads(out)
        self.assertEqual(out, canonical_json(result))
        self.assertEqual(result["outcome"], "published")
        self.assertIsNone(result["parent"])
        self.assertEqual(result["commit"], self.head())
        self.assertEqual(result["sha256"], {n: digest(FIRST[n]) for n in OWNED})
        self.assertEqual(self.tree(result["commit"]), FIRST)
        parents = self.rgit("rev-list", "--parents", "-n1", result["commit"]).split()
        self.assertEqual(len(parents), 1)

    def test_bootstrap_refuses_existing_branch(self):
        old = self.seed(FIRST)
        code, out, err = self.publish(SECOND, "absent", "--bootstrap")
        self.assertEqual((code, out), (1, ""))
        self.assertIn("existing output branch", err)
        self.assertEqual(self.head(), old)

    def test_expected_parent_on_absent_branch_is_a_conflict(self):
        code, out, err = self.publish(FIRST, COMMIT)
        self.assertEqual((code, out), (3, ""))
        self.assertIn(f"Output branch is absent, expected {COMMIT}", err)
        self.assertIsNone(self.head())

    def test_deleted_branch_under_sha_parent_is_a_conflict(self):
        old = self.seed(FIRST)
        self.rgit("update-ref", "-d", "refs/heads/output")
        code, out, err = self.publish(SECOND, old)
        self.assertEqual((code, out), (3, ""))
        self.assertIn(f"Output branch is absent, expected {old}", err)
        self.assertIsNone(self.head())
        self.assertEqual(self.rgit("for-each-ref"), b"")

    def test_usage_errors_exit_two(self):
        for args in (
            ("absent",),
            (COMMIT, "--bootstrap"),
            ("ABC",),
            (COMMIT[:-1],),
        ):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    self.publish(FIRST, *args)
                self.assertEqual(raised.exception.code, 2)
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                main(
                    [
                        "publish",
                        "--bundle-dir",
                        "x",
                        "--repository",
                        "nope",
                        "--expected-parent",
                        "absent",
                        "--bootstrap",
                    ]
                )
        self.assertEqual(raised.exception.code, 2)

    def test_update_replaces_only_owned_paths(self):
        old = self.seed({**FIRST, "README.md": b"keep\n"})
        code, out, err = self.publish(SECOND, old)
        self.assertEqual((code, err), (0, ""))
        result = json.loads(out)
        self.assertEqual(result["parent"], old)
        self.assertEqual(result["commit"], self.head())
        self.assertEqual(
            self.tree(result["commit"]),
            {**SECOND, "README.md": b"keep\n", "notes/note.txt": b"n"},
        )
        parents = self.rgit("rev-list", "--parents", "-n1", result["commit"]).split()
        self.assertEqual([p.decode() for p in parents[1:]], [old])
        self.assertEqual(self.rgit("rev-list", "--count", f"{old}..output"), b"1\n")

    def test_identical_bundle_is_no_change(self):
        old = self.seed(FIRST)
        code, out, err = self.publish(FIRST, old)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(
            json.loads(out),
            {
                "commit": old,
                "outcome": "no-change",
                "parent": old,
                "sha256": {n: digest(FIRST[n]) for n in OWNED},
            },
        )
        self.assertEqual(self.head(), old)

    def test_existing_output_without_valid_bundle_fails_closed(self):
        cases = {
            "missing state": {k: v for k, v in FIRST.items() if k != STATE},
            "null state": {**FIRST, STATE: b"null\n"},
            "corrupt manifest": {**FIRST, MANIFEST: b"{"},
            "tampered svg": {**FIRST, SVG: FIRST[SVG] + b" "},
        }
        for case, files in cases.items():
            with self.subTest(case=case):
                old = self.seed(files)
                code, out, err = self.publish(SECOND, old)
                self.assertEqual((code, out), (1, ""))
                self.assertIn("Existing output", err)
                self.assertEqual(self.head(), old)

    def test_rejects_different_subject_and_backwards_dates(self):
        old = self.seed(SECOND)
        for files, message in (
            (subject("U2"), "different subject"),
            (FIRST, "last_complete_activity_day precedes"),
        ):
            with self.subTest(message=message):
                code, out, err = self.publish(files, old)
                self.assertEqual((code, out), (1, ""))
                self.assertIn(message, err)
                self.assertEqual(self.head(), old)

    def test_rejects_backwards_popularity_observation(self):
        # Explicit recovery advances activity to SECOND's day but leaves
        # popularity one day behind SECOND's observation.
        recovered = advance(
            snapshot(start=date(2026, 11, 15), end=date(2026, 11, 16), prs=2),
            PRIOR,
            recover_through=date(2026, 11, 16),
        )
        self.assertEqual(
            (
                recovered["last_complete_activity_day"],
                recovered["last_popularity_observation_day"],
            ),
            ("2026-11-15", "2026-11-15"),
        )
        old = self.seed(SECOND)
        code, out, err = self.publish(build_files(recovered, COMMIT), old)
        self.assertEqual((code, out), (1, ""))
        self.assertIn("last_popularity_observation_day precedes", err)
        self.assertEqual(self.head(), old)

    def test_rejects_reset_growth_at_equal_dates(self):
        reset = build_files(advance(snapshot(end=date(2026, 11, 16))), COMMIT)
        self.assertEqual(
            json.loads(reset[STATE])["last_popularity_observation_day"],
            json.loads(SECOND[STATE])["last_popularity_observation_day"],
        )
        old = self.seed(SECOND)
        code, out, err = self.publish(reset, old)
        self.assertEqual((code, out), (1, ""))
        self.assertIn("drops existing day", err)
        self.assertEqual(self.head(), old)

    def test_same_day_rerun_with_raised_stars_publishes(self):
        first = advance(snapshot(stars=10))
        rerun = advance(snapshot(stars=13), first)
        for key in ("last_complete_activity_day", "last_popularity_observation_day"):
            self.assertEqual(rerun[key], first[key])
        self.assertEqual(rerun["repository_watermarks"]["R1"]["stars"], 13)
        old = self.seed(build_files(first, COMMIT))
        code, out, err = self.publish(build_files(rerun, COMMIT), old)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(json.loads(out)["outcome"], "published")
        self.assertEqual(json.loads(out)["commit"], self.head())

    def test_rejects_same_day_rerun_that_lowers_watermark(self):
        first = advance(snapshot(stars=13))
        lowered = advance(snapshot(stars=13), first)
        lowered["repository_watermarks"]["R1"]["stars"] = 10
        lowered["current_traits"]["stars"] = 10
        old = self.seed(build_files(first, COMMIT))
        code, out, err = self.publish(build_files(lowered, COMMIT), old)
        self.assertEqual((code, out), (1, ""))
        self.assertIn("lowers repository watermark R1", err)
        self.assertEqual(self.head(), old)

    def test_rejects_later_habitat_that_drops_growth(self):
        rebuilt = build_files(advance(snapshot(end=date(2026, 11, 17))), COMMIT)
        lowered = advance(snapshot(end=date(2026, 11, 16), prs=2), PRIOR)
        lowered["repository_watermarks"]["R1"]["stars"] = 5
        lowered["current_traits"]["stars"] = 5
        for files, message in (
            (rebuilt, "drops existing day 2026-10-16"),
            (build_files(lowered, COMMIT), "lowers repository watermark R1"),
        ):
            with self.subTest(message=message):
                old = self.seed(FIRST)
                code, out, err = self.publish(files, old)
                self.assertEqual((code, out), (1, ""))
                self.assertIn(message, err)
                self.assertEqual(self.head(), old)

    def test_same_state_with_new_source_commit_publishes(self):
        old = self.seed(FIRST)
        code, out, err = self.publish(build_files(PRIOR, "f" * 40), old)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(json.loads(out)["outcome"], "published")
        self.assertEqual(json.loads(out)["commit"], self.head())

    def test_rejects_unfinished_recovery_before_network(self):
        state = {**json.loads(SECOND[STATE]), "recovery_target": "2026-12-31"}
        with patch.object(publisher, "_remote_head") as lookup:
            code, out, err = self.publish(
                build_files(state, COMMIT), "absent", "--bootstrap"
            )
        self.assertEqual((code, out), (1, ""))
        self.assertIn("recovery_target", err)
        lookup.assert_not_called()

    def test_invalid_candidate_bundle_fails(self):
        code, out, err = self.publish(
            {**FIRST, SVG: b"<svg/>"}, "absent", "--bootstrap"
        )
        self.assertEqual((code, out), (1, ""))
        self.assertIsNone(self.head())

    def test_moved_head_is_a_conflict(self):
        old = self.seed(FIRST)
        newer = self.seed(SECOND, parent=old)
        code, out, err = self.publish(SECOND, old)
        self.assertEqual((code, out), (3, ""))
        self.assertIn("conflict:", err)
        self.assertEqual(self.head(), newer)

    def test_lookup_failure_is_not_absent(self):
        self.url = (self.root / "missing.git").as_uri()
        code, out, err = self.publish(FIRST, "absent", "--bootstrap")
        self.assertEqual((code, out), (1, ""))
        self.assertIn("lookup failed", err)

    def test_rejected_push_is_a_conflict_without_force(self):
        old = self.seed(FIRST)
        other = self.seed(SECOND, parent=old, ref=None)
        real = publisher._push

        def race(git, remote, commit, parent):
            self.rgit("update-ref", "refs/heads/output", other, old)
            return real(git, remote, commit, parent)

        with patch.object(publisher, "_push", side_effect=race):
            code, out, err = self.publish(SECOND, old)
        self.assertEqual((code, out), (3, ""))
        self.assertIn("push was rejected", err)
        self.assertEqual(self.head(), other)

    def test_rewound_or_deleted_head_before_push_is_a_conflict(self):
        for case in ("rewound", "deleted"):
            with self.subTest(case=case):
                grand = self.seed(FIRST)
                old = self.seed(FIRST, parent=grand)
                real = publisher._push

                def race(git, remote, commit, parent, old=old, grand=grand):
                    if case == "rewound":
                        self.rgit("update-ref", "refs/heads/output", grand, old)
                    else:
                        self.rgit("update-ref", "-d", "refs/heads/output", old)
                    return real(git, remote, commit, parent)

                with patch.object(publisher, "_push", side_effect=race):
                    code, out, err = self.publish(SECOND, old)
                self.assertEqual((code, out), (3, ""))
                self.assertIn("push was rejected", err)
                self.assertEqual(self.head(), grand if case == "rewound" else None)

    def test_bootstrap_conflicts_with_branch_created_before_push(self):
        other = self.seed(SECOND, ref=None)
        real = publisher._push

        def race(git, remote, commit, parent):
            self.rgit("update-ref", "refs/heads/output", other, "")
            return real(git, remote, commit, parent)

        with patch.object(publisher, "_push", side_effect=race):
            code, out, err = self.publish(FIRST, "absent", "--bootstrap")
        self.assertEqual((code, out), (3, ""))
        self.assertIn("push was rejected", err)
        self.assertEqual(self.head(), other)

    def test_head_moved_during_fetch_is_a_conflict(self):
        old = self.seed(FIRST)
        newer = self.seed(SECOND, parent=old, ref=None)
        real = publisher._fetch

        def race(git, remote, expected):
            self.rgit("update-ref", "refs/heads/output", newer, old)
            return real(git, remote, expected)

        with (
            patch.object(publisher, "_fetch", side_effect=race),
            patch.object(publisher, "_push") as push,
        ):
            code, out, err = self.publish(SECOND, old)
        self.assertEqual((code, out), (3, ""))
        self.assertIn("during fetch", err)
        push.assert_not_called()
        self.assertEqual(self.head(), newer)

    def test_head_deleted_during_fetch_is_a_conflict(self):
        old = self.seed(FIRST)
        real = publisher._fetch

        def race(git, remote, expected):
            self.rgit("update-ref", "-d", "refs/heads/output", old)
            return real(git, remote, expected)

        with (
            patch.object(publisher, "_fetch", side_effect=race),
            patch.object(publisher, "_push") as push,
        ):
            code, out, err = self.publish(SECOND, old)
        self.assertEqual((code, out), (3, ""))
        self.assertIn("deleted during fetch", err)
        push.assert_not_called()
        self.assertIsNone(self.head())

    def test_fetch_failure_with_unconfirmed_head_is_not_a_conflict(self):
        old = self.seed(FIRST)
        real = publisher._fetch

        def race(git, remote, expected):
            self.remote.rename(self.root / "moved.git")
            return real(git, remote, expected)

        with (
            patch.object(publisher, "_fetch", side_effect=race),
            patch.object(publisher, "_push") as push,
        ):
            code, out, err = self.publish(SECOND, old)
        self.assertEqual((code, out), (1, ""))
        self.assertIn("fetch failed", err)
        push.assert_not_called()

    def test_git_error_text_redacts_the_token(self):
        token = "ghp_secretTokenValue123"
        with tempfile.TemporaryDirectory() as directory:
            repo = publisher._Git(directory, token)
            with self.assertRaises(ValueError) as raised:
                repo("cat-file", "-t", f"{token}^{{commit}}")
        message = str(raised.exception)
        self.assertNotIn(token, message)
        self.assertIn("***", message)

    def test_remote_rejection_is_a_failure_not_conflict(self):
        hook = self.remote / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\necho denied >&2\nexit 1\n")
        hook.chmod(0o755)
        code, out, err = self.publish(FIRST, "absent", "--bootstrap")
        self.assertEqual((code, out), (1, ""))
        self.assertIn("push failed", err)
        self.assertIsNone(self.head())

    def test_head_moved_inside_receive_is_a_conflict(self):
        old = self.seed(FIRST)
        other = self.seed(SECOND, parent=old, ref=None)
        hook = self.remote / "hooks" / "pre-receive"
        hook.write_text(
            "#!/bin/sh\ncat >/dev/null\nunset GIT_QUARANTINE_PATH\n"
            f"git update-ref refs/heads/output {other} {old}\n"
        )
        hook.chmod(0o755)
        code, out, err = self.publish(SECOND, old)
        self.assertEqual((code, out), (3, ""))
        self.assertIn("push was rejected", err)
        self.assertEqual(self.head(), other)

    def test_declined_update_with_unmoved_head_is_a_failure(self):
        old = self.seed(FIRST)
        hook = self.remote / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\ncat >/dev/null\necho denied >&2\nexit 1\n")
        hook.chmod(0o755)
        code, out, err = self.publish(SECOND, old)
        self.assertEqual((code, out), (1, ""))
        self.assertIn("push failed", err)
        self.assertEqual(self.head(), old)

    def test_readback_head_mismatch_is_explicit(self):
        other = self.seed(SECOND, ref=None)
        hook = self.remote / "hooks" / "post-receive"
        hook.write_text(f"#!/bin/sh\ngit update-ref refs/heads/output {other}\n")
        hook.chmod(0o755)
        code, out, err = self.publish(FIRST, "absent", "--bootstrap")
        self.assertEqual((code, out), (1, ""))
        self.assertRegex(err, r"Pushed [0-9a-f]{40} but the remote head reads")
        self.assertEqual(self.head(), other)

    def test_readback_hash_mismatch_is_explicit(self):
        def tampered(remote, token, commit):
            return commit, {**FIRST, STATE: FIRST[STATE] + b" "}

        with patch.object(publisher, "_read_back", side_effect=tampered):
            code, out, err = self.publish(FIRST, "absent", "--bootstrap")
        self.assertEqual((code, out), (1, ""))
        self.assertIn("remote file hashes differ", err)
        self.assertIsNotNone(self.head())

    def test_source_checkout_is_untouched(self):
        source = self.root / "source"
        source.mkdir()
        git("init", "--quiet", str(source))
        (source / "tracked.txt").write_text("one\n")
        git("-C", str(source), "add", "tracked.txt")
        git("-C", str(source), "commit", "--quiet", "--no-gpg-sign", "-m", "init")
        (source / "tracked.txt").write_text("dirty\n")
        (source / "staged.txt").write_text("staged\n")
        git("-C", str(source), "add", "staged.txt")
        (source / "untracked.txt").write_text("secret\n")
        before = {
            p: p.read_bytes()
            for p in (
                source / ".git" / "HEAD",
                source / ".git" / "index",
                source / ".git" / "config",
                source / "tracked.txt",
                source / "staged.txt",
                source / "untracked.txt",
            )
        }
        refs = git("-C", str(source), "show-ref")
        cwd = os.getcwd()
        os.chdir(source)
        try:
            with patch.dict(
                os.environ,
                {
                    "GIT_DIR": str(source / ".git"),
                    "GIT_INDEX_FILE": str(source / ".git" / "index"),
                },
            ):
                first = self.publish(
                    {**FIRST, "extra.txt": b"x"}, "absent", "--bootstrap"
                )
                parent = json.loads(first[1])["commit"]
                second = self.publish(SECOND, parent)
        finally:
            os.chdir(cwd)
        self.assertEqual((first[0], second[0]), (0, 0))
        self.assertEqual({p: p.read_bytes() for p in before}, before)
        self.assertEqual(git("-C", str(source), "show-ref"), refs)
        self.assertEqual(self.tree(self.head()), SECOND)

    def test_token_stays_out_of_argv_output_and_commits(self):
        token = "ghp_secretTokenValue123"
        calls = []
        real = subprocess.run

        def record(args, **kwargs):
            calls.append((args, kwargs.get("env") or {}))
            return real(args, **kwargs)

        with (
            patch.dict(os.environ, {"GH_TOKEN": token}),
            patch.object(publisher.subprocess, "run", side_effect=record),
        ):
            code, out, err = self.publish(FIRST, "absent", "--bootstrap")
        self.assertEqual(code, 0)
        self.assertTrue(calls)
        for args, env in calls:
            self.assertNotIn(token, " ".join(args))
            self.assertEqual(
                env.get("GIT_CONFIG_KEY_0"), "http.https://github.com/.extraheader"
            )
            self.assertNotIn(token, env.get("GIT_CONFIG_VALUE_0", ""))
        self.assertNotIn(token, out + err)
        objects = self.rgit("cat-file", "--batch-all-objects", "--batch")
        self.assertNotIn(token.encode(), objects)
        config = (self.remote / "config").read_bytes()
        self.assertNotIn(token.encode(), config)


if __name__ == "__main__":
    unittest.main()
