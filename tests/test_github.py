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
                GraphQLClient("test-token", opener=fail)("query", {})
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
