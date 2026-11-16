# Offline SVG validation verification

Verified locally on 2026-11-16 under Python 3.12.16 for issue #11.
`validate_svg(bytes)` is an explicit offline API, not a sanitizer, automatic renderer hook, bundle validator or CLI.
It accepts the current generator's constrained SVG grammar and rejects unsupported content with `ValueError`.
The implementation uses no new dependency and changes no renderer, artwork, state, scoring or seed inputs.

## Negative-first evidence

The initial validator was a no-op; its negative suite reported 19 expected missing-rejection failures before implementation.
Subsequent review identified numeric-list parsing that wrongly accepted compact transform/viewBox forms and test shapes placed where child-placement checks masked geometry checks.
Corrected fixtures reached the intended geometry/reference branches, and new separator regressions failed before the parser repair.
Path data retains its valid compact-number grammar; transform arguments and viewBox require explicit comma or ASCII-whitespace separators.
The root adversarial pass also exposed a quadratic unanchored search on a long malformed transform name.
A 180,000-character malformed name within the byte budget timed out at five seconds before the fix; a forward-cursor matcher now passes the bounded subprocess regression.
This guards a specific denial-of-service input, not a universal parsing-performance promise.

## Coverage

The unit corpus covers invalid bytes/XML, conflicting encodings and UTF-16/32 autodetection, root/namespace/viewBox errors, DTD/internal/external entities, processing instructions, foreign elements, events and namespaced attributes.
CSS tests cover imports, escapes, fonts, URLs, extra selectors, hidden-text rules, new animation declarations and malformed delays.
Reference tests cover nonlocal schemes, encoded scheme text, alternate namespace attributes, duplicate/unresolved/wrong-type IDs, cycles, reuse expansion and animated definitions.
Geometry tests cover malformed commands, arities, arc flags, negative radii, nonfinite/excessive numbers, invalid separators and transform names.
Metadata tests reject empty accessible text, missing or hidden identity groups, misplaced labels, zero-size text and invalid dates/stages.
Positive fixtures cover five personas, all five stages, saturated traits, calm mode, XML-special subject IDs, a 39-character login and CSS-free static output.
Exact 200 KiB / 1,200-element / 40-animation limits pass; limit-plus-one inputs fail.
The 32-level nesting boundary passes and level 33 fails during construction.
Actual selector matching is counted without relying on the `ambient` helper class; absent CSS assigns no animation.
With CSS present, animated groups require `ambient` on themselves or an ancestor; a negative-first regression and a forced-reduced browser probe confirmed the unguarded family-only case before the repair.
Tests replace socket construction and URL opening with failures while validating safe and malicious XML inputs.

Run `python -m unittest discover -s tests -v`, `ruff check src tests`, `ruff format --check src tests`, changed-document link/anchor checks and `git diff --check`.
All 81 unit tests, Ruff checks, changed-document relative targets/anchors and the bounded-read README example passed locally.
A fresh wheel installation outside the source checkout accepted generated output and matched the source renderer's SHA-256; the renderer/artwork/growth/state files are unchanged.
Two independent reviews found numeric-separator and fixture-reachability defects; both were repaired and independently revalidated, followed by scoped revalidation of the bounded transform matcher.
The [Python XML API](https://docs.python.org/3.12/library/xml.etree.elementtree.html) documents the tree-builder callbacks used to reject DTDs and processing instructions.
The [SVG transform grammar](https://www.w3.org/TR/SVG11/coords.html#TransformAttribute) distinguishes numeric-list separators from compact path data.

## Boundaries

Only the exact trusted ambient CSS or its absence is accepted, with finite inline animation delays; the validator does not interpret arbitrary CSS or optimize SVG.
Labels are checked structurally against the current renderer's visible placement/attributes; perceptual contrast, overlap, accumulated affine extents and full browser behavior remain gallery responsibilities.
Nesting is capped at 32, numeric magnitudes at 1,000,000 and conservative reference expansion at 10,000 nodes, in addition to the product's byte/element/animation budgets.
The checked-in source reference and arbitrary historical artwork are not supported generator-output formats.
Oracle lookup found no directly applicable project precedent for SVG security/CSS grammar: `[no precedent found]`; the policy follows issue #11 and the current renderer contract.
