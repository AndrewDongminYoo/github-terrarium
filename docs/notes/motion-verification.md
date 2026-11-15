# Ambient motion verification

Verified locally on 2026-11-15 for issue #10, using Python 3.12.16 and Chromium 157.0.8103.38 on macOS.
This evidence covers the three motion families and their fallbacks; the complete browser/persona matrix remains issue #12 and final botanical approval remains issue #13.

## Automated contracts

Run `python -m unittest discover -s tests -v`, `ruff check src tests`, and `ruff format --check src tests`.
The 65-test suite covers each PR/review/issue dimension at zero, six, seven, and eight inactive completed UTC days, replay, state immutability, incomplete history rejection, and equal scene geometry across active/calm states.
The all-traits-saturated Sanctuary has 38 ambient groups, below the limit of 40; SVG size and element limits remain covered.
The initial motion assertions failed before implementation, including the missing active/calm mode and missing motion families.

## Browser observations

A local HTML image embedded the same generated active and calm scenes, differing only in their seven-day activity placement and motion-mode attribute.
Time-separated 900-pixel captures changed 3,931 pixels in active mode and 2,140 pixels in calm mode, while identity and freshness regions stayed unchanged.
Those counts demonstrate observed motion, not a calibrated intensity or performance comparison: frame intervals and phases differ.
Recordings also preserve the actual active, calm, and reduced-motion output.
An inline equivalent independently exposed all six CSS keyframe rules through CSSOM; animated properties were restricted to `transform` and `opacity`.
Reduced motion exposed zero active animations, `animation-name: none`, and zero-duration transitions on every ambient group.

## Reduced-motion test setup

In this Chromium build, DevTools reduced-motion emulation made the HTML/inline media query true but left the SVG image moving, including in a fresh browser session.
Do not treat that parent-page result as proof that the image received the preference.
A separate isolated browser launched with `--force-prefers-reduced-motion` produced identical time-separated image captures and matched the no-CSS static image exactly (zero changed pixels).
The no-CSS image also had zero changed pixels across captures.
Chromium's [switch implementation](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/ui/gfx/switches.cc) documents that flag as overriding the system preference; no operating-system preference was changed during this check.
This contrast isolates the observed problem to the emulated preference path in the tested environment; it is not a universal claim about all Chromium releases or operating systems.

## Limits

WebKit, the complete width/background/persona matrix, GitHub README image behavior, and performance calibration have not been established by this issue.
The standalone SVG remains self-contained; the test HTML and recordings are local review evidence rather than a deployed service.
