# Original botanical primitives

`botanical.svg` contains native SVG definitions authored for github-terrarium issue #9, alongside the renderer in the same change.
The leaf, flower, mushroom, seedling, and pond-creature paths were constructed directly from SVG coordinates; no predecessor artwork, third-party image, font, or generated bitmap was imported.
The renderer loads these definitions as the packaged resource `github_terrarium.art` and places them using bounded, independently seeded slots.
The vessel, soil, stems, ground cover, pond, and fireflies are parameterized native geometry in `src/github_terrarium/render.py`.

This file records provenance, not a license grant or final visual approval.
Source and artwork licensing remains subject to issues #21 and #22; the complete botanical gallery is reviewed separately in #13.
