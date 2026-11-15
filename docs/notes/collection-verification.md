# Public Collection Verification

Date: 2026-11-15.
Scope: read-only public collection on `feat/collection-probe`; no growth state or output publication.

## Daily review source proof

Existing reviews by `hugovk` on [python/peps PR 5228](https://github.com/python/peps/pull/5228) provided the live example.
The PR node ID was `PR_kwDOAMyu2c8AAAABN8ICtQ`.
Separate `pullRequestReviewContributions` queries from each day's UTC midnight to the next midnight recovered:

| UTC day | Returned `occurredAt` for the PR |
| --- | --- |
| 2026-11-09 | 2026-11-09T20:45:58Z |
| 2026-11-12 | 2026-11-12T16:05:08Z |
| 2026-11-13 | 2026-11-13T18:04:24Z |

Each response had `hasNextPage: false`.
The 2026-11-09 through 2026-11-14 midnight query returned only the final review for this PR in the initial proof.
The PR's review records separately confirmed submissions on these three days.
This supports one contribution unit per PR per completed UTC day, rather than counting individual comments or all review submissions.

A boundary comparison showed that ending at the same day's `23:59:59Z` did not recover that day's contribution; for November 13 it instead returned the November 12 review.
Both the probe and collector therefore request midnight-to-midnight intervals and filter returned timestamps into the half-open interval.
This is observed API behavior, not a claim about its internal implementation.

## Local verification

All 29 offline tests, Ruff lint, formatting, and `git diff --check` passed locally.
The offline suite tests snapshot validation, public filtering, empty days, cursor pagination/loops, identity guards, duplicate removal, repeated reviews across days, UTC boundaries, partial responses, bounded retries, and response limits.
Ruff checks formatting and lint rules.
A live collection for `AndrewDongminYoo` over 2026-10-16 through 2026-11-15 exclusive completed in 44 HTTP requests: 93 eligible repositories, 30 complete days, 850 PR contributions, 234 issue contributions, and 0 review contributions.
Only these public aggregate results are recorded; raw responses and credentials are not stored.

## Local review

Reviewed the changed transport, normalization, schema, CLI, and CI paths for incomplete-data acceptance, private-data leakage, duplicate credit inputs, and unbounded requests.
The live endpoint mismatch was corrected in both collection commands and covered by query-boundary assertions.
No remote review or PR was requested, following the operator's local-review-only instruction.

## Remaining scope

Growth reconciliation, persistent state, SVG rendering, and publication are not implemented.
A snapshot cannot guarantee transactional consistency across all GitHub pages; conflicting repeated repository observations fail closed.
The four-minute budget can stop unusually large accounts without producing partial output.
