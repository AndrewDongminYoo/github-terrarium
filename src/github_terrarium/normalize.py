"""Complete public collection, with deterministic UTC-day normalization."""

from datetime import UTC, datetime, timedelta

from .models import count, day_range, identifier, validate_snapshot
from .probe import connection, public_repository

IDENTITY = """query($login:String!, $owner:String!, $name:String!) {
  repository(owner:$owner,name:$name){id}
  user(login:$login){id login}
}"""
REPOSITORIES = """query($login:String!, $cursor:String) {
  user(login:$login){id login
    repositories(first:100,after:$cursor,ownerAffiliations:[OWNER],privacy:PUBLIC,isFork:false){
      nodes{id visibility isFork stargazerCount forkCount}
      pageInfo{hasNextPage endCursor}
    }
  }
}"""
# contributionsCollection silently omits early contributions of the first
# requested day (issue #57), so each request starts one day before its window
# and nodes outside the window are discarded by their own UTC day.
REQUEST_PAD = timedelta(days=1)
FIELDS = {
    "prs": ("pullRequestContributions", "pullRequest"),
    "issues": ("issueContributions", "issue"),
    "reviews": ("pullRequestReviewContributions", "pullRequest"),
}


def activity_query(metric):
    field, entity = FIELDS[metric]
    details = (
        "pullRequest{id} repository{id visibility}"
        if metric == "reviews"
        else entity + "{id repository{id visibility}}"
    )
    return """query($login:String!, $cursor:String, $from:DateTime!, $to:DateTime!){
      user(login:$login){id login contributionsCollection(from:$from,to:$to){
        %s(first:100,after:$cursor){nodes{isRestricted occurredAt %s}
          pageInfo{hasNextPage endCursor}}
      }}
    }""" % (field, details)


def today():
    return datetime.now(UTC).date()


def collect(
    config,
    start,
    end,
    client,
    *,
    observed_on=None,
    expected_subject=None,
    clock=None,
):
    """Read at most 90 completed days; only return after every page succeeds.

    Without an explicit `observed_on`, stock is observed on the clock's UTC date,
    and a collection that ends on a later UTC date fails so that stock read
    after midnight is never filed under the earlier day. A caller that passes
    `observed_on` owns that check.
    """
    clock = clock or today
    guard = observed_on is None
    observed_on = observed_on or clock()
    if not 0 < (end - start).days <= 90 or end > observed_on:
        raise ValueError("Collect requires 1–90 completed UTC days")
    owner, name = config.repository.split("/")
    try:
        data = client(IDENTITY, {"login": config.login, "owner": owner, "name": name})
        subject = data["user"]
        subject_id = identifier(subject["id"])
        excluded = identifier(data["repository"]["id"])
        if subject["login"].lower() != config.login.lower() or (
            expected_subject is not None and expected_subject != subject_id
        ):
            raise ValueError("Subject identity mismatch")

        def pages(query, variables, field, activity=False):
            cursor = None
            seen = set()
            for _ in range(100):
                user = client(
                    query, {"login": config.login, "cursor": cursor, **variables}
                )["user"]
                if user["id"] != subject_id or user["login"] != subject["login"]:
                    raise ValueError("Subject changed during collection")
                value = (
                    user["contributionsCollection"][field] if activity else user[field]
                )
                nodes, more = connection(value)
                if len(nodes) > 100 or (more and not nodes):
                    raise ValueError("Incomplete connection page")
                yield from nodes
                if not more:
                    return
                cursor = value["pageInfo"]["endCursor"]
                if not isinstance(cursor, str) or not cursor or cursor in seen:
                    raise ValueError("Missing or repeated pagination cursor")
                seen.add(cursor)
            raise ValueError("Connection page budget exhausted")

        repositories = {}
        for repo in pages(REPOSITORIES, {}, "repositories"):
            if not public_repository(repo, excluded):
                continue
            if type(repo["isFork"]) is not bool:
                raise ValueError("Missing fork status")
            if repo["isFork"]:
                continue
            key = identifier(repo["id"])
            stock = {
                "stars": count(repo["stargazerCount"]),
                "forks": count(repo["forkCount"]),
            }
            if key in repositories and repositories[key] != stock:
                raise ValueError("Conflicting repository observations")
            repositories[key] = stock

        days = {day: {metric: 0 for metric in FIELDS} for day in day_range(start, end)}
        for metric, (field, entity) in FIELDS.items():
            seen = set()
            window_start = start
            while window_start < end:
                window_end = min(
                    end, window_start + timedelta(days=1 if metric == "reviews" else 30)
                )
                variables = {
                    "from": (window_start - REQUEST_PAD).isoformat() + "T00:00:00Z",
                    "to": window_end.isoformat() + "T00:00:00Z",
                }
                for node in pages(
                    activity_query(metric), variables, field, activity=True
                ):
                    if type(node["isRestricted"]) is not bool:
                        raise ValueError("Missing restricted visibility")
                    if node["isRestricted"]:
                        continue
                    item = node[entity]
                    repo = (
                        node["repository"]
                        if metric == "reviews"
                        else item["repository"]
                    )
                    if not public_repository(repo, excluded):
                        continue
                    item_id = identifier(item["id"])
                    try:
                        occurred = datetime.fromisoformat(
                            node["occurredAt"].replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError, AttributeError):
                        raise ValueError("Invalid contribution timestamp") from None
                    if occurred.tzinfo is None:
                        raise ValueError("Contribution timestamp lacks timezone")
                    day = occurred.astimezone(UTC).date()
                    if not window_start <= day < window_end:
                        continue
                    key = (item_id, day) if metric == "reviews" else item_id
                    if key not in seen:
                        days[day.isoformat()][metric] += 1
                        seen.add(key)
                window_start = window_end
        snapshot = validate_snapshot(
            {
                "schema_version": 1,
                "complete_snapshot": True,
                "subject": {"id": subject_id, "login": subject["login"]},
                "activity_start": start.isoformat(),
                "activity_end": end.isoformat(),
                "observed_on": observed_on.isoformat(),
                "repositories": repositories,
                "days": days,
            }
        )
    except (KeyError, TypeError, AttributeError):
        raise ValueError("Collection response is missing required fields") from None
    if guard and clock() != observed_on:
        raise ValueError("UTC date changed during collection; no snapshot, rerun")
    return snapshot
