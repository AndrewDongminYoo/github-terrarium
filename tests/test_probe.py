import copy
import unittest
from datetime import date

from github_terrarium.config import Config
from github_terrarium.probe import probe


def connection(nodes=None):
    return {"nodes": nodes or [], "pageInfo": {"hasNextPage": False}}


def response():
    return {
        "user": {
            "id": "U1",
            "login": "octocat",
            "repositories": connection(),
            "contributionsCollection": {
                name: connection()
                for name in (
                    "pullRequestContributions",
                    "issueContributions",
                    "pullRequestReviewContributions",
                )
            },
        },
        "repository": {"id": "GENERATOR"},
    }


class ProbeTests(unittest.TestCase):
    def run_probe(self, payload):
        return probe(
            Config("octocat", "owner/terrarium"),
            date(2026, 11, 14),
            lambda query, variables: copy.deepcopy(payload),
        )

    def test_empty_is_sample_not_complete_snapshot(self):
        summary = self.run_probe(response())
        self.assertFalse(summary["complete_snapshot"])
        self.assertEqual(summary["subject_id"], "U1")
        self.assertEqual(summary["samples"]["prs"], 0)

    def test_excludes_private_and_generator(self):
        payload = response()
        nodes = [
            {"isRestricted": True},
            {
                "isRestricted": False,
                "occurredAt": "2026-11-14T10:00:00Z",
                "pullRequest": {
                    "id": "PR1",
                    "repository": {"id": "PRIVATE", "visibility": "PRIVATE"},
                },
            },
            {
                "isRestricted": False,
                "occurredAt": "2026-11-14T10:00:00Z",
                "pullRequest": {
                    "id": "PR2",
                    "repository": {"id": "GENERATOR", "visibility": "PUBLIC"},
                },
            },
        ]
        payload["user"]["contributionsCollection"]["pullRequestContributions"] = (
            connection(nodes)
        )
        self.assertEqual(self.run_probe(payload)["samples"]["prs"], 0)

    def test_rejects_missing_visibility(self):
        payload = response()
        payload["user"]["contributionsCollection"]["issueContributions"] = connection(
            [
                {
                    "isRestricted": False,
                    "occurredAt": "2026-11-14T00:00:00Z",
                    "issue": {"id": "I1", "repository": {"id": "R1"}},
                }
            ]
        )
        with self.assertRaises(ValueError):
            self.run_probe(payload)

    def test_reports_truncation_honestly(self):
        payload = response()
        payload["user"]["repositories"]["pageInfo"]["hasNextPage"] = True
        self.assertIn("repositories", self.run_probe(payload)["truncated_connections"])

    def test_query_uses_closed_utc_day(self):
        def client(query, variables):
            self.assertEqual(variables["from"], "2026-11-14T00:00:00Z")
            self.assertEqual(variables["to"], "2026-11-14T23:59:59Z")
            return response()

        probe(Config("octocat", "owner/terrarium"), date(2026, 11, 14), client)
