# Fixture gallery verification

Verified locally on 2026-11-16 for issue #12 with `tools/gallery.py`, Playwright for Python 1.65.2, and Python 3.12.16.
This note is the evidence index for the visual review in issue #13; it does not approve the visual direction.
The captures are not committed: they are written under the ignored `work/gallery/` directory and are reproduced with the commands below.

## Commands

```bash
python -m pip install --require-hashes -r requirements-dev.txt
python -m playwright install chromium webkit
python tools/gallery.py build
python tools/gallery.py check
```

`build` is offline and writes the fixture SVGs, `index.html`, negative-control pages, and `fixtures.json` to `work/gallery/`.
`check` serves that directory on a loopback HTTP server, runs Chromium and then WebKit (one browser process at a time), writes `results-<engine>.json` and PNG captures under `work/gallery/captures/`, and closes every browser and the server.
It exits 1 when any cell fails, including when a negative control passes.

## Host and engines

| Item | Value |
| --- | --- |
| Host | Apple M4, 10 logical CPUs, 16 GiB memory, macOS 26.7.3 arm64 (`macOS-26.7.3-arm64-arm-64bit`) |
| Chromium | 159.0.8154.6, Playwright's default headless binary `chromium_headless_shell-1255` |
| WebKit | 27.2, Playwright build `webkit-2388`, headless |
| Viewport | widths 360, 768 and 900 CSS pixels, height 900, device scale factor 1 |
| Host backgrounds | `color_scheme` light (`#ffffff`) and dark (`#0d1117`); a cell fails unless the computed body background is `rgb(255, 255, 255)` or `rgb(13, 17, 23)` respectively |
| Motion | normal: `reduced_motion="no-preference"`; reduced: `reduced_motion="reduce"`, plus `--force-prefers-reduced-motion` at Chromium launch |
| Frame interval | at least 2.0 seconds between the end of the first capture and the start of the second; measured 2.0–5.28 s in Chromium and 2.0–6.2 s in WebKit (per image, from one run) |

Linux Chromium and Linux WebKit cells are **pending**: they belong to issue #18 and were not run here.

## Fixtures

All thirteen gallery states are grown by `github_terrarium.growth.advance` from snapshots (no edited state), rendered by `render`, and accepted by `validate_svg`.

| Fixture | Stage | Motion | Bytes | Elements | Animated groups | SHA-256 (prefix) |
| --- | --- | --- | --- | --- | --- | --- |
| `persona-empty` | seed | calm | 95,571 | 328 | 2 | `8412623bfaed` |
| `persona-popularity` | seed | calm | 100,102 | 416 | 10 | `15c3f57fc235` |
| `persona-pull-requests` | mature | active | 97,986 | 374 | 16 | `cc70c42f7e27` |
| `persona-reviews` | grove | active | 98,086 | 372 | 13 | `0118d2e3a98b` |
| `persona-issues` | sprout | active | 97,916 | 369 | 4 | `f9a5b1e4d9f2` |
| `stage-seed` | seed | active | 99,414 | 398 | 6 | `92576a5a7992` |
| `stage-sprout` | sprout | active | 99,446 | 398 | 14 | `5df321ceab38` |
| `stage-grove` | grove | active | 99,316 | 399 | 17 | `7b10ffb8aaeb` |
| `stage-mature` | mature | active | 99,816 | 410 | 20 | `72330f908fff` |
| `stage-sanctuary` | sanctuary | active | 104,021 | 481 | 29 | `24300bb3d400` |
| `richest` | sanctuary | active | 106,722 | 533 | 33 | `e10f406624c8` |
| `renamed` | sprout | active | 98,947 | 389 | 14 | `9a22ecd402ff` |
| `calm` | grove | calm | 99,314 | 399 | 17 | `8e4ad6d97a27` |

`richest` saturates all five traits at Sanctuary; `renamed` keeps subject `U1` under a 33-character login, which exercises the long-label path at 360 pixels; `calm` has seven completed zero-activity days.
Full hashes are in `work/gallery/fixtures.json`, and a repeated `build` is byte-identical (unit-tested).

## Assertions and controls

Every cell loads `index.html`, waits for each `img` to decode, and asserts no horizontal page overflow, every image inside the viewport, no clipping ancestor, and a whole image at the 900:360 ratio.
Each image is captured twice; normal motion requires changed pixels outside the identity, freshness and stage-label regions and zero changed pixels inside them, and reduced motion requires identical captures.
The identity region spans viewBox x 20–650, so it covers the 620-unit stretched label that the renderer draws for a login longer than 20 characters (the `renamed` fixture); a unit test ties the region to that rendered label.
No negative control moves text, so the text-region assertion is shown to fail only by the unit test of `motion_verdict`, not in a browser.

The same cell runs negative controls, and the cell fails if a control passes:

- `control-overflow.html` (a 1200-pixel image) failed the overflow and viewport assertions in all 24 cells.
- `control-clipped.html` (a 40-pixel `overflow: hidden` figure) failed the clipping assertion in all 24 cells.
- `control-static.svg` (the richest SVG without its stylesheet) produced identical frames and failed the normal-motion assertion in all 12 normal cells.
- `control-reduced-ignored.svg` (the richest SVG without its reduced-motion rule) kept moving and failed the reduced-motion assertion in all 6 Chromium reduced cells, which proves the assertion can fail there.
  In the 6 WebKit reduced cells every image keeps moving (see below), so this control also fails there but cannot tell a broken SVG from a working one and proves nothing for those cells.

## Results

| Engine | Motion | Cells | Status | Changed pixels per image (min–max over fixtures) | Text-region changes |
| --- | --- | --- | --- | --- | --- |
| Chromium | normal | 6 | passed | 7–4,088 at 360; 52–14,194 at 768; 81–18,514 at 900 | 0 |
| Chromium | reduced | 6 | passed | 0 | 0 |
| WebKit | normal | 6 | passed | 26–4,204 at 360; 139–14,563 at 768; 169–18,035 at 900 | 0 |
| WebKit | reduced | 6 | **pending** | 24–18,103 (images still move) | 0 |

The smallest normal-motion change belongs to `persona-empty`, whose two canopy groups are the only animated groups.
Pixel counts show that motion was observed through `img`; they are not an intensity or performance measure.

WebKit reduced motion is pending, not passed.
The host page reports `prefers-reduced-motion: reduce` in every reduced cell, and in one separate probe at a 900-pixel viewport a direct navigation to the richest SVG stopped moving, but the SVG inside `img` keeps animating under Playwright's emulation.
Only Playwright's context emulation was tried; no WebKit launch-level override was found or tested, and no operating-system preference was changed for this run.
The tool declares this cell pending with that reason; it still records the captures and fails the cell if the host page does not receive the preference.
Whether WebKit propagates a real operating-system reduced-motion setting into `img` SVG remains unverified.

## Richest-fixture measurements

| Measurement | Value |
| --- | --- |
| Dimensions | `viewBox="0 0 900 360"`, shown at 328×131.2 (360 width), 736×294.4 (768) and 868×347.2 (900) CSS pixels |
| SVG bytes | 106,722 |
| Elements | 533 |
| Animated groups | 33 (leaf sway, firefly travel, pond ripple) |
| `render()` time | 1.85 ms median of 7 runs in CPython 3.12.16 |
| `img` load and decode | Chromium 3.3 ms, WebKit 9 ms; median of 7 cache-busted loads from loopback at a 900-pixel viewport |

These numbers come from one headless run on the host above; they do not establish a frame rate or a device-independent rendering cost.

## Limits

- Linux engines and CI integration remain issue #18.
- WebKit reduced motion through `img` is pending as described above.
- Visual approval of the scenes remains issue #13.
- Captures cover headless engines driven by Playwright, not GitHub's README image proxy; milestone 7 owns that smoke scenario.
