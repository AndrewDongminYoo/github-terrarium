# CI render, bundle, and browser regression gates

Implement [issue #18](https://github.com/AndrewDongminYoo/github-terrarium/issues/18) by extending the existing read-only workflow `.github/workflows/ci.yml`; do not recreate it.
Written on 2026-11-17 at `main` = `6e54e95` as the brief for a later `/pr-loop` run; the decisions below are proposed defaults to confirm at that run's plan gate.
The [GitHub Actions boundary](../specs/architecture.md#github-actions-boundary) and the [fixture gallery evidence](../notes/fixture-gallery-verification.md) are the governing contracts.

## Current state at 6e54e95

- `ci.yml` (name "Public collection") has one `test` job on `ubuntu-latest` with `permissions: contents: read`, Python 3.12, hashed `requirements-dev.txt` install, editable install, `unittest`, and Ruff over `src tests` only.
- Its push trigger is `branches: [main, feat/persistent-growth]`; the second branch is a stale task-specific allowlist that #18 replaces.
- Two live steps (`probe`, `collect`) run with `GH_TOKEN: ${{ github.token }}` when `github.event_name != 'pull_request'` and the repository is `AndrewDongminYoo/github-terrarium`; they do not check the ref, so a manual dispatch from any branch reaches them.
- Actions are pinned to full SHAs: `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` (v7.0.1) and `actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0` (v7.1.0).
- `requirements-dev.txt` already pins `playwright==1.65.2` (with `greenlet`) and `ruff==0.14.5`; browsers are installed separately and are not in the lock.
- Offline commands that exist: `python -m github_terrarium build --snapshot FILE --bootstrap --bundle-dir DIR --source-commit SHA`, `python -m github_terrarium validate --bundle-dir DIR` (exit 0 valid, 1 invalid, 2 usage), `python tools/gallery.py build [--out DIR]`, and `python tools/gallery.py check [--out DIR] [--engine chromium webkit]` (exit 1 when any cell fails, including a negative control that passes; pending cells do not fail).
- Persona fixtures: `tests/fixtures/{empty,issues,popularity,pull-requests,reviews}.json`.
- Known pending gallery cells: WebKit reduced motion through `img` (Playwright emulation does not reach SVG inside `img`), and every Linux cell, which no run has produced yet.
- README line "it does not lint `tools` yet, so run the `tools` checks locally" and the unchecked milestone 6 `ci.yml` checkbox in `docs/plans/implementation.md` describe the gap this work closes.

## Contract and decisions (proposed defaults)

1. Keep one workflow file and split it into jobs so a browser failure does not hide unit or bundle results:
   - `test`: the existing install, `unittest`, and Ruff, widened to `ruff check src tests tools` and `ruff format --check src tests tools`.
   - `bundles`: offline deterministic bundle regression (item 3).
   - `browser`: the gallery smoke matrix (item 4).
   - `live`: the existing `probe` and `collect` steps, unchanged in behavior, restricted as in item 2.
2. Durable trigger and credential policy:
   - `push` on `main` only, `pull_request` (all branches), and `workflow_dispatch`; no trigger for `output`, so output pushes cannot start CI or generation.
   - Top-level `permissions: contents: read`; no job gains write permission, no secrets other than `github.token`, and no `pull_request_target`.
   - `live` runs only when `github.event_name != 'pull_request'`, the repository is `AndrewDongminYoo/github-terrarium`, and `github.ref == 'refs/heads/main'`.
   - `concurrency` grouped by workflow and ref with `cancel-in-progress: true` for pull requests only, since every job is read-only.
   - Record the policy in `docs/specs/architecture.md` §GitHub Actions boundary.
3. Bundle regression in a small script `tools/ci_bundles.py` (runnable locally and unit-tested), not inline YAML:
   - For each persona fixture, run `build --bootstrap` into a fresh temporary directory with `--source-commit` set to the checked-out SHA, then `validate`; both must exit 0.
   - Build each fixture twice into separate directories and require byte-identical bundles.
   - Negative path: copy one valid bundle, flip one byte of `terrarium.svg` without updating the manifest, and require `validate` to exit 1 with no stdout; a passing negative case fails the script.
   - Exit 0 only when every positive and negative expectation holds; print one line per fixture.
4. Browser smoke on Linux:
   - `python -m playwright install --with-deps chromium webkit`, then `python tools/gallery.py build` and `python tools/gallery.py check`.
   - Chromium then WebKit in one job, sequentially, as the tool already does; job timeout 20 minutes.
   - Pending cells stay pending; the job fails only on failed cells, as the tool defines.
5. Failure artifacts: on failure of `bundles` or `browser`, upload only `work/gallery/results-*.json`, `work/gallery/captures/`, and the script's log with `actions/upload-artifact` pinned to a full SHA verified at implementation time, `retention-days: 7`, and `if-no-files-found: ignore`; never upload the workspace root, `.git`, or environment files.
6. Do not cache Playwright browsers in the first version; measure the install time in the PR's own run and record it.
7. Documentation: update the README CI paragraph, `CONTRIBUTING.md` verification text, `docs/specs/architecture.md` §GitHub Actions boundary, and tick the milestone 6 `ci.yml` checkbox in `docs/plans/implementation.md`; do not edit dated notes.

Questions for the plan gate:

- Upload artifacts on failure only (default) or on every run?
- Run the `browser` job on every pull request (default) or only when `src/`, `assets/`, or `tools/gallery.py` change?
- Keep the browser matrix at both engines (default) or Chromium only on pull requests?

Plan-gate answers (2026-11-17): all three defaults were accepted, so artifacts upload on failure only, the `browser` job runs on every pull request, and both engines run on every event.

## Work order

1. Create `tools/ci_bundles.py` and `tests/test_ci_bundles.py`; prove the negative case fails when the tamper step is removed.
2. Restructure `ci.yml` into the four jobs with the trigger, permission, concurrency, and `live` conditions above; keep both existing action pins and add the verified `upload-artifact` pin.
3. Run the bundle script and the gallery locally (macOS, one browser at a time) and the full gates.
4. Update the documents in item 7.
5. Open the PR; its own CI run is the Linux evidence for the bundle and browser jobs; record the Linux gallery counts (passed, pending, failed per engine), browser versions, install time, and job durations in the PR body.
6. Prove a failing path in CI once: push a temporary commit that breaks the bundle negative expectation or a gallery control, confirm the job fails and uploads the artifact, then revert it in the same PR before merge, and record the run URLs.

## Verification

- Local: `python -m unittest discover -s tests -v`, `ruff check src tests tools`, `ruff format --check src tests tools`, `python tools/ci_bundles.py`, `python tools/gallery.py build`, `python tools/gallery.py check`, and `git diff --check`.
- Workflow review: no workflow linter is installed on this Mac (`actionlint` and `zizmor` are absent); review triggers, `if:` conditions, permissions, pins, and artifact paths by reading the YAML, and rely on the PR's own run as the executed check.
- CI evidence on the PR: all four jobs green on the final head, `live` skipped on the pull request, and the deliberate failing run from work order step 6.
- Live hosted publication evidence is #26's scope, not this issue's.

## Risks

- `playwright install --with-deps` downloads both browsers and system packages on every run; measure and revisit caching only if the job is slow.
- The two-second frame comparison can be timing-sensitive on shared runners; if a cell flakes, record the run and fix the tool deliberately rather than retrying silently.
- Linux WebKit and Chromium may report different pending or failing cells than macOS; record the actual counts and update the evidence note in a follow-up rather than weakening an assertion to pass.

## Out of scope

The scheduled generation workflow `generate.yml` (#19), live publication evidence (#26), restore (#17), and the follow-ups #43 and #44.
