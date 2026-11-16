# SVG artwork provenance

## Paper-cut runtime pieces

`papercut.svg` contains named native vector pieces extracted from the operator-supplied [Sanctuary design reference](../references/terrarium-papercut-sanctuary.svg), created with Claude and preserved unchanged.
The source SHA-256 is `f87b93c4b6def040906347b1ab690413f6dddd5d03112218c04941038a5264e9`.
Regenerate the packaged asset from the repository root with Python 3.12:

```bash
python tools/extract_papercut_assets.py
```

Edit the extractor rather than the generated asset.
The extractor rejects a changed reference so its reviewed child-index map cannot silently select different pieces.
It removes mockup labels and authoring-time animation classes, retains flat contours and reused shadows, and names landscape, water, canopy, trunk, roots, flowers, mushrooms, and foreground resources.
Renderer version 3 loads these definitions through `github_terrarium.art`; installed wheels need neither the source reference nor the extractor.
Runtime code supplies identity/date labels, stage scales, independently seeded trait slots, and ambient CSS; it does not embed a finished mockup or read the reference at runtime.

## Historical botanical primitives

`botanical.svg` contains native SVG definitions authored for github-terrarium issue #9, alongside the renderer in the same change.
The leaf, flower, mushroom, seedling, and pond-creature paths were constructed directly from SVG coordinates; no predecessor artwork, third-party image, font, or generated bitmap was imported.
Renderer versions 1 and 2 loaded these definitions through `github_terrarium.art`, with a parameterized vessel, soil, stems, ground cover, pond, and fireflies.
The current renderer uses `papercut.svg`; the earlier primitives remain as historical artwork.

This file records provenance, not a license grant or final visual approval.
Source and artwork licensing remains subject to issues #21 and #22; the complete generated-scene gallery is reviewed separately in #13.
