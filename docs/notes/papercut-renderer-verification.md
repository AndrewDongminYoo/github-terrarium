# Paper-cut renderer port verification

Verified locally on 2026-11-16 with Python 3.12.16 and Chromium 157.0.8103.38 on macOS.
This ports the approved reference into renderer version 3; it does not complete the independent SVG validator, full browser matrix, publication, or operator approval of generated scenes.
The public README's fixed reference banner was separately reviewed and merged in [PR #34](https://github.com/AndrewDongminYoo/github-terrarium/pull/34).
That banner is not generated output.

## Automated contracts and packaging

The 67-test suite passed with `python -m unittest discover -s tests -v`.
`ruff check src tests tools`, `ruff format --check src tests tools`, relative documentation links, and `git diff --check` passed.
Existing stage/cap boundaries, state rejection, login rename, fresh-process determinism, independent traits, seven-day calm selection, and static geometry contracts remain covered.
Two new regressions cover container-free composition and permanent tree/root growth independent of landscape and recent traits.
The new paper-cut assertions failed against the vessel renderer before implementation.

The extractor reproduced the packaged asset byte-for-byte and rejected a modified reference.
The source reference's SHA-256 remains `f87b93c4b6def040906347b1ab690413f6dddd5d03112218c04941038a5264e9`.
A built wheel was installed without dependencies into a fresh Python 3.12 environment; isolated rendering outside the checkout matched the source renderer's saturated output byte-for-byte.

| Scene | SVG bytes | XML elements | Animated groups |
| --- | --- | --- | --- |
| Empty Seed | 95,571 | 328 | 2 |
| Popularity-heavy | 100,102 | 416 | 10 |
| PR-heavy | 97,986 | 374 | 16 |
| Review-heavy | 98,086 | 372 | 13 |
| Issue-heavy | 97,916 | 369 | 4 |
| Saturated Sanctuary | 106,722 | 533 | 33 |
| Saturated, 39-character login | 106,835 | 533 | 33 |

Every measured scene stays within 200 KiB, 1,200 elements, and 40 animation groups.
Two independent read-only reviews found no blockers in runtime contracts or asset extraction/provenance.
Additional combinations checked determinism, unique IDs, local fragments, and budgets across stages and trait combinations; these are structural checks, not browser compatibility evidence.

## Rendered observations

Individual HTML image captures cover all five fixture personas, five stage thresholds, saturated traits, and a 39-character login at 360 and 900 CSS pixels.
The low/high comparisons retain the pond, terrain, ridges, and foreground while tree/root scale and trait slots change.
The opaque canvas stays complete at both widths; no scene clipping or label overlap was observed in these captures.
An inline equivalent measured the long identity at x=26 with width 620 and the Sanctuary label starting at x=760.203125, leaving a horizontal gap.
This measurement supplements the actual image captures; an inline SVG is not a substitute for image playback verification.

Time-separated 900-pixel HTML-image captures changed 9,143 pixels in active mode and 9,052 in calm mode, with zero changes in the measured identity/date/stage label regions.
These counts demonstrate motion, not a calibrated intensity or frame-rate comparison.
The no-CSS control had zero changed pixels over time.
A separate isolated Chromium launch with `--force-prefers-reduced-motion` also had zero changed pixels and matched the no-CSS image exactly.
The setup follows the [previous motion verification](motion-verification.md#reduced-motion-test-setup), which records why parent-page DevTools emulation alone is insufficient in this browser.

## Remaining gates

Generated output has not been tested in a public GitHub README; only the unchanged reference banner has.
WebKit, the full 360/768/900 light/dark browser matrix, performance calibration, and the independent malicious-SVG validator remain open.
Local comparison captures and active/calm/reduced recordings are retained for operator review; the reference approval does not approve this generated gallery automatically.
No collector, growth/scoring/state/seed version, CLI, publisher, or workflow behavior changed.
