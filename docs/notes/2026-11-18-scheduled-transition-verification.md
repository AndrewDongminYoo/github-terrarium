# Scheduled Transition Verification

Date: 2026-11-18 run, recorded on 2026-11-19.
Scope: the first `schedule`-triggered run of the `Daily generation` workflow ([`generate.yml`](../../.github/workflows/generate.yml)) and the later-day transition it published, for [issue #27](https://github.com/AndrewDongminYoo/github-terrarium/issues/27).
Previous bundle: `output` at `caceb5d`, published by the manual bootstrap ([publication verification](2026-11-17-publication-verification.md)).

## Run

| Field | Value |
| --- | --- |
| Run | [44260620533](https://github.com/AndrewDongminYoo/github-terrarium/actions/runs/44260620533), attempt 1 |
| Event | `schedule` |
| Intended start | 2026-11-18T00:23Z (`23 0 * * *`) |
| Run created | 2026-11-18T07:39:43Z, 7 h 16 min after the cron time |
| `generate` job | `success`, 07:39:46Z to 07:40:41Z |
| Source | `main` at `3c048b7ca52effe8343bddd50d1ad747ebae66db` |
| `BOOTSTRAP` | `false` |

At 04:01Z no run existed yet, which [the first comment on #27](https://github.com/AndrewDongminYoo/github-terrarium/issues/27#issuecomment-6968641525) recorded and read as a dropped event; the run arrived later, and [the correction](https://github.com/AndrewDongminYoo/github-terrarium/issues/27#issuecomment-6995749774) records that.
The delay is consistent with GitHub's documented best-effort scheduling; one delayed start is not a measured delay distribution.

The result JSON in the log reported:

| Field | Value |
| --- | --- |
| outcome | `published` |
| commit | `b9274957deaf9c4e6772e95784a0ea7cca182237` |
| attempts | 1 |
| activity_interval | 2026-10-19 to 2026-11-18 |
| recovered_gap_days | 0 |
| stock_observation_day | 2026-11-18 |
| subject_id | `MDQ6VXNlcjgyOTk5NzE1` |
| xp_delta | 66 |
| state.json bytes | 12904 |
| terrarium.svg bytes | 103845 |

## Independent read of the remote output

A fresh single-branch clone of `output` showed `b927495` with the single parent `caceb5d`, so the history was extended, not rewritten.
Its author is `github-terrarium <github-terrarium@users.noreply.github.com>`, its subject is "Publish terrarium through 2026-11-17", and it holds exactly `manifest.json`, `state.json`, and `terrarium.svg`.
`python -m github_terrarium validate --bundle-dir <clone>` exited 0.

| Manifest field | `caceb5d` | `b927495` |
| --- | --- | --- |
| complete_activity_day | 2026-11-16 | 2026-11-17 |
| stock_observation_day | 2026-11-17 | 2026-11-18 |
| source_commit | `701ebb5` | `3c048b7` |
| manifest, schema, scoring, renderer versions | 1, 1, 1, 3 | 1, 1, 1, 3 |
| subject_id | `MDQ6VXNlcjgyOTk5NzE1` | `MDQ6VXNlcjgyOTk5NzE1` |

| File at `b927495` | `shasum -a 256` |
| --- | --- |
| `state.json` | `ad015a805a8b730338c5ce20cdde51973dbc00e7263d47e67b08fab8a14fa45f` |
| `terrarium.svg` | `b8e946e0b64d0f5f1e3ca9e7a78699676f3c21e42dbf76335baa8568e3c2d9c5` |
| `manifest.json` | `adf3c875fb580ecac61e9d091745c519b305a7e9a5afcd82862c19404bf30199` |

The `state.json` and `terrarium.svg` hashes equal the manifest values.
The SVG label changed from `Activity through 2026-11-16 UTC` to `Activity through 2026-11-17 UTC`, equal to the new `complete_activity_day`.

## Transition invariants

The two `state.json` files were compared day by day.

- Completed activity advanced by one day: `last_complete_activity_day` 2026-11-16 → 2026-11-17.
- Popularity stayed on the actual observation day: `last_popularity_observation_day` 2026-11-17 → 2026-11-18, the UTC date of the run.
- No day record was removed; one was added (2026-11-18, the observation day with no activity counts), for 31 → 32 records.
- Total awarded XP rose from 2028 to 2094; the difference, 66, equals `xp_delta`.
- Only one day's award changed: 2026-11-17 went from 0 XP and null activity counts to 66 XP, from 18 PRs and 2 issues (12 × 5 capped PRs + 3 × 2 issues).
- No award was lowered and no unit was awarded twice.
- One past day changed only its observed count: 2026-10-19 `prs` fell from 11 to 4 while its `activity_xp_awarded` stayed 75, as [`architecture.md`](../specs/architecture.md) requires when a corrected count falls.
- `recovery_target` stayed null; `current_traits` changed to `issues` 217 and `prs` 837 (from 216 and 839), with forks, reviews, and stars unchanged.

## Known gap: first window day

The 2026-10-19 drop is not a real correction.
Read-only probes showed that GitHub's `contributionsCollection` omits early contributions of the first day of the requested window, so the oldest day of every snapshot is undercounted.
The award invariants above still hold because awards never fall, but the bootstrap's first day (2026-10-18) is under-awarded by 6 XP and `current_traits` drifts down by each day's loss.
[Issue #57](https://github.com/AndrewDongminYoo/github-terrarium/issues/57) owns the probe outputs, the measured impact, and the proposed fix; the published counts for the first window day are therefore not complete.

## Not verified

- A distribution of scheduled start delays; only this one run is recorded.
- Image freshness of the README after this publication, which is [issue #29](https://github.com/AndrewDongminYoo/github-terrarium/issues/29).
- The contents of the hosted job summary page.
