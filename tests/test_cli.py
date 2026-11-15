import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from github_terrarium.__main__ import main


class CLITests(unittest.TestCase):
    def test_future_day_fails_before_network(self):
        with patch("github_terrarium.__main__.GraphQLClient") as client:
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["probe", "--day", "2999-01-01"]), 1)
            client.assert_not_called()

    def test_missing_configuration_is_actionable(self):
        stream = io.StringIO()
        with contextlib.redirect_stderr(stream):
            self.assertEqual(
                main(["probe", "--config", "/nonexistent/terrarium.toml"]), 1
            )
        self.assertIn("error:", stream.getvalue())

    def test_grow_offline_and_replay(self):
        from test_growth import snapshot

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "snapshot.json"
            prior = Path(directory) / "state.json"
            source.write_text(json.dumps(snapshot(prs=1)))
            with patch("github_terrarium.__main__.GraphQLClient") as client:
                first = io.StringIO()
                with contextlib.redirect_stdout(first):
                    self.assertEqual(
                        main(["grow", "--snapshot", str(source), "--bootstrap"]), 0
                    )
                prior.write_text(first.getvalue())
                second = io.StringIO()
                with contextlib.redirect_stdout(second):
                    self.assertEqual(
                        main(
                            ["grow", "--snapshot", str(source), "--state", str(prior)]
                        ),
                        0,
                    )
                self.assertEqual(first.getvalue(), second.getvalue())
                client.assert_not_called()
                original = prior.read_bytes()
                source.write_text('{"complete_snapshot":false}')
                output = io.StringIO()
                with (
                    contextlib.redirect_stdout(output),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    self.assertEqual(
                        main(
                            ["grow", "--snapshot", str(source), "--state", str(prior)]
                        ),
                        1,
                    )
                self.assertEqual(output.getvalue(), "")
                self.assertEqual(prior.read_bytes(), original)

    def test_unrepresentable_bootstrap_window_fails_cleanly(self):
        from datetime import date

        from test_growth import snapshot

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "snapshot.json"
            source.write_text(
                json.dumps(snapshot(end=date(1, 1, 2), start=date(1, 1, 1)))
            )
            error = io.StringIO()
            with contextlib.redirect_stderr(error):
                self.assertEqual(
                    main(["grow", "--snapshot", str(source), "--bootstrap"]), 1
                )
            self.assertIn("error:", error.getvalue())
            self.assertNotIn("Traceback", error.getvalue())
