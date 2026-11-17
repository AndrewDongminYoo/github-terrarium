# Project Guide

## Identity and purpose

Canonical project ID: `github-terrarium`.
Personal-account repository: `AndrewDongminYoo/github-terrarium`.
Generate a personalized, animated SVG terrarium from public GitHub activity and preserve its growth across daily GitHub Actions runs.

## Start here

- Read [README.md](README.md) for the current implementation status.
- Read [the product specification](docs/specs/terrarium.md) for behavior and acceptance criteria.
- Read [the technical design](docs/specs/architecture.md) for data, state, rendering, and publication contracts.
- Follow [the implementation plan](docs/plans/implementation.md) for ordered work and verification.

## Boundaries

- This repository has a complete read-only public collector, local persistent-growth reconciliation, `render`/`validate_svg` Python APIs, offline output-bundle build/validation, a low-level `publish` command, a `generate` command that publishes with one conflict recollection, and a guarded `generate.yml` workflow; do not claim published live output or a verified scheduled run.
- Keep durable source and documentation on `main`; publish generated images and growth state together on `output` after implementation.
- Treat incomplete collection as failure, never as zero activity.
- Keep scoring and rendering deterministic, and prevent repeated runs from earning duplicate growth.
- Collect public activity only in v1 and exclude this repository's automated activity from scoring.
- Preserve output history; never force-push generated state or silently reset an existing habitat.
- Keep technical documentation and identifiers in English; preserve intentional localized product strings.

## Verification

For documentation changes, check relative links, examples, and `git diff --check`.
Run `python -m unittest discover -s tests -v`, `ruff check src tests tools`, and `ruff format --check src tests tools` in the installed Python 3.12 environment.
The `probe`, `collect`, offline `grow`, `build`, `validate`, `publish`, and `generate` commands exist; publisher and generator tests use local bare remotes and fake collectors.
