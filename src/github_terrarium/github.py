"""Bounded HTTPS GraphQL transport with sanitized failures."""

import json
import urllib.error
import urllib.request


class GitHubError(ValueError):
    """An API response cannot be trusted as collection evidence."""


class GraphQLClient:
    def __init__(self, token, opener=urllib.request.urlopen):
        if not token or any(char.isspace() for char in token):
            raise GitHubError("A valid GH_TOKEN or GITHUB_TOKEN is required")
        self.token = token
        self.opener = opener

    def __call__(self, query, variables):
        request = urllib.request.Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": query, "variables": variables}).encode(),
            headers={
                "Authorization": "Bearer " + self.token,
                "Content-Type": "application/json",
                "User-Agent": "github-terrarium-capability-probe",
            },
            method="POST",
        )
        try:
            with self.opener(request, timeout=30) as response:
                body = response.read(2 * 1024 * 1024 + 1)
        except urllib.error.HTTPError as error:
            raise GitHubError(f"GitHub HTTP {error.code}; no data accepted") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise GitHubError("GitHub transport failed; no data accepted") from None
        if len(body) > 2 * 1024 * 1024:
            raise GitHubError("GitHub response exceeds probe budget")
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeError):
            raise GitHubError("GitHub returned invalid JSON") from None
        if not isinstance(payload, dict) or payload.get("errors"):
            raise GitHubError("GitHub GraphQL errors; no partial data accepted")
        if not isinstance(payload.get("data"), dict):
            raise GitHubError("GitHub response is missing data")
        return payload["data"]
