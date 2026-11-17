# Public README render verification

Date: 2026-11-17, observed from 19:13:09Z to 19:14:30Z.
Scope: the generated terrarium as rendered in the public repository README at <https://github.com/AndrewDongminYoo/github-terrarium>, for [issue #28](https://github.com/AndrewDongminYoo/github-terrarium/issues/28).
Source: `main` at `5e226b5` (the README embed from PR #55); published output: `output` at `caceb5d`, built from `701ebb5` ([publication verification](2026-11-17-publication-verification.md)).

## Method

The milestone 4 browser harness (Playwright for Python 1.65.2) stood in for the `agent-browser` session named in the implementation plan's GitHub README smoke scenario; isolation came from a fresh, signed-out context per cell.
Each cell opened the repository page in its own context, waited for network idle and for the README `img` whose `src` is the stable URL to finish loading, scrolled it into view, and took two element screenshots at least 2.0 seconds apart (measured 2.09–2.15 s).
Frames were compared with the fixture gallery's PNG decoder and motion verdict (`compare` and `motion_verdict` in [`tools/gallery.py`](../../tools/gallery.py)): normal motion must change pixels outside the identity, freshness, and stage text regions, and reduced motion must change none.
Reduced motion used `reduced_motion="reduce"`, plus `--force-prefers-reduced-motion` at Chromium launch, as in the [fixture gallery](fixture-gallery-verification.md).
Each cell also read the image box, the viewport width, the document `scrollWidth` and `clientWidth`, and the computed body background.

| Item | Value |
| --- | --- |
| Host | the macOS host recorded in the fixture gallery note, headless |
| Chromium | 159.0.8154.6 |
| WebKit | 27.2 |
| Viewport | widths 360 and 900 CSS pixels, height 900, device scale factor 1 |
| Host theme | `color_scheme` light (body `rgb(255, 255, 255)`) and dark (body `rgb(13, 17, 23)`) |

## Rendered image

GitHub rendered the embed as an `img` whose `src` is the stable URL `https://raw.githubusercontent.com/AndrewDongminYoo/github-terrarium/output/terrarium.svg` itself, with no proxy rewrite, and with the alt text from the README.
The image loaded with a natural size of 300 × 120 and displayed at 294 × 118 CSS pixels at width 360 and 538 × 215 at width 900, ending at x = 327 and x = 587 respectively.
In every cell the document `scrollWidth` equalled its `clientWidth` (360 and 900), so the image caused no horizontal overflow.

The image label reads `Activity through 2026-11-16 UTC`, which equals `complete_activity_day` in the published `manifest.json`; the identity line `AndrewDongminYoo / terrarium` and the stage `Mature` are readable, and the whole vessel is visible at both widths.

| Capture | Width | Theme |
| --- | --- | --- |
| [chromium-360-light.png](assets/2026-11-17-readme/chromium-360-light.png) | 360 | light |
| [chromium-360-dark.png](assets/2026-11-17-readme/chromium-360-dark.png) | 360 | dark |
| [chromium-900-light.png](assets/2026-11-17-readme/chromium-900-light.png) | 900 | light |
| [chromium-900-dark.png](assets/2026-11-17-readme/chromium-900-dark.png) | 900 | dark |

These four viewport captures show the README context in normal motion; the other captures stayed local, and the motion comparison is recorded by count below.

## Motion

| Engine | Width | Theme | Normal: changed pixels | Reduced: changed pixels | Text regions changed |
| --- | --- | --- | --- | --- | --- |
| Chromium | 360 | light | 1,863 | 0 | none |
| Chromium | 360 | dark | 1,982 | 0 | none |
| Chromium | 900 | light | 5,481 | 0 | none |
| Chromium | 900 | dark | 5,504 | 0 | none |
| WebKit | 360 | light | 1,991 | 1,973 (pending) | none |
| WebKit | 360 | dark | 1,995 | 1,967 (pending) | none |
| WebKit | 900 | light | 5,728 | 5,725 (pending) | none |
| WebKit | 900 | dark | 5,748 | 5,764 (pending) | none |

Chromium passes every cell: normal motion moves only ambient pixels, and reduced motion keeps the full scene with no changed pixel.
WebKit passes normal motion; its reduced-motion cells are **pending**, not failed, because Playwright's reduced-motion emulation does not reach an SVG inside `img` in WebKit, the same harness limit the fixture gallery records.

## Not verified

- WebKit reduced motion through `img`, as above.
- Signed-in GitHub views, Firefox, mobile browsers, and real devices; this note claims no compatibility beyond the cells above.
- Freshness after a later publication, which is [issue #29](https://github.com/AndrewDongminYoo/github-terrarium/issues/29).
