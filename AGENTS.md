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

- This repository has a complete read-only public collector and local persistent-growth reconciliation; do not claim a working terrarium generator or daily scheduled workflow.
- Keep durable source and documentation on `main`; publish generated images and growth state together on `output` after implementation.
- Treat incomplete collection as failure, never as zero activity.
- Keep scoring and rendering deterministic, and prevent repeated runs from earning duplicate growth.
- Collect public activity only in v1 and exclude this repository's automated activity from scoring.
- Preserve output history; never force-push generated state or silently reset an existing habitat.
- Keep technical documentation and identifiers in English; preserve intentional localized product strings.

## Verification

For documentation changes, check relative links, examples, and `git diff --check`.
Run `python -m unittest discover -s tests -v`, `ruff check src tests`, and `ruff format --check src tests` in the installed Python 3.12 environment.
The `probe`, `collect`, and offline `grow` commands exist; build, validate, and publish remain planned.
