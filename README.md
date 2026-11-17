# GitHub Terrarium

<img src="https://raw.githubusercontent.com/AndrewDongminYoo/github-terrarium/output/terrarium.svg" alt="Animated paper-cut terrarium grown from AndrewDongminYoo's public GitHub activity, labeled with its last complete UTC activity day">

**Generated habitat:** the [daily workflow](#daily-workflow) publishes this image to the [`output` branch](https://github.com/AndrewDongminYoo/github-terrarium/tree/output) under a stable URL; its label reads "Activity through" the last complete UTC day, and a viewer can still see an earlier copy for a while (see [freshness and caching](#freshness-and-caching)).

![Animated paper-cut terrarium design sample](assets/references/terrarium-papercut-sanctuary.svg)

**Design preview:** This fixed animated SVG sample uses synthetic data and is not generated from live GitHub activity.

A small living world shaped by your GitHub activity.
Stars bring flowers and fireflies, forks spread seedlings, pull requests grow plants, reviews enrich a pond, and issues add mushrooms.

**Status: public collection, persistent growth, and animated SVG rendering implemented.**
A paginated public collector, local growth-state reconciliation, read-only API probe, and offline checks are implemented.
The paper-cut SVG renderer, bounded ambient motion, and offline SVG validator are available as Python APIs, and offline `build`/`validate` commands produce and check the three-file output bundle, a low-level `publish` command pushes a validated bundle to the `output` branch, `generate` connects collection, growth, building, and publication with one fresh recollection after a conflict, and a manual `restore` command brings back an earlier output bundle as a new commit; a development-only browser fixture gallery checks the images through HTML `img` elements, and the guarded daily workflow `generate.yml` runs `generate` on a schedule and on manual dispatch.
The first habitat was published by a manual bootstrap run on 2026-11-17, and a same-day replay reported `no-change`; see [publication verification](docs/notes/2026-11-17-publication-verification.md).
No scheduled run has been verified.

## Run the collection probe

Use Python 3.12 or later.
The package has no third-party runtime dependencies; Ruff and Playwright are pinned development-only tools.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.txt
python -m pip install -e .
python -m github_terrarium probe --repository AndrewDongminYoo/github-terrarium
```

Set `GH_TOKEN` or `GITHUB_TOKEN` in the environment; never put it in configuration or command arguments.
`terrarium.toml` contains the target login.
The repository argument may instead come from `GITHUB_REPOSITORY` in Actions.
`--day YYYY-MM-DD` selects a completed UTC day; the default is yesterday in UTC.
The probe reads at most one page of each connection and explicitly reports truncation.
Its sample counts are not complete statistics and must not be used for scoring.
It writes no growth state and never updates a remote branch.

```bash
python -m unittest discover -s tests -v
ruff check src tests tools
ruff format --check src tests tools
```

The read-only CI workflow runs these checks, an offline bundle regression (`python tools/ci_bundles.py`), and the fixture gallery in Chromium and WebKit on Linux; its triggers, credentials, and live-probe conditions are defined in the [GitHub Actions boundary](docs/specs/architecture.md#github-actions-boundary).
Hosted tests and public API access with the default workflow token passed in [Actions run 43690047131](https://github.com/AndrewDongminYoo/github-terrarium/actions/runs/43690047131) at `aaa3759`.
Daily review recovery was verified against existing public reviews; see [collection evidence](docs/notes/collection-verification.md).
Regenerate the development lock with `uv pip compile requirements-dev.in --generate-hashes -o requirements-dev.txt` after changing the input.

## Collect daily activity

```bash
python -m github_terrarium collect --repository AndrewDongminYoo/github-terrarium --start 2026-11-13 --end 2026-11-15 > snapshot.json
```

`--start` is inclusive, `--end` is exclusive and defaults to today in UTC.
A run accepts 1–90 completed days and prints a validated JSON snapshot only after every page succeeds.
Use `--expected-subject NODE_ID` when continuing an existing user's habitat.
The snapshot contains public repository stock counts and daily PR, issue, and review contribution counts, including empty days.
These are GitHub-recognized contributions, not an exhaustive record of every GitHub action.
Reviews count each PR once per UTC day; the generator repository, restricted/private records, and fork repositories' stock counts are excluded.
Popularity is observed on the actual collection date even when the activity interval is historical.
A collection that crosses UTC midnight fails with no snapshot; rerun it.
The collector allows at most 1,000 HTTP attempts, 100 pages per connection, three attempts per request, and a four-minute collection deadline.
Rate-limit waits above 30 seconds fail with no snapshot; rerun later.
Collection does not award growth or publish output.

## Reconcile local growth

The `grow` command is offline and prints a validated candidate state; it does not publish files or contact GitHub.
Bootstrap requires exactly 30 completed days ending on the snapshot's actual observation date.

```bash
python -m github_terrarium grow --snapshot tests/fixtures/pull-requests.json --bootstrap > state.json
python -m github_terrarium grow --snapshot tests/fixtures/pull-requests.json --state state.json > next-state.json
cmp state.json next-state.json
```

Use a separate destination from the input state so shell redirection cannot truncate the prior state.
Publishing a bootstrap additionally requires an absent remote output branch and an explicit `publish --bootstrap`; this local command alone does not authorize a remote reset.
For normal updates, collect from the earlier of today minus 30 days and the day after `last_complete_activity_day`, ending at today's UTC date exclusively.
The snapshot must cover exactly that interval, with no unknown days; an interval over 90 days requires explicit recovery.

Daily awards never decrease and reruns award only positive differences within the same daily caps.
Repository watermarks use immutable GitHub node IDs, not repository names: renames and disappearance/reappearance cannot copy star credit.
An unseen repository ID establishes its current baseline without an initial popularity award.
User login changes retain the same habitat identity; a different user ID fails.

For a longer gap, choose one fixed completed cutoff and collect contiguous batches of at most 90 days.
Start the first batch on the day after `last_complete_activity_day`; each next batch starts at the prior batch's exclusive end.
Pass `--recover-through YYYY-MM-DD` with that same cutoff to every `grow --state` call.
Persist each validated candidate separately before proceeding to the next batch.
Recovery retains existing popularity watermarks and observations without awarding historical popularity or using the batch's stock counts.
An unfinished recovery records its cutoff and blocks normal updates; after the final batch, perform a normal fresh collection to update popularity on its actual observation date.
The same explicit mode can apply deliberate older corrections within a snapshot of at most 90 days; do not include activity before this habitat's bootstrap.

State files are UTF-8 JSON, limited to 2 MiB, and reject duplicate keys, unsupported versions, missing dates, invalid counts, and inconsistent derived activity totals.
The five synthetic fixtures cover empty, popularity-heavy, PR-heavy, review-heavy, and issue-heavy histories.
See [growth verification](docs/notes/growth-verification.md) for the checked invariants and local review results.

## Render a habitat

The `render(state)` Python API accepts a validated growth state and returns deterministic UTF-8 SVG bytes.
It reuses the existing stages and normalized traits, with stable subject-ID-based anchors and bounded object slots.
Embedded CSS adds leaf sway, firefly travel, and pond ripples; after seven completed UTC days with no eligible PR, review, or issue activity, motion becomes calmer without changing earned growth or geometry.
Reduced motion disables every ambient animation and transition, and disabled CSS leaves the complete static scene visible.
The `build` command below renders through this API, and `publish` pushes the resulting bundle.

```bash
python - <<'PYTHON'
from pathlib import Path
from github_terrarium.growth import advance
from github_terrarium.render import render
from github_terrarium.state import read_json

state = advance(read_json("tests/fixtures/pull-requests.json"))
Path("terrarium-preview.svg").write_bytes(render(state))
PYTHON
```

The container-free scene assembles packaged [paper-cut SVG pieces](assets/terrarium/papercut.svg) derived from the preserved design reference; their [provenance and extraction command](assets/terrarium/README.md) are recorded with the source.
Earned growth expands the tree and roots through five stages; recent activity fills bounded canopy, branch, seedling, flower, firefly, pond, mushroom, and ground-cover slots.
The fixed banner above previews the reference artwork; it is separate from generated renderer output.
The renderer alone does not establish full browser compatibility or approval of its generated scenes; those remain gallery and operator-review gates.
See [paper-cut port verification](docs/notes/papercut-renderer-verification.md) for the checked scope and remaining limits.
See [motion verification](docs/notes/motion-verification.md) for the tested fallback behavior and reduced-motion browser setup.

## Validate a rendered SVG

`validate_svg(raw)` accepts current generator-format UTF-8 SVG bytes and returns `None`, or raises `ValueError` without rewriting the image.
It checks XML, the closed element/attribute/CSS vocabulary, typed internal references, finite geometry, structural identity/date metadata, and the 200 KiB / 1,200-element / 40-animation limits.
DTD/entities, processing instructions, external resources, reference cycles and excessive nesting/reuse are rejected offline.
Only the renderer's exact ambient stylesheet or complete CSS absence is supported; arbitrary SVG/CSS is outside this API.

```bash
python - <<'PYTHON'
from github_terrarium.validate import MAX_BYTES, validate_svg

with open("terrarium-preview.svg", "rb") as stream:
    validate_svg(stream.read(MAX_BYTES + 1))
PYTHON
```

Call this API explicitly; `render` does not invoke it automatically.
See [SVG validation verification](docs/notes/svg-validation-verification.md) for negative-fixture coverage and limits.

## Check the fixture gallery in browsers

The gallery embeds every fixture SVG through HTML `img` elements: the five personas, every growth stage, a fully saturated Sanctuary, a renamed user, and a calm inactive habitat, all grown with the existing growth engine.

```bash
python -m playwright install chromium webkit
python tools/gallery.py build
python tools/gallery.py check
```

`build` is offline and writes `work/gallery/index.html`, the SVGs, and measurements; open the page in any browser to review the scenes.
`check` runs Chromium and then WebKit at 360/768/900 CSS pixels, on light and dark host backgrounds, with normal and reduced motion, and fails on horizontal overflow, clipping, missing motion, moving text, or reduced-motion changes.
It also runs deliberate overflow, clipping, missing-motion and ignored-reduced-motion controls and fails if any of them passes.
Captures and `results-<engine>.json` stay in the ignored `work/gallery/` directory, and every browser it opens is closed.
Unit tests cover the browser-free parts; the browser checks run only through this command.
See [fixture gallery verification](docs/notes/fixture-gallery-verification.md) for engine versions, results, measurements and pending cells; visual approval remains a separate review.

## Build and validate an output bundle

`build` is offline: it reconciles growth from a snapshot, renders and validates the SVG, and writes `terrarium.svg`, `state.json`, and `manifest.json` to a bundle directory.
It prints the manifest on success; a data or validation failure exits 1 with no stdout and leaves the destination and inputs unchanged, and usage errors exit 2.

```bash
python -m github_terrarium build --snapshot tests/fixtures/pull-requests.json --bootstrap --bundle-dir bundle --source-commit "$(git rev-parse HEAD)"
python -m github_terrarium validate --bundle-dir bundle
```

For an update, pass `--state` with the prior `state.json` instead of `--bootstrap`; the same directory may be the destination.
`--bootstrap` refuses a directory that already holds any bundle file.
An update into a directory that holds a bundle requires that bundle to be valid, for the same user, and to contain exactly the supplied prior state, so a stale `--state` copy cannot replace newer growth.
Other files in the directory are never touched.
`validate` checks the three files without modifying them.
The [technical design](docs/specs/architecture.md#atomic-publication) defines the manifest keys and the validation rules.

## Publish a bundle

`publish` revalidates a bundle and pushes it to the `output` branch with one commit whose parent is the expected remote head; the push is leased on that head, so it fast-forwards or fails as a conflict and never rewrites history.

```bash
python -m github_terrarium publish --bundle-dir bundle --repository AndrewDongminYoo/github-terrarium --expected-parent absent --bootstrap
python -m github_terrarium publish --bundle-dir bundle --repository AndrewDongminYoo/github-terrarium --expected-parent "$(git ls-remote https://github.com/AndrewDongminYoo/github-terrarium.git refs/heads/output | cut -f1)"
```

It builds the commit in a temporary bare Git directory, so the current checkout's branch, index, worktree, and configuration are never read or changed.
Only `terrarium.svg`, `state.json`, and `manifest.json` change; every other path on `output` is preserved, and extra files in the bundle directory are ignored.
A new root commit requires both `--expected-parent absent` and `--bootstrap`, and `--bootstrap` fails when the branch exists.
An existing branch must hold a valid bundle for the same subject, and the candidate's activity and popularity dates must not move backwards; a candidate with an unfinished recovery cutoff is refused.
When all three files are byte-identical to the parent, nothing is pushed and the result reports `no-change`.
After a push, a fresh fetch must show the new commit as the remote head with matching file hashes before `published` is reported.
The token comes only from `GH_TOKEN` or `GITHUB_TOKEN` and reaches Git through environment-scoped configuration, never through arguments, remote URLs, or commits; `--remote URL` overrides the default `https://github.com/OWNER/NAME.git` for local tests.
Success prints a canonical JSON result; failures exit 1 with no stdout, a remote head that is absent or differs from a SHA expected parent, or a rejected push, exits 3, and usage errors exit 2.
A failed readback after a successful push exits 1 and names the pushed commit.
`generate` below fetches fresh data and retries once after a conflict.

## Generate and publish

`generate` reads the current `output` head and bundle, collects the interval that state requires, grows the state, builds and validates the bundle, and publishes it over the head it read.

```bash
GH_TOKEN=... python -m github_terrarium generate --config terrarium.toml --repository AndrewDongminYoo/github-terrarium --source-commit "$(git rev-parse HEAD)" --bootstrap
GH_TOKEN=... python -m github_terrarium generate --config terrarium.toml --repository AndrewDongminYoo/github-terrarium --source-commit "$(git rev-parse HEAD)"
```

`--bootstrap` is accepted only while the `output` branch is absent; an existing branch without a valid bundle fails and is never reset.
An update collects the last 30 completed UTC days plus any missed days; a gap over 90 days or an unfinished recovery fails before collection and needs `grow --recover-through` batches.
If another publisher moves the head first, the run discards its snapshot, reads the new head, collects again, and retries once; a second conflict exits 3 and leaves the newer output untouched.
`--source-commit` defaults to `GITHUB_SHA`, and `--remote URL` works as for `publish`.
Success prints one JSON summary with the activity interval, stock date, recovered gap days, XP delta, file sizes, attempts, commit, and `published` or `no-change`; failures print one error line to stderr and nothing to stdout.
`--summary PATH` also appends a Markdown summary of the result or the failure to `PATH`, as the workflow does with `GITHUB_STEP_SUMMARY`; if `PATH` cannot be written, the exit code is unchanged and stderr gets one more `warning: summary not written:` line, after a success too.

## Restore a historical bundle

`restore` is a manual maintenance command that brings back the bundle of an earlier `output` commit as a new commit on top of the current head.

```bash
GH_TOKEN=... python -m github_terrarium restore --repository AndrewDongminYoo/github-terrarium --from-commit <earlier output SHA> --expected-parent "$(git ls-remote https://github.com/AndrewDongminYoo/github-terrarium.git refs/heads/output | cut -f1)"
```

Both SHAs are full 40-character SHAs, and `--from-commit` must be the current head or one of its ancestors on `output`.
The historical `manifest.json`, `state.json`, and `terrarium.svg` must validate as a bundle for the same subject with supported versions; they are written unchanged, every other path on `output` is kept, and the history is never rewritten.
This is the only command that may move the activity and popularity dates backwards; the next `generate` grows from the restored state with the normal 30-day window and 90-day gap rules.
A head that is absent or differs from `--expected-parent`, or a push rejected by the lease, exits 3 and is not retried; read the head again and choose again.
A push refused by a hook or a branch protection rule exits 1.
Any other refusal exits 1 and pushes nothing, identical files report `no-change`, and `--remote URL` works as for `publish`.
Success prints one JSON result with the outcome, the restored-from commit, the new commit, its parent, and the file hashes.

## Daily workflow

[`generate.yml`](.github/workflows/generate.yml) runs `generate` at 00:23 UTC each day (09:23 Asia/Seoul) and on manual dispatch from the default branch; the [GitHub Actions boundary](docs/specs/architecture.md#github-actions-boundary) defines its triggers, permissions, and guards.

- **Configuration:** `terrarium.toml` holds only the target `login`. A fork or a copy also changes the `github.repository == 'AndrewDongminYoo/github-terrarium'` guard in `generate.yml`, without which the job skips every step, and the owner and name in the embed URL at the top of this README, together with the `REPOSITORY` constant in `tests/test_workflow.py` and the `EMBED` constant in `tests/test_readme.py` that pin them.
- **Enabling:** the schedule is active once the workflow is on the default branch. Scheduled runs fail with "Output branch is absent" until one manual run creates the habitat (Actions → Daily generation → Run workflow on the default branch, with `bootstrap` checked); that bootstrap ran on 2026-11-17, so `output` now exists. A fork or a new repository runs the same dispatch once. `bootstrap` works only while `output` is absent, an `output` branch without a valid bundle fails every run, and no command deletes or resets the branch; an intentional new-user reset is outside routine generation, as the [technical design](docs/specs/architecture.md#verification-and-recovery) states.
- **Manual reruns:** run the workflow again with `bootstrap` unchecked. The manifest records the source commit, so a rerun reports `no-change` and pushes nothing only when it collects nothing new and the default branch has not moved since the last publication; otherwise it publishes a new `output` commit. A dispatch from another branch skips the job.
- **Token:** the job uses only the repository `GITHUB_TOKEN` with `contents: write`; no personal token or secret is needed, and none is created or rotated.
- **Output URLs:** after the bootstrap, the image is `https://raw.githubusercontent.com/AndrewDongminYoo/github-terrarium/output/terrarium.svg`, next to `state.json` and `manifest.json` on the [`output` branch](https://github.com/AndrewDongminYoo/github-terrarium/tree/output).
- **Delays and disablement:** GitHub can start scheduled runs late or drop them, and disables schedules in a public repository after 60 days without repository activity; re-enable the workflow on the Actions page; the next scheduled run or a manual dispatch resumes generation. The generated commits on `output` are not assumed to prevent disablement. A missed day is collected by the next run, and a delay is not inactivity.
- **Failures and recovery:** read the job summary; a failed run leaves the last valid habitat unchanged. A gap over 90 days or an unfinished recovery needs `grow --recover-through` batches, and the workflow never resets or bootstraps over an existing branch. To roll back to an earlier valid bundle, run [`restore`](#restore-a-historical-bundle) by hand; the workflow never restores. [Rehearse recovery locally](#rehearse-recovery-locally) shows each case.

### Freshness and caching

The image label and the manifest's `complete_activity_day` name the last complete UTC activity day, which is the day before the run; the manifest's `stock_observation_day` is the run's own UTC date, on which stars and forks were read.
After a dropped or failed run, the published label stays on the earlier day until the next successful run, which also collects the missed days, so no growth is lost.
GitHub serves the image through caches, so a reader can see the previous image for a while after a publication; the `manifest.json` on `output` is the authority for what was published.
Keep the URL stable: a query string or another cache-busting URL is not supported.

## Rehearse recovery locally

These commands run from the checkout root against synthetic snapshots and a local bare remote in the ignored `work/recovery/` directory; they need no token and never reach GitHub.
In production, each snapshot comes from [`collect`](#collect-daily-activity) with `--expected-subject` and the same `--start`/`--end`, and its `observed_on` is the collection date; recovery starts from the `state.json` on `output`, and the recovered bundle goes out with [`publish`](#publish-a-bundle) over the current head.

```bash
mkdir -p work/recovery
python - <<'PYTHON'
import json
from datetime import date, timedelta
from pathlib import Path


def write(name, start, end, observed, stars):
    start, end = date.fromisoformat(start), date.fromisoformat(end)
    days = {
        (start + timedelta(days=n)).isoformat(): {"issues": 0, "prs": 1, "reviews": 0}
        for n in range((end - start).days)
    }
    snapshot = {
        "activity_end": end.isoformat(),
        "activity_start": start.isoformat(),
        "complete_snapshot": True,
        "days": days,
        "observed_on": observed,
        "repositories": {"R1": {"forks": 0, "stars": stars}},
        "schema_version": 1,
        "subject": {"id": "U1", "login": "octocat"},
    }
    text = json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
    Path("work/recovery", name).write_text(text)


write("bounded.json", "2026-11-15", "2027-01-15", "2027-01-15", 3)
write("batch-1.json", "2026-11-15", "2027-01-15", "2027-03-15", 9)
write("batch-2.json", "2027-01-15", "2027-03-15", "2027-03-15", 9)
write("fresh.json", "2027-02-13", "2027-03-15", "2027-03-15", 9)
PYTHON
cd work/recovery
python -m github_terrarium grow --snapshot ../../tests/fixtures/pull-requests.json --bootstrap > state.json
```

The bootstrap state is complete through 2026-11-14.
A bounded gap needs no command: a run on 2027-01-15 collects `[2026-11-15, 2027-01-15)`, 61 days within the 90-day limit, and `generate` does it in one normal update.

```bash
python -m github_terrarium grow --snapshot bounded.json --state state.json > bounded-state.json
```

A run on 2027-03-15 would need 120 days, so a normal update fails with `Gap exceeds 90 days; use explicit recovery batches` and exit 1.
Recover with contiguous batches of at most 90 days toward one fixed cutoff, each saved to its own file, then build the final normal snapshot on the recovered state; the [growth rules](#reconcile-local-growth) define the batches.

```bash
python -m github_terrarium grow --snapshot fresh.json --state state.json > refused.json || echo "refused: exit $?"
python -m github_terrarium grow --snapshot batch-1.json --state state.json --recover-through 2027-03-15 > recovery-1.json
python -m github_terrarium grow --snapshot batch-2.json --state recovery-1.json --recover-through 2027-03-15 > recovery-2.json
python -m github_terrarium build --snapshot fresh.json --state recovery-2.json --bundle-dir recovered --source-commit "$(git rev-parse HEAD)"
python -m github_terrarium validate --bundle-dir recovered
```

The last batch must end at the cutoff: until then, `grow` and `build` refuse a normal snapshot with `Finish explicit recovery before normal updates`, and `publish` refuses a state that records an unfinished cutoff.
To rehearse publication and the append-only `restore`, seed a local bare remote with the bootstrap bundle, publish the recovered bundle over it, and restore the first bundle as a third commit:

```bash
git init --quiet --bare remote.git
REMOTE="$PWD/remote.git"
python -m github_terrarium build --snapshot ../../tests/fixtures/pull-requests.json --bootstrap --bundle-dir first --source-commit "$(git rev-parse HEAD)"
python -m github_terrarium publish --bundle-dir first --repository octocat/terrarium --remote "$REMOTE" --expected-parent absent --bootstrap
python -m github_terrarium publish --bundle-dir recovered --repository octocat/terrarium --remote "$REMOTE" --expected-parent "$(git ls-remote "$REMOTE" refs/heads/output | cut -f1)"
python -m github_terrarium restore --repository octocat/terrarium --remote "$REMOTE" --from-commit "$(git --git-dir="$REMOTE" rev-parse output~1)" --expected-parent "$(git ls-remote "$REMOTE" refs/heads/output | cut -f1)"
git --git-dir="$REMOTE" log --oneline output
```

Pass `--remote` as an absolute path, because publication runs Git in a temporary directory.
Missing or corrupt state is refused, never replaced: each of these exits 1 with one error line and leaves its inputs unchanged.

```bash
printf '{}' > corrupt.json
python -m github_terrarium grow --snapshot bounded.json --state corrupt.json > out.json || echo "refused: exit $?"
python -m github_terrarium grow --snapshot bounded.json --state missing.json > out.json || echo "refused: exit $?"
```

The same refusal applies to an `output` branch that exists without a valid bundle: `generate`, `publish`, and `restore` fail without resetting it.
Return to the checkout root and remove `work/recovery/` when done.

## Planned experience

- A personal terrarium with a stable layout that grows over time.
- Public GitHub activity mapped to five visual traits and persistent growth.
- Gentle SVG animation that plays inside a GitHub profile README without JavaScript.
- Daily GitHub Actions generation, with images and growth state committed together to an `output` branch.
- A calm resting state during inactivity, with no loss of earned growth.

## Documentation

| Document | Contents |
| --- | --- |
| [Product specification](docs/specs/terrarium.md) | Scope, metric definitions, visual behavior, scoring, and acceptance criteria |
| [Technical design](docs/specs/architecture.md) | Collection, persistent state, SVG rendering, daily publication, and failure recovery |
| [Implementation plan](docs/plans/implementation.md) | Ordered milestones, intended files, tests, and release gates |
| [Contribution guide](CONTRIBUTING.md) | Current workflow and project boundaries |
| [Verification notes](docs/notes/) | Dated evidence for collection, growth, rendering, validation, the gallery, and publication |

## Repository layout

```plaintext
main
├── AGENTS.md
├── CONTRIBUTING.md
├── README.md
├── pyproject.toml
├── terrarium.toml
├── assets/
│   ├── references/   # unchanged design reference
│   └── terrarium/    # packaged SVG pieces (github_terrarium.art)
├── docs/
│   ├── notes/        # dated verification evidence
│   ├── plans/
│   └── specs/
├── src/github_terrarium/
├── tests/
└── tools/            # asset extraction, the bundle regression, and the browser fixture gallery
```

The `output` branch contains `terrarium.svg`, `state.json`, and `manifest.json` at its root.
The first validated bootstrap publication created it on 2026-11-17.
The daily schedule is 00:23 UTC (09:23 Asia/Seoul), subject to GitHub scheduling delays.

## License

Source code and original artwork are released under the [MIT License](LICENSE).
Artwork provenance is recorded in [the asset notes](assets/terrarium/README.md).
