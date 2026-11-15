import tempfile
import unittest
from pathlib import Path

from github_terrarium.config import load_config


class ConfigTests(unittest.TestCase):
    def load(self, content, repository="owner/terrarium"):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "config.toml"
            file.write_text(content)
            return load_config(file, repository)

    def test_valid(self):
        result = self.load('login = "octocat"')
        self.assertEqual(result.login, "octocat")
        self.assertEqual(result.repository, "owner/terrarium")

    def test_rejects_unsafe_or_ambiguous_configuration(self):
        for content in [
            'login = "../bad"',
            'login = "a--b"',
            "login = 1",
            'login = "ok"\nprivate = true',
            "",
        ]:
            with self.subTest(content=content), self.assertRaises(ValueError):
                self.load(content)

    def test_requires_explicit_repository(self):
        for repo in ["", "owner", "owner/repo/extra", "https://github.com/a/b"]:
            with self.subTest(repo=repo), self.assertRaises(ValueError):
                self.load('login = "ok"', repo)
