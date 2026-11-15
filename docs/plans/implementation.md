# GitHub Terrarium Implementation Plan

Status: milestone 1 in progress; read-only probe and offline checks implemented, hosted-token and multi-day review proof pending.
Created: 2026-11-15.
Implement the [product specification](../specs/terrarium.md) using the contracts in [the technical design](../specs/architecture.md).
The initial documentation bootstrap is complete; runtime implementation has started.

## Delivery strategy

Build one deterministic, single-user pipeline from public GitHub activity to an animated SVG and persistent growth state.
Use the existing `main` checkout; a new worktree is not required merely because implementation begins.
Keep each milestone independently reviewable and update implementation status only after its verification runs.
Do not build a website, hosted multi-user API, additional biome, generalized renderer, or private-data feature in v1.

Order: collection proof and contracts → normalization → growth/state → visual prototype → publishing → Actions integration → release validation.
Complete the live collection proof early because token behavior and contribution visibility can affect later design.
Do not activate the daily publisher until state and concurrency regressions pass.

## Milestone 1: executable contracts and collection proof

- [ ] Add `pyproject.toml`, `src/github_terrarium/__main__.py`, `config.py`, `models.py`, and a documented `terrarium.toml` for Python 3.12.
- [ ] Define the snapshot/state types, exact CLI flags, error categories, logical dates, and explicit generator-repository identity input.
- [ ] Implement a minimal read-only collection spike that resolves the target user and one complete page of each required connection.
- [ ] Verify public access in an actual GitHub Actions run using its repository `GITHUB_TOKEN`; report capability gaps without recording raw personal payloads.
- [ ] Prove that separate daily review queries recover a known user's reviews on the same public PR across two UTC days; stop and revise the review source contract if that proof fails or remains unavailable.
- [ ] Establish declared test/format/lint commands and lock any justified dependencies; use the repository-scoped Trunk setup workflow if adopting Trunk.
- [ ] Create synthetic fixture personas and failure responses under `tests/fixtures/`; keep network access out of the default unit suite.

Acceptance: the package installs, its help works, invalid configuration fails clearly, and the live proof identifies the exact supported public collection path.
Verification to establish: `python -m pip install -e .`, `python -m github_terrarium --help`, and `python -m unittest discover -s tests -v`.
Installation, CLI help, and the unit-test commands above now run; hosted verification is still pending.
Record the data-token decision before proceeding; a broader token must remain optional unless the live proof demonstrates a need.

## Milestone 2: complete collection and normalized snapshots

- [ ] Implement `github.py` and `normalize.py` with cursor pagination, public filtering, generator-repository exclusion, explicit request budgets, and bounded retry.
- [ ] Normalize PR/issue openings and review units into completed UTC days; enforce half-open interval boundaries and deterministic ordering.
- [ ] Fetch review contributions per UTC day so the API's latest-review-per-PR behavior cannot collapse multiple days; paginate every daily connection.
- [ ] Collect repository stock counts using immutable repository IDs, including archived originals and excluding fork repositories.
- [ ] Collect and mark complete every day in the requested interval, including genuinely empty days; keep popularity observations on their actual observation day.
- [ ] Fail on partial GraphQL results, incomplete pages, cursor loops, missing required visibility fields, and identity mismatches.

Acceptance: normalized output matches fixtures exactly and contains no private data or unfiltered aggregate contribution totals.
Verification: tests for multiple pages, UTC midnight, same-PR reviews on different days, duplicate records, restricted nodes, privileged-token visibility, 401/403/429/5xx responses, retry exhaustion, and generator feedback exclusion.
Traceability: AC-05, AC-06, AC-10, and AC-12.

## Milestone 3: persistent growth and recovery

- [ ] Implement `growth.py` and `state.py` with versioned schemas, date continuity, size limits, and exact integer scoring.
- [ ] Implement 30-day bootstrap activity credit, popularity baseline initialization, and bounded trait normalization.
- [ ] Reconcile daily awards by positive differences, enforce daily rather than per-run caps, and retain per-repository high-water marks across disappearance/reappearance.
- [ ] Refresh the recent 30-day window, recover missed activity up to 90 days automatically, and provide deliberate multi-batch recovery for larger gaps.
- [ ] Implement explicit historical recovery without invented popularity history or an accidental implicit reset.
- [ ] Derive growth stages from awarded XP, preserve user identity across login changes, and reject unsupported versions or changed user IDs.

Acceptance: replay cannot create growth, repeated runs cannot evade caps, and incomplete data never causes a state transition.
Verification: table-driven cases at every stage/cap boundary; same-day reruns; a star drop/recovery; renamed and newly observed repositories; removed/reappearing repositories; stale-state recovery; null versus empty days; and a 2 MiB overflow fixture.
Prove the example scores of 39 activity XP and 11 popularity XP, plus the daily maxima of 115 and 90.
Traceability: AC-02, AC-03, AC-04, AC-06, and AC-12.

## Milestone 4: one complete visual prototype

- [ ] Implement `render.py` and original assets in `assets/terrarium/`: glass vessel, layered soil, central plant, pond, seedlings, flowers/fireflies, and mushrooms.
- [ ] Use fixed anchors and independent seeded variation so one changing trait does not rearrange the habitat.
- [ ] Add leaf sway, firefly travel, and pond ripples through embedded CSS; add complete static and reduced-motion states.
- [ ] Implement `validate.py` for XML structure, prohibited content/references, escaped text, and the agreed size/element/animation budgets.
- [ ] Render the fixture gallery through HTML image elements and capture each persona at narrow and wide widths on light/dark host backgrounds.

Acceptance: all five metrics create understandable differences, every stage is complete, and reduced motion retains the same scene.
Verification: XML/security-negative fixtures, byte-identical rendering from fixed inputs, 360/768/900-pixel captures, normal/reduced-motion captures, and time-separated frames proving motion through `img`.
Run Chromium and WebKit checks where available; explicitly record any untested browser rather than claiming universal compatibility.
Visual gate: review the fixture gallery with the operator before expanding artwork or treating the direction as approved.
Traceability: AC-01, AC-07, AC-08, and AC-09.

## Milestone 5: safe output-branch publication

- [ ] Implement `publish.py` using an isolated temporary Git directory or Git plumbing, without changing the source checkout's branch or staging unrelated files.
- [ ] Read the expected remote output parent, distinguish absent branch from missing state, and prepare all three generated files with canonical serialization and a hash manifest.
- [ ] Create one commit per changed bundle, skip byte-identical output, and preserve unrelated paths on an existing output branch.
- [ ] Push without force; on a changed remote head, fetch, discard the old snapshot, recollect, rebuild from the new state, and retry once, including same-day conflicts.
- [ ] Read back the published commit and hashes before reporting success.

Acceptance: a remote reader sees either the prior complete bundle or the new complete bundle, and source files never enter `output` accidentally.
Verification: local bare-remotes covering first publication, no change, normal growth, missing/corrupt state, untracked source files, unrelated output paths, same-day stale-snapshot conflicts, backwards snapshot dates, retry exhaustion, and post-push readback failure.
Traceability: AC-02, AC-06, and AC-11.

## Milestone 6: daily GitHub Actions integration

- [ ] Add read-only `ci.yml` for the declared unit, formatting, lint, and fixture-validation commands.
- [ ] Add `generate.yml` with default-branch-only `workflow_dispatch`, the 00:23 UTC schedule, a bounded job timeout, and serialized publication with cancellation disabled.
- [ ] Set publication permissions at the job level, pin actions to verified commit SHAs, and keep PR validation away from write credentials.
- [ ] Connect collection, previous-state loading, building, validation, publication, and concise failure summaries.
- [ ] Document workflow enabling, manual reruns, token capability, output URLs, schedule delay/disablement, and recovery in the README.

Acceptance: manual generation publishes a validated bundle; an output push cannot trigger regeneration; failed collection preserves the existing image and state.
Verification: read the full workflow run and job result, inspect the live output commit/manifest, repeat a same-day run, and observe a later-day transition before claiming daily growth works.
Do not call a successful manual run proof that the schedule has executed; observe a scheduled run separately.
Traceability: AC-04, AC-06, AC-10, and AC-11.

## Milestone 7: release validation and documentation

- [ ] Publish a demonstration README in this repository that embeds the generated SVG; do not edit the operator's separate profile repository without authorization.
- [ ] Verify animation through GitHub's rendered image, freshness labeling, caching behavior, and mobile-width readability.
- [ ] Measure real rendering behavior for the richest fixture and record devices/browsers used; reduce expensive detail if the initial budget is insufficient.
- [ ] Calibrate the proposed scoring constants against the fixture gallery and freeze scoring version 1 before ongoing production growth.
- [ ] Select a license with the operator before distributing reusable code/art and retain provenance for any adopted material.
- [ ] Update README status, setup steps, actual commands, and recovery instructions; preserve visible review and verification evidence with the release work.

Acceptance: AC-01 through AC-12 have recorded evidence, the visual direction is approved, and one real scheduled transition is observed.
Release notes must distinguish tested behavior from known gaps; no full-browser or real-time guarantees without evidence.

### GitHub README smoke scenario

Use the installed `agent-browser` in a named isolated session for the public demonstration README, refreshing snapshots after navigation and closing the session afterward.
Reuse milestone 4's browser harness for viewport and reduced-motion settings, and use the operator's named browser only when signed-in state is required.

1. Read the published output commit and `manifest.json`; record the expected complete-activity date and SVG hash.
2. Open the rendered repository README at 360 CSS pixels and capture the entire terrarium; expect a readable identity/date label, a visible whole vessel, and no image-caused horizontal overflow.
3. With normal motion, capture the same image at two times at least two seconds apart; expect leaf/firefly/ripple pixels to change while scene anchors and text stay fixed.
4. Enable reduced motion, reload, and capture twice at the same interval; expect the same complete scene with no animated-pixel changes.
5. Repeat the layout check at 900 CSS pixels on light and dark host backgrounds; compare the freshness label with the manifest's complete-activity date.
6. After a later-day publication, verify the new remote SVG/hash first, then reload the README using its normal stable image URL; record when the new label first appears and any delay relative to publication.
7. If GitHub still displays the older image, record the observed older label and caching delay as pending; do not call the new image visible, bypass the test with a changed URL, or purge the shared cache automatically.

Keep captures, output commit, browser/version, viewport, motion preference, and observation times with the release verification evidence.

## Risk-driven checkpoints

| Risk | Earliest check | Required response |
| --- | --- | --- |
| Token cannot read the required public contribution connections | Milestone 1 Actions spike | Resolve the collection/authentication contract before writing the complete collector. |
| GitHub contribution semantics differ from the intended metric | Milestones 1–2 | Correct labels and fixtures; do not substitute unrelated totals silently. |
| Replays, late data, or concurrency inflate growth | Milestones 3 and 5 | Block publication until adversarial state and remote tests pass. |
| SVG looks correct only when opened directly | Milestone 4 | Fix the image-context rendering before workflow integration. |
| High activity makes the scene illegible or expensive | Milestones 4 and 7 | Bound slots and simplify details; retain the stable layout. |
| Schedule or API failures create gaps | Milestones 3 and 6 | Preserve prior output, recover bounded history, and report unknown intervals. |

## Completion reporting

For every milestone, report changed files, checks actually run, skipped checks, remaining risks, and the next eligible milestone.
Keep planned commands clearly separated from commands that exist and have passed.
The bootstrap is complete when the repository and these documents are published and read back; that does not complete any runtime milestone above.
