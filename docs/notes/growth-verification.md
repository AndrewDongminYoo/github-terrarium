# Persistent Growth Verification

Date: 2026-11-15.
Scope: local state reconciliation on `feat/persistent-growth`, following merged collection commit `07049f1`.

## Implemented behavior

The offline `grow` command reconciles validated snapshots against a prior state or an explicit 30-day bootstrap.
Daily activity awards preserve already-earned XP; popularity uses repository-ID high-water marks and observation-day caps.
The first observation of an ID establishes a baseline, and missing repositories retain their watermarks.
State validation enforces date continuity, versions, counts, derived activity totals, UTF-8 JSON, duplicate-key rejection, and the 2 MiB limit.
Long gaps use explicit batches with a fixed cutoff, without invented popularity history.

## Regression evidence

All 49 offline tests, Ruff lint, and formatting checks passed locally.
The suite verifies the 39/11 XP examples, 115/90 daily caps, every stage boundary, deterministic replay, late corrections, decreasing metrics, new/reappearing repository IDs, user renames, recovery, malformed state, and CLI failure preservation.
Five persisted synthetic personas also pass state validation and trait bounds.

The repository-rename regression starts with 10,000 stars as an uncredited baseline, adds three stars for 6 XP, then changes the repository name three times while retaining ID `R1`.
The total stays at 6 XP and only one watermark exists.
This covers renames through collection normalization and growth reconciliation together.

## Local review and repairs

Two read-only local reviews examined growth/state logic and validation/CLI coverage separately.
Review found that ordinary updates accepted older-than-required collection intervals; normal updates now require the exact refresh interval, while explicit recovery permits deliberate older corrections.
Review also found automatic UTF-16 decoding and an extreme-date bootstrap overflow; explicit UTF-8 decoding and duration-based bootstrap validation now reject those inputs cleanly.
Regression tests cover all three repairs; the root reran the full suite after the fixes.
No remote review or PR was requested.

## Remaining scope

State validation checks internal consistency, not authenticity of arbitrary edited histories; publication will add coherent bundle hashes and remote-parent checks.
Rendering, output publication, and the daily schedule remain unimplemented.
Growth constants remain version-one design defaults pending fixture-gallery calibration.
