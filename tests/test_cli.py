import contextlib
import io
import unittest
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
