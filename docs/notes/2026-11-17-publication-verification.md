# Publication Verification

Date: 2026-11-17.
Scope: the first manual publication and a same-day replay through the `Daily generation` workflow ([`generate.yml`](../../.github/workflows/generate.yml)) in `AndrewDongminYoo/github-terrarium`, plus a controlled failure in a disposable repository, for [issue #26](https://github.com/AndrewDongminYoo/github-terrarium/issues/26).
Source: `main` at `701ebb5c754bc28b3936a2b299472d2ab14e9a35`.
Token: only the repository `GITHUB_TOKEN`; no personal token or repository secret was configured.

## Precondition

The remote `output` branch was absent before the bootstrap.
An earlier `output` ref without a bundle, created 2026-11-17T05:55:07Z at `b1f55e6`, was deleted with approval before PR #49 merged.

## Bootstrap run

[Run 44037011074](https://github.com/AndrewDongminYoo/github-terrarium/actions/runs/44037011074) was a `workflow_dispatch` on `main` with `bootstrap=true`, dispatched at 07:13:18Z.
The `generate` job succeeded from 07:13:22Z to 07:14:21Z.
The result JSON in the log reported:

| Field | Value |
| --- | --- |
| outcome | `published` |
| commit | `caceb5d10d115539e99fa6abb6a60f1c621412b4` |
| attempts | 1 |
| activity_interval | 2026-10-18 to 2026-11-17 |
| recovered_gap_days | 0 |
| stock_observation_day | 2026-11-17 |
| subject_id | `MDQ6VXNlcjgyOTk5NzE1` |
| xp_delta | 2028 (no previous state) |
| state.json bytes | 12702 |
| terrarium.svg bytes | 103845 |

## Independent read of the remote output

A fresh clone of the remote `output` branch showed one root commit, `caceb5d`, with no parent.
Its author is `github-terrarium <github-terrarium@users.noreply.github.com>` and its subject is "Publish terrarium through 2026-11-16".
That one commit contains exactly three files: `manifest.json`, `state.json`, and `terrarium.svg`.
`python -m github_terrarium validate --bundle-dir <clone>` exited 0.

| Manifest field | Value |
| --- | --- |
| manifest_version | 1 |
| schema_version | 1 |
| scoring_version | 1 |
| renderer_version | 3 |
| complete_activity_day | 2026-11-16 |
| stock_observation_day | 2026-11-17 |
| source_commit | `701ebb5c754bc28b3936a2b299472d2ab14e9a35` |
| subject_id | `MDQ6VXNlcjgyOTk5NzE1` |

| File | `shasum -a 256` |
| --- | --- |
| `state.json` | `4b8380cc8bd530fe4f0a8ad9f8fb51e76618b2dcef8faa36d32d16caa4500a60` |
| `terrarium.svg` | `2b8dfd63dc6564a8afd69dfa0ea3573cd55ec1e2ce9c58ec21ce0a9b2cf5b2d9` |
| `manifest.json` | `9ff9bd3b11c041cbb3cf87e7d0549f06f126014a921f02b19365b3bd9b234280` |

The `state.json` and `terrarium.svg` hashes equal the values in the manifest.
`gh api users/AndrewDongminYoo` returned the node ID `MDQ6VXNlcjgyOTk5NzE1`, so the subject is the intended user.
`state.json` records `last_complete_activity_day` 2026-11-16, `last_popularity_observation_day` 2026-11-17, `recovery_target` null, and 31 day records.

## Same-day replay

[Run 44037271802](https://github.com/AndrewDongminYoo/github-terrarium/actions/runs/44037271802) was dispatched with `bootstrap=false` at 07:15:18Z and succeeded from 07:15:21Z to 07:16:14Z.
It reported outcome `no-change`, commit `caceb5d10d115539e99fa6abb6a60f1c621412b4`, xp_delta 0, and the same byte sizes and activity interval.
The remote `output` head stayed at `caceb5d`: no extra commit was pushed and no growth was awarded twice.

## Workflow guards

- No regeneration loop: after the bootstrap pushed `output`, the only new run listed was the bootstrap run itself; `generate.yml` has no push trigger.
- Non-default dispatch: [run 44037557840](https://github.com/AndrewDongminYoo/github-terrarium/actions/runs/44037557840) was dispatched with `bootstrap=true` from the temporary branch `dispatch-guard-probe` at `701ebb5` at 07:17:30Z. The run concluded `skipped`, the `generate` job ran 0 steps (no checkout), and the remote `output` stayed at `caceb5d`. The temporary branch was deleted afterwards.
- Log hygiene: the only token-like line in the bootstrap log is the masked credential configuration of `actions/checkout`; the generate step printed only the result JSON.

## Safe failure preservation

The disposable private repository `AndrewDongminYoo/terrarium-failure-probe` was created on 2026-11-17 for this check and is kept.
The workflow guard pins the production repository name, so the workflow cannot run there; the same source `701ebb5` ran locally through the CLI with the local `gh` login token instead.

1. A valid bootstrap with `login = "AndrewDongminYoo"` and `--bootstrap` exited 0 with outcome `published`, commit `2a9451b68e272e2f46e81dc8cf271bc861a8f398`, xp_delta 2034, and a 12766-byte `state.json`.
   These values differ from production (2028 and 12702) because collection excludes only the configured target repository (`collect` in `normalize.py` sets `excluded` from `data["repository"]["id"]`), so this run also counted activity in `github-terrarium`.
   This is an expected real-data difference, not a defect.
2. An update with the nonexistent login `terrarium-no-such-login-2026` (`gh api users/terrarium-no-such-login-2026` returns 404) and no `--bootstrap` exited 1 with empty stdout and the stderr line `error: GitHub GraphQL errors; no partial data accepted`.
   It wrote a failure summary with outcome `failure` and exit code 1.
   The remote `output` head was `2a9451b68e272e2f46e81dc8cf271bc861a8f398` before and after the run.

## Not verified

- A scheduled (cron) run.
- A later-day transition, which milestone 6 requires before daily growth is claimed.
- The contents of the hosted job summary pages for the production runs.
