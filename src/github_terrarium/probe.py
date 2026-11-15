"""Read one page per connection to establish capabilities, not totals."""

from datetime import UTC, datetime, time, timedelta

QUERY = """
query($login:String!, $owner:String!, $name:String!, $from:DateTime!, $to:DateTime!) {
  repository(owner:$owner, name:$name) { id }
  user(login:$login) {
    id login
    repositories(first:100, ownerAffiliations:[OWNER], privacy:PUBLIC, isFork:false) {
      nodes { id visibility isFork stargazerCount forkCount }
      pageInfo { hasNextPage }
    }
    contributionsCollection(from:$from, to:$to) {
      pullRequestContributions(first:100) {
        nodes { isRestricted occurredAt
          pullRequest { id repository { id visibility } } }
        pageInfo { hasNextPage }
      }
      issueContributions(first:100) {
        nodes { isRestricted occurredAt issue { id repository { id visibility } } }
        pageInfo { hasNextPage }
      }
      pullRequestReviewContributions(first:100) {
        nodes { isRestricted occurredAt
          pullRequest { id } repository { id visibility } }
        pageInfo { hasNextPage }
      }
    }
  }
}
"""


def connection(value):
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("nodes"), list)
        or not isinstance(value.get("pageInfo"), dict)
        or type(value["pageInfo"].get("hasNextPage")) is not bool
    ):
        raise ValueError("Incomplete GitHub connection")
    return value["nodes"], value["pageInfo"]["hasNextPage"]


def public_repository(value, excluded):
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("id"), str)
        or value.get("visibility") not in {"PUBLIC", "PRIVATE", "INTERNAL"}
    ):
        raise ValueError("Repository visibility or identity missing")
    return value["visibility"] == "PUBLIC" and value["id"] != excluded


def probe(config, day, client):
    start = datetime.combine(day, time(), tzinfo=UTC)
    end = start + timedelta(days=1)
    owner, name = config.repository.split("/")
    data = client(
        QUERY,
        {
            "login": config.login,
            "owner": owner,
            "name": name,
            "from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )
    try:
        user = data["user"]
        excluded = data["repository"]["id"]
        if (
            not isinstance(user["id"], str)
            or not isinstance(excluded, str)
            or user["login"].lower() != config.login.lower()
        ):
            raise ValueError("Subject identity mismatch")
        samples = {}
        truncated = []
        repos, more = connection(user["repositories"])
        if more:
            truncated.append("repositories")
        samples["repositories"] = 0
        for repo in repos:
            if public_repository(repo, excluded):
                if type(repo.get("isFork")) is not bool or any(
                    type(repo.get(key)) is not int or repo[key] < 0
                    for key in ("stargazerCount", "forkCount")
                ):
                    raise ValueError("Invalid repository counters")
                if not repo["isFork"]:
                    samples["repositories"] += 1
        fields = [
            ("prs", "pullRequestContributions", "pullRequest"),
            ("issues", "issueContributions", "issue"),
            ("reviews", "pullRequestReviewContributions", "pullRequest"),
        ]
        for metric, field, entity in fields:
            nodes, more = connection(user["contributionsCollection"][field])
            if more:
                truncated.append(metric)
            ids = set()
            for node in nodes:
                if type(node.get("isRestricted")) is not bool:
                    raise ValueError("Missing restricted visibility")
                if node["isRestricted"]:
                    continue
                item = node[entity]
                repo = node["repository"] if metric == "reviews" else item["repository"]
                if not public_repository(repo, excluded):
                    continue
                occurred = datetime.fromisoformat(
                    node["occurredAt"].replace("Z", "+00:00")
                )
                if occurred.tzinfo is None or not isinstance(item["id"], str):
                    raise ValueError("Invalid contribution timestamp or identity")
                if start <= occurred < end:
                    ids.add(item["id"])
            samples[metric] = len(ids)
        return {
            "schema_version": 1,
            "kind": "capability_probe",
            "complete_snapshot": False,
            "subject_id": user["id"],
            "login": user["login"],
            "activity_day": day.isoformat(),
            "samples": samples,
            "truncated_connections": sorted(truncated),
            "daily_review_recovery": "not_verified",
        }
    except (KeyError, TypeError, AttributeError):
        raise ValueError("GitHub probe response is missing required fields") from None
