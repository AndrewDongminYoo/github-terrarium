"""Fixture gallery that embeds generated SVG through HTML img elements.

`build` is offline: it grows every fixture with `advance`, renders and validates
it, and writes the gallery page, negative-control pages and measurements.
`check` drives one Playwright browser at a time against a local HTTP server and
closes every browser and server it opens. Playwright is development-only.
"""

import argparse
import hashlib
import html
import http.server
import json
import os
import platform
import re
import statistics
import struct
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
import zlib
from datetime import date, timedelta
from functools import partial
from importlib.metadata import version
from pathlib import Path

from github_terrarium.growth import advance, traits
from github_terrarium.models import canonical_json, day_range
from github_terrarium.render import render
from github_terrarium.state import read_json
from github_terrarium.validate import validate_svg

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
DEFAULT_OUT = ROOT / "work" / "gallery"
NS = "{http://www.w3.org/2000/svg}"
PERSONAS = ("empty", "popularity", "pull-requests", "reviews", "issues")
END = date(2026, 11, 15)
WIDTHS = (360, 768, 900)
BACKGROUNDS = ("light", "dark")
# Computed body background that each requested host color scheme must produce.
HOST_BACKGROUNDS = {"dark": "rgb(13, 17, 23)", "light": "rgb(255, 255, 255)"}
MOTIONS = ("normal", "reduced")
ENGINES = ("chromium", "webkit")
INTERVAL = 2.0
VIEW = (900, 360)
# Identity, freshness and stage text in viewBox units; ambient motion stays out.
# The identity region spans the stretched label of a login over 20 characters,
# which the renderer draws from x 26 with textLength 620.
TEXT_REGIONS = {
    "freshness": (20, 38, 330, 60),
    "identity": (20, 6, 650, 36),
    "stage": (750, 6, 890, 36),
}
QUIET = {"prs": 0, "reviews": 0, "issues": 0}
SATURATED = {"prs": 5, "reviews": 10, "issues": 5}
MODEST = {"R1": {"stars": 10, "forks": 2}}
RENAMED_LOGIN = "octocat-renamed-to-a-longer-login"
# Host-page styles that must make the layout assertion fail at every width.
LAYOUT_CONTROLS = {
    "control-clipped": "figure { overflow: hidden; height: 40px; }\n",
    "control-overflow": "img { width: 1200px; max-width: none; }\n",
}
# Cells whose preference the harness cannot deliver into an img-embedded SVG.
# Their captures are still taken and recorded, but they never count as passing.
PENDING = {
    ("webkit", "reduced"): (
        "Playwright's emulated reduced motion reaches the host page and direct SVG "
        "navigation but not SVG inside img; no WebKit launch-level override was found, "
        "so an operating-system preference run is required"
    ),
}
REDUCED_RULE = re.compile(rb"@media \(prefers-reduced-motion: reduce\) \{.*?\n\}", re.S)


def snapshot(start, end, counts, repositories, login="octocat"):
    return {
        "schema_version": 1,
        "complete_snapshot": True,
        "subject": {"id": "U1", "login": login},
        "activity_start": start.isoformat(),
        "activity_end": end.isoformat(),
        "observed_on": end.isoformat(),
        "repositories": repositories,
        "days": {day: dict(counts(day)) for day in day_range(start, end)},
    }


def grow(counts, repositories=MODEST, later=0, renamed=None):
    """Bootstrap 30 days, then apply `later` daily updates ending at END."""
    end = END - timedelta(days=later)
    state = advance(snapshot(end - timedelta(days=30), end, counts, repositories))
    for step in range(later):
        end += timedelta(days=1)
        login = renamed if renamed and step == later - 1 else "octocat"
        value = snapshot(end - timedelta(days=30), end, counts, repositories, login)
        state = advance(value, state)
    return state


def fixtures():
    """Return gallery states in display order; every one is grown by `advance`."""
    result = {
        f"persona-{name}": advance(read_json(FIXTURES / f"{name}.json"))
        for name in PERSONAS
    }
    stages = {
        "seed": lambda day: {**QUIET, "issues": 1},
        "sprout": lambda day: {**QUIET, "reviews": 1},
        "grove": lambda day: {**QUIET, "prs": 2},
        "mature": lambda day: {**QUIET, "prs": 5},
    }
    for name, counts in stages.items():
        result[f"stage-{name}"] = grow(counts)
    result["stage-sanctuary"] = grow(lambda day: SATURATED, later=5)
    result["richest"] = grow(
        lambda day: SATURATED, {"R1": {"stars": 500, "forks": 100}}, later=5
    )
    result["renamed"] = grow(
        lambda day: {**QUIET, "prs": 1}, later=1, renamed=RENAMED_LOGIN
    )
    quiet_from = (END - timedelta(days=8)).isoformat()
    result["calm"] = grow(
        lambda day: {**QUIET, "prs": 2} if day < quiet_from else QUIET
    )
    return result


def describe(raw):
    root = ET.fromstring(raw)
    return {
        "animated_groups": sum(
            "ambient" in node.get("class", "").split() for node in root.iter()
        ),
        "bytes": len(raw),
        "elements": len(list(root.iter())),
        "motion": root.get("data-motion"),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "stage": root.get("data-stage"),
        "title": root.find(NS + "title").text,
    }


def controls(raw):
    """Deliberately broken variants; each must make one browser assertion fail."""
    static, removed = re.subn(rb"<style>.*?</style>", b"", raw, flags=re.S)
    ignored, stripped = REDUCED_RULE.subn(b"", raw)
    if removed != 1 or stripped != 1:
        raise ValueError("Renderer stylesheet changed; update the gallery controls")
    return {"control-static": static, "control-reduced-ignored": ignored}


STYLE = """
:root { color-scheme: light dark; }
body {
  margin: 0; padding: 16px; background: #ffffff; color: #1f2328;
  font: 14px/1.4 system-ui, sans-serif;
}
@media (prefers-color-scheme: dark) {
  body { background: #0d1117; color: #e6edf3; }
}
figure { margin: 0 0 24px; }
img { display: block; width: 100%; max-width: 900px; height: auto; }
""".strip()


def page(title, images, extra_style=""):
    figures = "\n".join(
        f'<figure><img src="svg/{html.escape(name)}.svg" '
        f'data-fixture="{html.escape(name)}" width="{VIEW[0]}" height="{VIEW[1]}" '
        f'alt="{html.escape(alt)}"><figcaption>{html.escape(name)}</figcaption>'
        "</figure>"
        for name, alt in images
    )
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n"
        f"<style>\n{STYLE}\n{extra_style}</style>\n</head>\n<body>\n"
        f"<h1>{html.escape(title)}</h1>\n{figures}\n</body>\n</html>\n"
    )


def build(out=DEFAULT_OUT):
    """Write SVGs, gallery pages and measurements; return the fixture summary."""
    out = Path(out)
    (out / "svg").mkdir(parents=True, exist_ok=True)
    summary = {}
    rendered = {}
    for name, state in fixtures().items():
        raw = render(state)
        validate_svg(raw)
        rendered[name] = raw
        summary[name] = {
            **describe(raw),
            "traits": traits(state["current_traits"]),
        }
    for name, raw in {**rendered, **controls(rendered["richest"])}.items():
        (out / "svg" / f"{name}.svg").write_bytes(raw)
    images = [(name, item["title"]) for name, item in summary.items()]
    (out / "index.html").write_text(page("Terrarium fixture gallery", images))
    (out / "controls.html").write_text(
        page(
            "Terrarium motion controls",
            [
                ("control-static", "Control without stylesheet"),
                ("control-reduced-ignored", "Control ignoring reduced motion"),
            ],
        )
    )
    for name, style in LAYOUT_CONTROLS.items():
        (out / f"{name}.html").write_text(
            page(f"Terrarium {name}", [("richest", name)], style)
        )
    (out / "fixtures.json").write_text(canonical_json(summary))
    return summary


def render_timing(repeat=7):
    state = fixtures()["richest"]
    samples = []
    for _ in range(repeat):
        started = time.perf_counter()
        render(state)
        samples.append((time.perf_counter() - started) * 1000)
    return round(statistics.median(samples), 2)


def png_pixels(raw):
    """Decode an 8-bit, non-interlaced RGB/RGBA PNG into rows of bytes."""
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Not a PNG")
    position, data, header = 8, [], None
    while position < len(raw):
        (length,) = struct.unpack(">I", raw[position : position + 4])
        kind = raw[position + 4 : position + 8]
        body = raw[position + 8 : position + 8 + length]
        position += 12 + length
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            data.append(body)
        elif kind == b"IEND":
            break
    if header is None:
        raise ValueError("PNG lacks a header")
    width, height, depth, color, _, _, interlace = header
    if depth != 8 or color not in (2, 6) or interlace:
        raise ValueError("Unsupported PNG layout")
    channels = 3 if color == 2 else 4
    stride = width * channels
    filtered = zlib.decompress(b"".join(data))
    previous = bytearray(stride)
    rows = []
    for y in range(height):
        start = y * (stride + 1)
        kind = filtered[start]
        line = bytearray(filtered[start + 1 : start + 1 + stride])
        if kind == 2:
            line = bytearray((x + p) & 255 for x, p in zip(line, previous))
        elif kind:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                up = previous[i]
                corner = previous[i - channels] if i >= channels else 0
                if kind == 1:
                    predicted = left
                elif kind == 3:
                    predicted = (left + up) // 2
                elif kind == 4:
                    estimate = left + up - corner
                    distances = (
                        abs(estimate - left),
                        abs(estimate - up),
                        abs(estimate - corner),
                    )
                    predicted = (left, up, corner)[distances.index(min(distances))]
                else:
                    raise ValueError("Unsupported PNG filter")
                line[i] = (line[i] + predicted) & 255
        rows.append(bytes(line))
        previous = line
    return width, height, channels, rows


def compare(first, second):
    """Count changed pixels overall and inside each scaled text region."""
    if first == second:
        return {"changed": 0, "regions": dict.fromkeys(TEXT_REGIONS, 0)}
    width, height, channels, rows_a = png_pixels(first)
    other_width, other_height, _, rows_b = png_pixels(second)
    if (width, height) != (other_width, other_height):
        raise ValueError("Frames differ in size; layout moved between captures")
    changed = []
    for y, (row_a, row_b) in enumerate(zip(rows_a, rows_b)):
        if row_a != row_b:
            changed.extend(
                (x, y)
                for x in range(width)
                if row_a[x * channels : (x + 1) * channels]
                != row_b[x * channels : (x + 1) * channels]
            )
    sx, sy = width / VIEW[0], height / VIEW[1]
    regions = {
        name: sum(
            left * sx <= x < right * sx and top * sy <= y < bottom * sy
            for x, y in changed
        )
        for name, (left, top, right, bottom) in TEXT_REGIONS.items()
    }
    return {"changed": len(changed), "regions": regions}


def motion_verdict(mode, difference):
    """Normal motion must move ambient pixels only; reduced motion must not."""
    if mode == "reduced":
        return [] if difference["changed"] == 0 else ["reduced-motion frames differ"]
    failures = []
    if difference["changed"] == 0:
        failures.append("normal-motion frames are identical")
    moved = sorted(name for name, count in difference["regions"].items() if count)
    if moved:
        failures.append("text regions changed: " + ", ".join(moved))
    return failures


def layout_verdict(metrics):
    """No page overflow, and every image is loaded, unclipped and whole."""
    failures = []
    if metrics["scrollWidth"] > metrics["clientWidth"]:
        failures.append("page overflows horizontally")
    for image in metrics["images"]:
        name = image["name"]
        if not image["loaded"]:
            failures.append(f"{name}: image did not load")
        if image["left"] < 0 or image["right"] > metrics["clientWidth"] + 0.5:
            failures.append(f"{name}: image extends past the viewport")
        if image["clipped"]:
            failures.append(f"{name}: image is clipped by an ancestor")
        expected = image["width"] * VIEW[1] / VIEW[0]
        if image["width"] <= 0 or abs(image["height"] - expected) > 1:
            failures.append(f"{name}: image is not shown whole at 900:360")
    return failures


METRICS_JS = """
() => {
  const doc = document.documentElement;
  const images = [...document.images].map((img) => {
    const r = img.getBoundingClientRect();
    let clipped = false;
    for (let node = img.parentElement; node; node = node.parentElement) {
      const style = getComputedStyle(node);
      if (style.overflowX !== "visible" || style.overflowY !== "visible") {
        const box = node.getBoundingClientRect();
        if (r.left < box.left - 0.5 || r.right > box.right + 0.5 ||
            r.top < box.top - 0.5 || r.bottom > box.bottom + 0.5) clipped = true;
      }
    }
    return {
      name: img.dataset.fixture, left: r.left, right: r.right, width: r.width,
      height: r.height, clipped, loaded: img.complete && img.naturalWidth > 0,
    };
  });
  return {
    scrollWidth: doc.scrollWidth, clientWidth: doc.clientWidth,
    background: getComputedStyle(document.body).backgroundColor, images,
  };
}
"""

READY_JS = (
    "() => Promise.all([...document.images].map((img) => img.decode()))"
    ".then(() => true)"
)

LOAD_TIMING_JS = """
async (source) => {
  const samples = [];
  for (let i = 0; i < 7; i++) {
    const img = new Image();
    const started = performance.now();
    img.src = `${source}?sample=${i}-${Date.now()}`;
    await img.decode();
    samples.push(performance.now() - started);
  }
  samples.sort((a, b) => a - b);
  return samples[3];
}
"""


def host():
    def sysctl(key):
        try:
            return subprocess.run(
                ["sysctl", "-n", key], capture_output=True, text=True, check=True
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    memory = sysctl("hw.memsize")
    return {
        "cpu": sysctl("machdep.cpu.brand_string") or platform.processor() or None,
        "logical_cpus": os.cpu_count(),
        "machine": platform.machine(),
        "memory_bytes": int(memory) if memory and memory.isdigit() else None,
        "os": platform.platform(),
        "python": platform.python_version(),
    }


class Server:
    """Serve the gallery directory on loopback with an explicit SVG media type."""

    def __init__(self, directory):
        handler = partial(_Handler, directory=str(directory))
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def __exit__(self, *_):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


class _Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        ".html": "text/html; charset=utf-8",
        ".json": "application/json",
        ".svg": "image/svg+xml",
    }

    def log_message(self, *_):
        pass


def frames(page, directory):
    """Capture every image twice, at least INTERVAL seconds apart."""
    images = page.locator("img")
    names = [images.nth(i).get_attribute("data-fixture") for i in range(images.count())]
    directory.mkdir(parents=True, exist_ok=True)
    first = {}
    for index, name in enumerate(names):
        raw = images.nth(index).screenshot()
        # Timed after the first capture ends: the measured gap is a lower bound.
        first[name] = (time.monotonic(), raw)
    result = {}
    for index, name in enumerate(names):
        started, raw = first[name]
        time.sleep(max(0.0, started + INTERVAL - time.monotonic()))
        second_at = time.monotonic()
        second = images.nth(index).screenshot()
        (directory / f"{name}-a.png").write_bytes(raw)
        (directory / f"{name}-b.png").write_bytes(second)
        result[name] = {
            "interval_s": round(second_at - started, 2),
            **compare(raw, second),
            "sha256": [
                hashlib.sha256(raw).hexdigest(),
                hashlib.sha256(second).hexdigest(),
            ],
        }
    return result


def open_page(context, url):
    page = context.new_page()
    page.goto(url)
    page.wait_for_function("() => [...document.images].every((img) => img.complete)")
    page.evaluate(READY_JS)
    return page


def check_cell(browser, base, out, engine, motion, width, background):
    cell = out / "captures" / engine / motion / f"{background}-{width}"
    cell.mkdir(parents=True, exist_ok=True)
    context = browser.new_context(
        viewport={"width": width, "height": 900},
        device_scale_factor=1,
        color_scheme=background,
        reduced_motion="reduce" if motion == "reduced" else "no-preference",
    )
    try:
        gallery = open_page(context, f"{base}/index.html")
        prefers = gallery.evaluate(
            "() => matchMedia('(prefers-reduced-motion: reduce)').matches"
        )
        layout = gallery.evaluate(METRICS_JS)
        gallery.screenshot(path=str(cell / "page.png"), full_page=True)
        captured = frames(gallery, cell)
        layout_controls = {
            name: layout_verdict(
                open_page(context, f"{base}/{name}.html").evaluate(METRICS_JS)
            )
            for name in LAYOUT_CONTROLS
        }
        moving = open_page(context, f"{base}/controls.html")
        control_frames = frames(moving, cell / "controls")
    finally:
        context.close()
    expected = "control-static" if motion == "normal" else "control-reduced-ignored"
    controls_found = {
        **layout_controls,
        expected: motion_verdict(motion, control_frames[expected]),
    }
    return {
        "background": background,
        "controls": controls_found,
        "host_background": layout["background"],
        "host_prefers_reduced_motion": prefers,
        "images": captured,
        "layout": layout,
        "motion": motion,
        "width": width,
        **classify(
            engine, motion, background, prefers, layout, captured, controls_found
        ),
    }


def classify(engine, motion, background, prefers, layout, images, controls_found):
    """Decide a cell's status; only a declared, explained gap may be pending."""
    failures = layout_verdict(layout)
    if layout["background"] != HOST_BACKGROUNDS[background]:
        failures.append(
            f"host page background is {layout['background']}, "
            f"not the {background} {HOST_BACKGROUNDS[background]}"
        )
    if prefers != (motion == "reduced"):
        failures.append("host page did not receive the requested motion preference")
    motion_failures = [
        f"{name}: {failure}"
        for name, item in images.items()
        for failure in motion_verdict(motion, item)
    ]
    failures += [
        f"{name} passed; its assertion cannot fail"
        for name, found in controls_found.items()
        if not found
    ]
    pending = []
    if (engine, motion) in PENDING and prefers:
        pending, motion_failures = motion_failures, []
    failures += motion_failures
    status = "failed" if failures else "pending" if pending else "passed"
    return {"failures": failures, "pending": pending, "status": status}


def check(engine, out=DEFAULT_OUT):
    """Run the full width/background/motion matrix in one engine."""
    from playwright.sync_api import sync_playwright

    out = Path(out)
    if not (out / "index.html").is_file():
        raise SystemExit(f"Run `build` first; {out / 'index.html'} is missing")
    (out / "captures" / engine / "controls").mkdir(parents=True, exist_ok=True)
    result = {
        "engine": engine,
        "host": host(),
        "playwright": version("playwright"),
        "settings": {
            "backgrounds": list(BACKGROUNDS),
            "device_scale_factor": 1,
            "interval_s": INTERVAL,
            "viewport_height": 900,
            "widths": list(WIDTHS),
        },
        "cells": [],
    }
    with Server(out) as base, sync_playwright() as runtime:
        for motion in MOTIONS:
            # Chromium's emulated preference does not reach SVG inside img; see
            # docs/notes/motion-verification.md. Force it at launch instead.
            arguments = (
                ["--force-prefers-reduced-motion"]
                if engine == "chromium" and motion == "reduced"
                else []
            )
            browser = getattr(runtime, engine).launch(args=arguments)
            try:
                result["browser_version"] = browser.version
                result["settings"][f"launch_args_{motion}"] = arguments
                for width in WIDTHS:
                    for background in BACKGROUNDS:
                        result["cells"].append(
                            check_cell(
                                browser, base, out, engine, motion, width, background
                            )
                        )
                if motion == "normal":
                    context = browser.new_context(
                        viewport={"width": 900, "height": 900}
                    )
                    try:
                        timing = context.new_page()
                        timing.goto(f"{base}/index.html")
                        result["richest_decode_ms_median"] = round(
                            timing.evaluate(LOAD_TIMING_JS, f"{base}/svg/richest.svg"),
                            2,
                        )
                    finally:
                        context.close()
            finally:
                browser.close()
    result["pending_reasons"] = {
        motion: reason for (name, motion), reason in PENDING.items() if name == engine
    }
    (out / f"results-{engine}.json").write_text(canonical_json(result))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    build_parser = commands.add_parser("build", help="write the offline gallery")
    build_parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    check_parser = commands.add_parser("check", help="capture and assert in browsers")
    check_parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    check_parser.add_argument(
        "--engine", choices=ENGINES, nargs="+", default=list(ENGINES)
    )
    args = parser.parse_args(argv)
    if args.command == "build":
        summary = build(args.out)
        richest = summary["richest"]
        print(
            json.dumps(
                {
                    "fixtures": len(summary),
                    "out": str(args.out),
                    "richest": {
                        key: richest[key]
                        for key in ("animated_groups", "bytes", "elements", "stage")
                    },
                    "richest_render_ms_median": render_timing(),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    status = 0
    for engine in args.engine:  # sequential: one browser process at a time
        result = check(engine, args.out)
        failures = [
            f"{cell['motion']}/{cell['background']}/{cell['width']}: {failure}"
            for cell in result["cells"]
            for failure in cell["failures"]
        ]
        counts = {
            key: sum(cell["status"] == key for cell in result["cells"])
            for key in ("passed", "pending", "failed")
        }
        print(f"{engine} {result['browser_version']}: {counts}")
        for (name, motion), reason in PENDING.items():
            if name == engine and counts["pending"]:
                print(f"  PENDING {motion}: {reason}")
        for failure in failures:
            print(f"  FAIL {failure}")
        if failures:
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
