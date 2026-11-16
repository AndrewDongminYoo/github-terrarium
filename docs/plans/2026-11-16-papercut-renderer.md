# Paper-cut renderer implementation plan

Goal: port the approved container-free paper-cut reference into `render(state) -> bytes` while preserving deterministic growth and ambient motion contracts.
Scope approved by the operator on 2026-11-16: publish the art-direction/reference PR, then proceed with the renderer port.
Spec: [product specification](../specs/terrarium.md), especially the six paper-cut rules, two timescales, motion and acceptance budgets.
Reference: [unchanged Sanctuary SVG](../../assets/references/terrarium-papercut-sanctuary.svg).

## Architecture and ownership

- `assets/terrarium/papercut.svg`: reusable named vector pieces and static landscape layers derived from the supplied reference; no baked user/date/scoring labels.
- `src/github_terrarium/render.py`: unchanged public API and strict state validation; assemble pieces using explicit stage scales, independent feature salts, bounded trait slots, canonical XML and renderer version 3.
- `tests/test_render.py` and `tests/test_motion.py`: adapt scene expectations and add art, stage, identity, independent-trait and resource regressions.
- `assets/terrarium/README.md`, README, technical design and milestone status: record source provenance and actual renderer behavior.
- A dated verification note records observed comparison/motion evidence and outstanding browser limits.

The source reference is not edited and is not loaded at runtime.
Package resources remain standard-library based; introduce no runtime dependency.
No scoring/state/seed-version migration, collection change, CLI expansion, validator, publisher or workflow integration is included.

## Decisions within the approved direction

Preserve the reference's four distant ridge layers, left pond, right tree, mossy ground, exposed roots and dark foreground.
Keep background and terrain independent of recent traits; subject-ID salts vary fixed placement without global RNG coupling.
Stage scales around the tree/root anchor are 0.18, 0.32, 0.55, 0.8 and 1 for Seed through Sanctuary; permanent canopy counts increase from 2 to 13 pieces.
PR traits add at most six canopy pieces; fork traits add at most six branches and six seedlings; stars add flowers/fireflies; reviews add pond detail/creatures; issues add mushrooms/ground cover.
Only canopy pieces, fireflies and ripples animate, within 40 groups; calm/reduced-motion CSS remains independent of scene geometry.
Keep identity/date labels legible at 360 pixels, preserve long-login bounds, and reserve the upper label band from the canopy.

## Ordered work

- [x] Extract and name reusable source pieces; build provisional low-activity and saturated comparison SVGs in the visible review directory and inspect them before replacing `render.py`.
- [x] Write focused failing tests for container-free composition and permanent growth; retain dynamic-label and independent-trait regressions, and check flat silhouettes, reused shadows, and the three allowed gradients.
- [x] Replace the vessel renderer with deterministic scene assembly; preserve strict state validation and motion helpers, increment renderer version to 3.
- [x] Run existing persona/stage/saturation/rename/fresh-process/motion tests and new regressions; fix affected documentation in the same change.
- [x] Render all personas and stages, including low/high side-by-side captures at 360 and 900 pixels; inspect actual HTML-image motion, browser-level reduced motion and no-CSS frames.
- [ ] Complete a large-scope independent code/asset review and adversarial cross-check; commit, push and open a separate renderer PR; finish technical gates before requesting operator visual approval.

## Verification and review focus

Run `python -m unittest discover -s tests -v`, `ruff check src tests`, `ruff format --check src tests`, documentation relative-link/example checks and `git diff --check` under Python 3.12.
Build/install a wheel and prove renderer/resource behavior outside the source checkout.
Require at most 200 KiB, 1,200 elements, 40 animated groups, exactly the allowed sky/light/firefly gradient families, local fragment references, and no filters/scripts/external images.
Check zero data remains a complete scene; growth changes height, trunk/canopy/root spread without depending on browser time.
Check stage/cap boundaries and maximal combined traits do not clip labels or rearrange unrelated slots.
Check login rename preserves geometry; invalid or incomplete state fails before rendering; a changed subject changes seeded variation.
Compare time-separated frames through HTML images and preserve the known Chromium DevTools reduced-preference propagation limitation; use the process-level preference and a no-CSS control.
WebKit and real GitHub README playback remain explicit gaps until actually exercised; this port does not complete the full #12 matrix or #13 approval.
Observed checks and their limits are recorded in [port verification](../notes/papercut-renderer-verification.md).
