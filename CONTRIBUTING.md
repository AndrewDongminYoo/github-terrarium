# Contributing

This repository has a read-only paginated public collector, an offline persistent-growth engine, and an SVG rendering API with bounded ambient motion, an offline SVG validation API, offline output-bundle `build`/`validate` commands, a low-level `publish` command for the `output` branch, and a `generate` command that connects them with one conflict recollection.
Start with the [implementation plan](docs/plans/implementation.md) and its linked contracts before adding code.

## Changes

- Keep each change focused on one milestone or independently reviewable concern.
- Update affected specifications when behavior changes.
- Use synthetic public-data fixtures; never commit tokens or private repository data.
- Do not copy code or artwork from another repository without checking its license.
- Contributions are accepted under the [MIT License](LICENSE).
- Keep `output` reserved for generated files; edit generators on `main`.

## Verification

Documentation changes require valid relative links, consistent examples, and `git diff --check`.
Install the package and development tools as described in README.md.
Run the unit tests, Ruff lint, Ruff formatting checks, and `python tools/ci_bundles.py` before submitting code; CI runs them and the fixture gallery on every pull request.
Tests are offline; live API collection is a separate verification step and runs in CI only on `main`, as the [GitHub Actions boundary](docs/specs/architecture.md#github-actions-boundary) defines.
Future runtime verification is described in the implementation plan and must not be reported as passing until implemented and run.

## Commits

Use concern-based Conventional Commits and explicit staging paths.
Preserve existing hooks and review the complete staged diff before committing.
