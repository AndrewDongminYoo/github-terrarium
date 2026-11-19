# Acceptance Evidence

Date: 2026-11-19.
Scope: the evidence for each acceptance criterion in the [product specification](../specs/terrarium.md#acceptance-criteria), for [issue #30](https://github.com/AndrewDongminYoo/github-terrarium/issues/30).
Source: `main` at `9c449c7`; live output: `output` at `cee9c44`.
Each row names the tests, notes, and live runs that show the result, and states what was not shown.
Limitations marked **accepted** were accepted on 2026-11-19 as known gaps of this release.

## Live record

| Event | Run | Output | Note |
| --- | --- | --- | --- |
| Manual bootstrap, 2026-11-17 | [44037011074](https://github.com/AndrewDongminYoo/github-terrarium/actions/runs/44037011074) | `caceb5d` | [publication verification](2026-11-17-publication-verification.md) |
| Same-day replay, `no-change` | [44037271802](https://github.com/AndrewDongminYoo/github-terrarium/actions/runs/44037271802) | `caceb5d` | [publication verification](2026-11-17-publication-verification.md) |
| First scheduled run, 7 h 16 min late | [44260620533](https://github.com/AndrewDongminYoo/github-terrarium/actions/runs/44260620533) | `b927495` | [scheduled transition verification](2026-11-18-scheduled-transition-verification.md) |
| Second scheduled run, 7 h 13 min late | [44480853117](https://github.com/AndrewDongminYoo/github-terrarium/actions/runs/44480853117) | `cee9c44` | [README freshness verification](2026-11-19-readme-freshness-verification.md) |

The second scheduled run used `main` at `12333c7`, which includes the first-window-day fix ([#57](https://github.com/AndrewDongminYoo/github-terrarium/issues/57), PR [#59](https://github.com/AndrewDongminYoo/github-terrarium/pull/59)).
Its state comparison against `b927495`: total awarded XP rose from 2094 to 2154, equal to its `xp_delta` 60; only the open 2026-11-18 record changed its award; no record was removed; and the first day of its window, 2026-10-20, kept its counts, where the previous run had lowered its first day, 2026-10-19, from 11 PRs to 4.

## Criteria

| AC | Evidence | Status |
| --- | --- | --- |
| AC-01 distinct, legible habitats for the five fixtures | `test_render.py` `test_personas_are_distinct_and_bounded_self_contained_svg`; the [fixture gallery](fixture-gallery-verification.md); visual approval of renderer version 3 in [#13](https://github.com/AndrewDongminYoo/github-terrarium/issues/13#issuecomment-6919598552) | Evidenced; legibility is a reviewed judgement, not an automated contrast measurement. |
| AC-02 identical replay bytes, no extra growth | `test_growth.py` `test_bootstrap_and_byte_identical_replay`, `test_bundle.py` `test_build_is_deterministic`, `test_generate.py` `test_identical_rerun_is_no_change`; live same-day replay (`no-change`, `xp_delta` 0) | Evidenced. |
| AC-03 daily caps and no double popularity | `test_growth.py` `test_same_day_caps_and_stock_drop_recovery` and `test_activity_caps_apply_to_day_across_runs`; frozen scoring version 1 ([#20](https://github.com/AndrewDongminYoo/github-terrarium/issues/20#issuecomment-6932925175)) | Evidenced. |
| AC-04 missed days and late observations without duplicate awards | `test_growth.py` `test_activity_corrections_never_reduce_or_duplicate_awards`, `test_next_day_and_missed_days_preserve_continuity`, `test_old_corrections_require_explicit_recovery`; `test_generate.py` `test_different_day_advance_and_recovered_gap`; `test_normalize.py` `test_first_window_day_is_complete_when_the_api_drops_its_early_hours`; two live later-day transitions with XP equal to `xp_delta` | Evidenced. **Accepted limitation:** records stored before the #57 fix keep their values: 2026-10-18 is under-awarded by 6 XP (13 PRs and 1 issue stored, 23 and 3 collected now), and 2026-10-19 keeps an observed count of 4 PRs (11 collected now). Correcting them is a deliberate maintenance operation under [`architecture.md`](../specs/architecture.md); no live run has recovered a missed day yet. |
| AC-05 public-only data even with a privileged credential | `test_normalize.py` `test_public_deduplication_and_daily_review_recovery` and `test_probe.py` `test_excludes_private_and_generator` with private, restricted, and generator fixtures; the live check below | Evidenced for the generator repository and private repositories. **Accepted limitation:** the live window contained no private or restricted contribution node, so that branch of the filter is shown only by the fixture tests. |
| AC-06 prior bundle intact after a partial API result, invalid state, invalid SVG, or rejected push | `test_github.py` `test_rejects_partial_errors_without_echoing_response`; `test_generate.py` `test_corrupt_or_missing_remote_bundle_never_bootstraps`; `test_bundle.py` `test_unsafe_svg_is_rejected_after_hash_check`; `test_publish.py` `test_invalid_candidate_bundle_fails` and `test_rejected_push_is_a_conflict_without_force`; live failed update in the disposable repository ([publication verification](2026-11-17-publication-verification.md#safe-failure-preservation)) | Evidenced; only the failed collection was exercised live, the other three use local bare remotes. |
| AC-07 animation through `img` and the real README; complete still scene with reduced motion | [README render verification](2026-11-17-readme-render-verification.md) and the 768-pixel check below: Chromium normal motion changes ambient pixels and reduced motion changes none at 360, 768, and 900; [motion verification](motion-verification.md); [fixture gallery](fixture-gallery-verification.md) | Evidenced in Chromium. **Accepted limitation:** WebKit reduced-motion cells stay pending, because Playwright's emulation does not reach an SVG inside `img` in WebKit; signed-in views, Firefox, mobile browsers, and real devices were not tested. |
| AC-08 readable at 360, 768, and 900 on light and dark hosts | [Fixture gallery](fixture-gallery-verification.md) at all three widths and both themes in Chromium and WebKit, including the Linux CI cells; public README at 360 and 900 ([README render verification](2026-11-17-readme-render-verification.md)) and at 768 (below) | Evidenced; readability is layout, overflow, and reviewed legibility, not a perceptual measurement. |
| AC-09 at most 200 KiB, 1,200 elements, 40 animated groups | `test_validate.py` `test_exact_byte_element_and_actual_animation_budgets`; richest fixture 106,722 bytes, 533 elements, 33 groups ([fixture gallery](fixture-gallery-verification.md#richest-fixture-measurements)); live `terrarium.svg` 103,845 bytes, validated | Evidenced. |
| AC-10 workflow token only for publication | [`generate.yml`](../../.github/workflows/generate.yml) uses `permissions: {}` at the top, `contents: write` on the job, and `GH_TOKEN` from `github.token`; `test_workflow.py` `check_token_and_expressions`; no repository secret configured ([publication verification](2026-11-17-publication-verification.md)) | Evidenced; optional broader data credentials share AC-05's evidence and limitation. |
| AC-11 manifest hashes identify one output commit; no run from an output push | Hash equality read independently at `caceb5d`, `b927495`, and `cee9c44`; `test_workflow.py` `check_triggers`; no run followed the bootstrap push ([publication verification](2026-11-17-publication-verification.md#workflow-guards)) | Evidenced. |
| AC-12 login change keeps the seed; ID or schema change stops | `test_render.py` `test_login_rename_keeps_scene_and_subject_changes_vary_it`; `test_growth.py` `test_rename_keeps_identity_and_input_unchanged`; `test_generate.py` `test_identity_mismatch_fails_and_keeps_output` | Evidenced by tests and local remotes; no live rename was observed. |

## Checks added on 2026-11-19

### Privileged-credential collection (AC-05)

`python -m github_terrarium collect --start 2026-11-12 --end 2026-11-19` ran with a local `gh` token whose scopes include `repo`, so it can read the owner's private repositories.
A separate script read every page of `pullRequestContributions` and `issueContributions` for the same window and classified each node.

| Metric | Nodes in window | This repository | Public, counted | Collector equals public count per day |
| --- | --- | --- | --- | --- |
| PRs | 147 | 25 | 122 | yes |
| Issues | 51 | 31 | 20 | yes |

None of the 74 private repositories owned by the account appears among the snapshot's 93 repositories, and this repository is absent from it.
No node in the window was restricted or in a non-public repository.

### README at 768 CSS pixels (AC-07, AC-08)

The [README render](2026-11-17-readme-render-verification.md) harness ran at 768 × 900 against `output` `cee9c44`, from 07:54:36Z to 07:55:15Z.

| Engine | Theme | Normal: changed pixels | Reduced: changed pixels |
| --- | --- | --- | --- |
| Chromium 159.0.8154.6 | light | 3,471 | 0 |
| Chromium 159.0.8154.6 | dark | 3,449 | 0 |
| WebKit 27.2 | light | 3,600 | 3,565 (pending) |
| WebKit 27.2 | dark | 3,526 | 3,447 (pending) |

In every cell the image box was 406 × 162 at x = 49, and the document `scrollWidth` equalled its `clientWidth` (768), so the image caused no horizontal overflow.
The label `Activity through 2026-11-18 UTC`, the identity line, and the stage `Mature` are readable in both themes: [light](assets/2026-11-19-acceptance/readme-chromium-768-light.png), [dark](assets/2026-11-19-acceptance/readme-chromium-768-dark.png).

## Release decisions

- Visual direction: approved in [#13](https://github.com/AndrewDongminYoo/github-terrarium/issues/13#issuecomment-6919598552) on 2026-11-16.
- Scoring version 1: frozen in [#20](https://github.com/AndrewDongminYoo/github-terrarium/issues/20#issuecomment-6932925175) on 2026-11-17.
- License: MIT for code and artwork, chosen in [#21](https://github.com/AndrewDongminYoo/github-terrarium/issues/21#issuecomment-6932926268); see [`LICENSE`](../../LICENSE) and the artwork provenance in [`assets/terrarium/README.md`](../../assets/terrarium/README.md).
- Build tool: `setuptools` pinned to 84.2.1 past the reported advisories ([#24](https://github.com/AndrewDongminYoo/github-terrarium/issues/24), PR [#38](https://github.com/AndrewDongminYoo/github-terrarium/pull/38)).
- Performance: the richest fixture renders in 1.85 ms and decodes in 3.3 ms (Chromium) and 9 ms (WebKit) on one headless host ([fixture gallery](fixture-gallery-verification.md#richest-fixture-measurements)); no detail reduction was needed, and no frame rate or device cost is claimed.

## Verification commands

```bash
python -m unittest discover -s tests -v
ruff check src tests tools
ruff format --check src tests tools
python -m github_terrarium validate --bundle-dir <output clone>
git diff --check
```

## Not claimed

- On-time scheduled starts: both scheduled runs started more than 7 hours after the cron time.
- Real-time updates: the image changes only when a run publishes, and caches may serve the previous image for up to `max-age=300`.
- A frame rate, real-device behavior, or browsers beyond the cells above.
