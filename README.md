# GitHub Terrarium

![Animated paper-cut terrarium design sample](assets/references/terrarium-papercut-sanctuary.svg)

**Design preview:** This fixed animated SVG sample uses synthetic data and is not generated from live GitHub activity.

A small living world shaped by your GitHub activity.
Stars bring flowers and fireflies, forks spread seedlings, pull requests grow plants, reviews enrich a pond, and issues add mushrooms.

**Status: public collection, persistent growth, and animated SVG rendering implemented.**
A paginated public collector, local growth-state reconciliation, read-only API probe, and offline checks are implemented.
The paper-cut SVG renderer, bounded ambient motion, and offline SVG validator are available as Python APIs, and offline `build`/`validate` commands produce and check the three-file output bundle; the full browser gallery and publication remain planned.
No generated image publication or daily workflow is available at this stage.

## Run the collection probe

Use Python 3.12 or later.
The package has no third-party runtime dependencies; Ruff is a pinned development-only checker.

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
ruff check src tests
ruff format --check src tests
```

The CI workflow is prepared to run these checks and a read-only workflow-token probe on trusted pushes.
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
Once publication exists, bootstrap will additionally require an absent remote output branch; this local command alone does not authorize a remote reset.
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
The `build` command below renders through this API; publication is not included yet.

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
└── tools/            # authoring-time asset extraction
```

The planned `output` branch will contain `terrarium.svg`, `state.json`, and `manifest.json`.
It will be created by the first validated publication, not by this documentation bootstrap.
The planned default schedule is 00:23 UTC each day (09:23 Asia/Seoul), subject to GitHub scheduling delays.

## License

A license has not been selected yet.
