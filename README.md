# GitHub Terrarium

A small living world shaped by your GitHub activity.
Stars bring flowers and fireflies, forks spread seedlings, pull requests grow plants, reviews enrich a pond, and issues add mushrooms.

**Status: public collection and persistent growth implemented.**
A paginated public collector, local growth-state reconciliation, read-only API probe, and offline checks are implemented.
Artwork and the daily publishing workflow are not implemented yet.
No generated image or live preview is available at this stage.

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
├── README.md
├── CONTRIBUTING.md
└── docs/
    ├── plans/implementation.md
    └── specs/
        ├── architecture.md
        └── terrarium.md
```

The planned `output` branch will contain `terrarium.svg`, `state.json`, and `manifest.json`.
It will be created by the first validated publication, not by this documentation bootstrap.
The planned default schedule is 00:23 UTC each day (09:23 Asia/Seoul), subject to GitHub scheduling delays.

## License

A license has not been selected yet.
