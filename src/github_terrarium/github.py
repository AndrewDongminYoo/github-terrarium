"""Bounded HTTPS GraphQL transport with sanitized failures."""

import json
import random
import time
import urllib.error
import urllib.request


class GitHubError(ValueError):
    """An API response cannot be trusted as collection evidence."""


class GraphQLClient:
    def __init__(
        self,
        token,
        opener=urllib.request.urlopen,
        *,
        sleep=time.sleep,
        max_requests=1000,
    ):
        if not token or any(char.isspace() for char in token):
            raise GitHubError("A valid GH_TOKEN or GITHUB_TOKEN is required")
        self.token = token
        self.opener = opener
        self.sleep = sleep
        self.max_requests = max_requests
        self.requests = 0
        self.deadline = time.monotonic() + 240

    def __call__(self, query, variables):
        request = urllib.request.Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": query, "variables": variables}).encode(),
            headers={
                "Authorization": "Bearer " + self.token,
                "Content-Type": "application/json",
                "User-Agent": "github-terrarium",
            },
            method="POST",
        )
        for attempt in range(3):
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise GitHubError("GitHub collection deadline exceeded")
            if self.requests >= self.max_requests:
                raise GitHubError("GitHub request budget exhausted")
            self.requests += 1
            delay = 2**attempt + random.random()
            try:
                with self.opener(request, timeout=min(30, remaining)) as response:
                    body = response.read(2 * 1024 * 1024 + 1)
                break
            except urllib.error.HTTPError as error:
                headers = error.headers or {}
                limited = error.code == 429 or (
                    error.code == 403
                    and (
                        headers.get("Retry-After") is not None
                        or headers.get("X-RateLimit-Remaining") == "0"
                    )
                )
                retryable = limited or 500 <= error.code < 600
                message = f"GitHub HTTP {error.code}; no data accepted"
                if limited:
                    try:
                        if headers.get("Retry-After") is not None:
                            delay = max(delay, float(headers["Retry-After"]))
                        elif headers.get("X-RateLimit-Reset") is not None:
                            delay = max(
                                delay, float(headers["X-RateLimit-Reset"]) - time.time()
                            )
                    except (TypeError, ValueError):
                        retryable = False
                error.close()
                if not retryable or attempt == 2 or not 0 <= delay <= 30:
                    raise GitHubError(message) from None
            except (urllib.error.URLError, TimeoutError, OSError):
                if attempt == 2:
                    raise GitHubError(
                        "GitHub transport failed; no data accepted"
                    ) from None
            if delay >= self.deadline - time.monotonic():
                raise GitHubError("GitHub collection deadline exceeded")
            self.sleep(delay)
        if len(body) > 2 * 1024 * 1024:
            raise GitHubError("GitHub response exceeds response budget")
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeError):
            raise GitHubError("GitHub returned invalid JSON") from None
        if not isinstance(payload, dict) or payload.get("errors"):
            raise GitHubError("GitHub GraphQL errors; no partial data accepted")
        if not isinstance(payload.get("data"), dict):
            raise GitHubError("GitHub response is missing data")
        return payload["data"]
