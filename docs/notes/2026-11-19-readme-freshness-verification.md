# README Freshness Verification

Date: 2026-11-19, observed at 00:24Z and 07:37Z.
Scope: whether the public README shows a later publication through the unchanged stable image URL, for [issue #29](https://github.com/AndrewDongminYoo/github-terrarium/issues/29).
Baseline: the README embed and stable URL from the [README render verification](2026-11-17-readme-render-verification.md), and `output` at `b927495` from the [scheduled transition verification](2026-11-18-scheduled-transition-verification.md).

## Method

Each observation opened <https://github.com/AndrewDongminYoo/github-terrarium> in a fresh, signed-out Chromium 159.0.8154.6 context (Playwright for Python 1.65.2) at 360 × 900 CSS pixels, light host theme, no reduced motion, and device scale factor 1.
It waited for the README `img` whose source is the stable URL to load, saved an element screenshot, and recorded the image response the browser itself received: HTTP status, SHA-256 of the body, the `Activity through … UTC` label in that body, and the `etag`, `cache-control`, and `x-cache` headers.
A background loop checked the `output` ref with `git ls-remote` every 60 seconds; once the ref moved, it repeated the observation every 60 seconds until the label changed.
No query string, alternate URL, or cache purge was used.

The README image source is `https://raw.githubusercontent.com/AndrewDongminYoo/github-terrarium/output/terrarium.svg` itself, with no camo proxy, as the earlier render note recorded; its responses carried `cache-control: max-age=300`.

## Later publication

[Run 44480853117](https://github.com/AndrewDongminYoo/github-terrarium/actions/runs/44480853117), `event` `schedule`, attempt 1, was created at 2026-11-19T07:35:56Z, 7 h 13 min after the 00:23Z cron time; its `generate` job succeeded from 07:35:59Z to 07:37:04Z from `main` at `12333c7`.
It published `output` `cee9c449916a8a3ff5951bbed577bb1274df271f` (parent `b927495`), "Publish terrarium through 2026-11-18", committed at 07:36:58Z, with `xp_delta` 60.

A fresh single-branch clone showed that commit and passed `python -m github_terrarium validate --bundle-dir <clone>` (exit 0).

| File at `cee9c44` | `shasum -a 256` |
| --- | --- |
| `manifest.json` | `2becdf9a3aef41630dacf020f9a2258152aece693193d38872fd269df111c258` |
| `state.json` | `a51d7e143ab9a5c67f282bedcb23845aa2d826f1dcd61f8faeee460a3c265538` |
| `terrarium.svg` | `4d3367faae44c711ee1ee4151958e942360d1274b3e05dc0ab6e7ae1987b3a60` |

The manifest records `complete_activity_day` 2026-11-18 and `stock_observation_day` 2026-11-19, and the SVG label reads `Activity through 2026-11-18 UTC`.

## Observations

| Observed (UTC) | Image SHA-256 | Label | `x-cache` | `etag` | Capture |
| --- | --- | --- | --- | --- | --- |
| 00:24:18 | `b8e946e0…e3c2d9c5` (`b927495`) | 2026-11-17 | `HIT` | `W/"29be6d57…c4488a57"` | [before](assets/2026-11-19-freshness/before-0024Z-chromium-360-light.png) |
| 07:37:53 | `4d3367fa…987b3a60` (`cee9c44`) | 2026-11-18 | `MISS` | `W/"d182c119…dbb0054a"`[^etag] | [after](assets/2026-11-19-freshness/after-0737Z-chromium-360-light.png) |

[^etag]: The full value is `W/"d182c1193296fa418e8d8fe0e227ebd137efd3394c19a1b98ba4d72fdbb0054a"`; it is shortened in the table only.

The loop saw the `output` ref move at 07:37:52Z, and the first README observation after that, at 07:37:53Z, already received the new SVG, whose hash equals the manifest value.
So the new label was visible through the unchanged stable URL at most 55 seconds after the output commit time (07:36:58Z) and on the first reload after publication; no older label was observed after publication.
The response was a cache `MISS`, so this observation did not show the 300-second `max-age` delaying the change.

## Conclusion

Freshness through the stable URL is observed for one later publication: a fresh signed-out page showed the new complete-activity label within 55 seconds of the output commit, without changing the embed.
This is one observation in one browser context; a viewer whose browser or the raw CDN already holds the previous response may still see the older image, and this note does not measure how long, because only a cold-cache reload was observed.

## Not verified

- A reload inside an already warm cache window, in this or another browser.
- Signed-in GitHub views, WebKit, Firefox, mobile browsers, and real devices.
