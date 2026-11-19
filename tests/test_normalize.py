import contextlib
import copy
import io
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from github_terrarium.__main__ import main
from github_terrarium.config import Config
from github_terrarium.normalize import collect


def page(nodes=(), cursor=None):
    return {
        "nodes": list(nodes),
        "pageInfo": {"hasNextPage": cursor is not None, "endCursor": cursor},
    }


def event(day, item="PR1", visibility="PUBLIC", repository="R1", metric="prs"):
    value = {"isRestricted": False, "occurredAt": day + "T00:00:00Z"}
    repo = {"id": repository, "visibility": visibility}
    value["issue" if metric == "issues" else "pullRequest"] = {
        "id": item,
        "repository": repo,
    }
    value["repository"] = repo
    return value


def window_day(variables):
    """First day of the collector's window; requests start one day earlier."""
    return (date.fromisoformat(variables["from"][:10]) + timedelta(days=1)).isoformat()


class FixtureClient:
    def __init__(self):
        self.calls = []
        self.transform = lambda query, variables, user: user

    def __call__(self, query, variables):
        self.calls.append((query, variables))
        user = {"id": "U1", "login": "octocat"}
        if "repositories(first" in query:
            user["repositories"] = page(
                [
                    {
                        "id": "R1",
                        "visibility": "PUBLIC",
                        "isFork": False,
                        "stargazerCount": 3,
                        "forkCount": 1,
                    },
                    {
                        "id": "G",
                        "visibility": "PUBLIC",
                        "isFork": False,
                        "stargazerCount": 999,
                        "forkCount": 999,
                    },
                    {"id": "PRIVATE", "visibility": "PRIVATE"},
                    {"id": "FORK", "visibility": "PUBLIC", "isFork": True},
                ]
            )
        for field, metric in [
            ("pullRequestContributions", "prs"),
            ("issueContributions", "issues"),
            ("pullRequestReviewContributions", "reviews"),
        ]:
            if field in query:
                day = window_day(variables)
                nodes = [
                    event(day, metric=metric),
                    event(day, metric=metric),
                    event(day, visibility="PRIVATE", metric=metric),
                    event(day, repository="G", metric=metric),
                    {"isRestricted": True},
                ]
                user["contributionsCollection"] = {field: page(nodes)}
        return {
            "user": self.transform(query, variables, copy.deepcopy(user)),
            "repository": {"id": "G"},
        }


class CollectionTests(unittest.TestCase):
    def run_collect(self, client=None, **kwargs):
        return collect(
            Config("octocat", "owner/terrarium"),
            date(2026, 11, 13),
            date(2026, 11, 15),
            client or FixtureClient(),
            observed_on=date(2026, 11, 15),
            **kwargs,
        )

    def test_public_deduplication_and_daily_review_recovery(self):
        value = self.run_collect()
        self.assertEqual(value["repositories"], {"R1": {"stars": 3, "forks": 1}})
        self.assertEqual(
            value["days"],
            {
                "2026-11-13": {"prs": 1, "issues": 1, "reviews": 1},
                "2026-11-14": {"prs": 0, "issues": 0, "reviews": 1},
            },
        )
        self.assertNotIn("PRIVATE", str(value))

    def test_pagination_and_boundary(self):
        client = FixtureClient()

        def transform(query, variables, user):
            if "pullRequestContributions" in query:
                nodes = [event("2026-11-13", "A"), event("2026-11-15", "OPEN")]
                if variables["cursor"]:
                    nodes = [event("2026-11-14", "B"), event("2026-11-13", "A")]
                user["contributionsCollection"]["pullRequestContributions"] = page(
                    nodes, None if variables["cursor"] else "NEXT"
                )
            return user

        client.transform = transform
        value = self.run_collect(client)
        self.assertEqual([d["prs"] for d in value["days"].values()], [1, 1])
        self.assertTrue(any(v.get("cursor") == "NEXT" for _, v in client.calls))
        self.assertTrue(
            all(v["to"].endswith("T00:00:00Z") for _, v in client.calls if "to" in v)
        )

    def test_rejects_incomplete_cursor_and_identity_changes(self):
        for mode in ["cursor", "loop", "identity", "visibility", "null", "conflict"]:
            client = FixtureClient()

            def transform(query, variables, user):
                if "repositories(first" in query:
                    if mode == "identity":
                        user["id"] = "OTHER"
                    elif mode == "visibility":
                        del user["repositories"]["nodes"][0]["visibility"]
                    elif mode == "null":
                        user["repositories"]["nodes"].append(None)
                    elif mode == "conflict":
                        node = dict(
                            user["repositories"]["nodes"][0], stargazerCount=100
                        )
                        user["repositories"]["nodes"].append(node)
                    else:
                        user["repositories"]["pageInfo"] = {
                            "hasNextPage": True,
                            "endCursor": None if mode == "cursor" else "SAME",
                        }
                return user

            client.transform = transform
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.run_collect(client)

    def test_identity_guard_and_open_day(self):
        with self.assertRaises(ValueError):
            self.run_collect(expected_subject="WRONG")
        with self.assertRaises(ValueError):
            collect(
                Config("octocat", "owner/terrarium"),
                date(2026, 11, 14),
                date(2026, 11, 16),
                FixtureClient(),
                observed_on=date(2026, 11, 15),
            )

    def test_window_size_and_empty_days(self):
        client = FixtureClient()

        def transform(query, variables, user):
            for value in user.get("contributionsCollection", {}).values():
                value["nodes"] = []
            return user

        client.transform = transform
        value = collect(
            Config("octocat", "owner/terrarium"),
            date(2026, 9, 1),
            date(2026, 11, 15),
            client,
            observed_on=date(2026, 11, 15),
        )
        self.assertEqual(len(value["days"]), 75)
        self.assertTrue(all(not any(day.values()) for day in value["days"].values()))
        windows = {}
        for query, variables in client.calls:
            if "from" in variables:
                start = date.fromisoformat(window_day(variables))
                end = date.fromisoformat(variables["to"][:10])
                self.assertTrue(variables["from"].endswith("T00:00:00Z"))
                self.assertLessEqual((end - start).days, 30)
                field = next(
                    name
                    for name in (
                        "pullRequestReviewContributions",
                        "pullRequestContributions",
                        "issueContributions",
                    )
                    if name in query
                )
                windows.setdefault(field, []).append((start, end))
        self.assertEqual(len(windows), 3)
        for spans in windows.values():
            spans.sort()
            self.assertEqual(spans[0][0], date(2026, 9, 1))
            self.assertEqual(spans[-1][1], date(2026, 11, 15))
            for (_, previous_end), (next_start, _) in zip(spans, spans[1:]):
                self.assertEqual(previous_end, next_start)

    def test_review_and_repository_pagination(self):
        client = FixtureClient()

        def transform(query, variables, user):
            if "repositories(first" in query:
                if variables["cursor"]:
                    user["repositories"] = page(
                        [
                            {
                                "id": "R2",
                                "visibility": "PUBLIC",
                                "isFork": False,
                                "stargazerCount": 0,
                                "forkCount": 0,
                            }
                        ]
                    )
                else:
                    user["repositories"]["pageInfo"] = {
                        "hasNextPage": True,
                        "endCursor": "NEXT",
                    }
            if "pullRequestReviewContributions" in query:
                day = window_day(variables)
                user["contributionsCollection"]["pullRequestReviewContributions"] = (
                    page(
                        [
                            event(
                                day,
                                "B" if variables["cursor"] else "A",
                                metric="reviews",
                            )
                        ],
                        None if variables["cursor"] else "NEXT",
                    )
                )
            return user

        client.transform = transform
        result = self.run_collect(client)
        self.assertEqual(set(result["repositories"]), {"R1", "R2"})
        self.assertEqual([d["reviews"] for d in result["days"].values()], [2, 2])

    def test_first_window_day_is_complete_when_the_api_drops_its_early_hours(self):
        # GitHub's contributionsCollection omitted early contributions of the
        # requested first day without an error (issue #57); model that here.
        client = FixtureClient()

        def transform(query, variables, user):
            if "pullRequestContributions" in query:
                start = datetime.fromisoformat(variables["from"].replace("Z", "+00:00"))
                nodes = []
                for item, stamp in [
                    ("BEFORE", "2026-11-12T23:00:00Z"),
                    ("EARLY", "2026-11-13T01:00:00Z"),
                    ("LATE", "2026-11-13T08:00:00Z"),
                ]:
                    node = event("2026-11-13", item)
                    node["occurredAt"] = stamp
                    occurred = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                    if occurred >= start + timedelta(hours=7):
                        nodes.append(node)
                user["contributionsCollection"]["pullRequestContributions"] = page(
                    nodes
                )
            return user

        client.transform = transform
        value = self.run_collect(client)
        self.assertEqual(value["days"]["2026-11-13"]["prs"], 2)
        self.assertEqual(sorted(value["days"]), ["2026-11-13", "2026-11-14"])

    def test_timestamp_timezone_and_sanitized_failure(self):
        for timestamp in ["2026-11-14T01:00:00+02:00", "SECRET-INVALID-DATE"]:
            client = FixtureClient()

            def transform(query, variables, user):
                if "pullRequestContributions" in query:
                    node = event("2026-11-13")
                    node["occurredAt"] = timestamp
                    user["contributionsCollection"]["pullRequestContributions"] = page(
                        [node]
                    )
                return user

            client.transform = transform
            if timestamp.startswith("SECRET"):
                with self.assertRaises(ValueError) as caught:
                    self.run_collect(client)
                self.assertNotIn(timestamp, str(caught.exception))
            else:
                result = self.run_collect(client)
                self.assertEqual(result["days"]["2026-11-13"]["prs"], 1)

    def test_collection_crossing_utc_midnight_returns_no_snapshot(self):
        days = iter([date(2026, 11, 15), date(2026, 11, 16)])
        client = FixtureClient()
        with self.assertRaisesRegex(ValueError, "UTC date changed.*rerun"):
            collect(
                Config("octocat", "owner/terrarium"),
                date(2026, 11, 13),
                date(2026, 11, 15),
                client,
                clock=lambda: next(days),
            )
        self.assertTrue(client.calls)

    def test_guarded_collection_on_one_utc_day_returns_a_snapshot(self):
        reads = []

        def clock():
            reads.append(None)
            return date(2026, 11, 15)

        value = collect(
            Config("octocat", "owner/terrarium"),
            date(2026, 11, 13),
            date(2026, 11, 15),
            FixtureClient(),
            clock=clock,
        )
        self.assertEqual(value["observed_on"], "2026-11-15")
        self.assertGreaterEqual(len(reads), 2)

    def test_explicit_observation_day_leaves_the_check_to_the_caller(self):
        value = self.run_collect(clock=lambda: date(2026, 11, 16))
        self.assertEqual(value["observed_on"], "2026-11-15")

    def test_cli_collection_crossing_utc_midnight_prints_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "terrarium.toml"
            config.write_text('login = "octocat"\n')
            before = sorted(Path(directory).iterdir())
            output, error = io.StringIO(), io.StringIO()
            with (
                patch(
                    "github_terrarium.__main__.GraphQLClient",
                    return_value=FixtureClient(),
                ),
                patch(
                    "github_terrarium.normalize.today",
                    side_effect=[date(2026, 11, 15), date(2026, 11, 16)],
                ),
                contextlib.redirect_stdout(output),
                contextlib.redirect_stderr(error),
            ):
                code = main(
                    [
                        "collect",
                        "--config",
                        str(config),
                        "--repository",
                        "owner/terrarium",
                        "--start",
                        "2026-11-13",
                        "--end",
                        "2026-11-15",
                    ]
                )
            self.assertEqual(code, 1)
            self.assertEqual(output.getvalue(), "")
            self.assertIn("UTC date changed during collection", error.getvalue())
            self.assertEqual(sorted(Path(directory).iterdir()), before)
