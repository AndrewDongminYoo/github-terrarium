import io
import json
import unittest
import urllib.error

from github_terrarium.github import GitHubError, GraphQLClient


class TransportTests(unittest.TestCase):
    def client(self, payload):
        return GraphQLClient("test-token", opener=lambda *a, **k: io.BytesIO(payload))

    def test_accepts_data(self):
        self.assertEqual(
            self.client(b'{"data":{"user":null}}')("query", {}), {"user": None}
        )

    def test_rejects_partial_errors_without_echoing_response(self):
        secret = "DO-NOT-LOG-THIS"
        payload = json.dumps(
            {"data": {"user": {}}, "errors": [{"message": secret}]}
        ).encode()
        with self.assertRaises(GitHubError) as caught:
            self.client(payload)("query", {})
        self.assertNotIn(secret, str(caught.exception))

    def test_rejects_bad_json_missing_data_and_oversize(self):
        for payload in [
            b"[]",
            b"{}",
            b"not json",
            b"\xff",
            b"x" * (2 * 1024 * 1024 + 1),
        ]:
            with self.subTest(size=len(payload)), self.assertRaises(GitHubError):
                self.client(payload)("query", {})

    def test_timeout_and_http_error_are_sanitized(self):
        for error in [
            TimeoutError("secret"),
            urllib.error.HTTPError(
                "https://api.github.com/graphql", 403, "secret", {}, None
            ),
        ]:

            def fail(*args, **kwargs):
                raise error

            with self.assertRaises(GitHubError) as caught:
                GraphQLClient("test-token", opener=fail, sleep=lambda _: None)(
                    "query", {}
                )
            self.assertNotIn("secret", str(caught.exception))

    def test_fixed_https_endpoint_and_timeout(self):
        def opener(request, timeout):
            self.assertEqual(request.full_url, "https://api.github.com/graphql")
            self.assertEqual(timeout, 30)
            self.assertEqual(request.get_method(), "POST")
            return io.BytesIO(b'{"data":{}}')

        GraphQLClient("test-token", opener=opener)("query", {})

    def test_missing_or_invalid_token(self):
        for token in ["", "bad\ntoken", "bad token"]:
            with self.assertRaises(GitHubError):
                GraphQLClient(token)


class RetryTests(unittest.TestCase):
    def test_retryable_errors_then_success(self):
        for code, headers in [
            (429, {"Retry-After": "1"}),
            (503, {}),
            (403, {"X-RateLimit-Remaining": "0"}),
        ]:
            calls = []
            waits = []

            def opener(*args, **kwargs):
                calls.append(1)
                if len(calls) < 3:
                    raise urllib.error.HTTPError("url", code, "secret", headers, None)
                return io.BytesIO(b'{"data":{}}')

            self.assertEqual(
                GraphQLClient("token", opener=opener, sleep=waits.append)("q", {}), {}
            )
            self.assertEqual(len(waits), 2)

    def test_auth_long_wait_and_budget_fail_closed(self):
        for code, headers in [
            (401, {}),
            (403, {}),
            (429, {"Retry-After": "3600"}),
            (503, {}),
        ]:
            calls = []

            def opener(*args, **kwargs):
                calls.append(1)
                raise urllib.error.HTTPError("url", code, "secret", headers, None)

            with self.assertRaises(GitHubError):
                GraphQLClient(
                    "token", opener=opener, sleep=lambda _: None, max_requests=2
                )("q", {})
            self.assertEqual(len(calls), 2 if code == 503 else 1)

    def test_deadline_and_exhaustion(self):
        client = GraphQLClient(
            "token", opener=lambda *a, **k: self.fail("Unexpected request")
        )
        client.deadline = 0
        with self.assertRaisesRegex(GitHubError, "deadline"):
            client("q", {})
        calls = []

        def fail(*args, **kwargs):
            calls.append(1)
            raise TimeoutError("secret")

        with self.assertRaises(GitHubError):
            GraphQLClient("token", opener=fail, sleep=lambda _: None)("q", {})
        self.assertEqual(len(calls), 3)
