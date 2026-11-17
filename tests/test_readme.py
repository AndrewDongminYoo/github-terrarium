"""Standard-library checks for the README embed and local documentation links.

`ReadmeTests.test_checks_fail_on_mutated_copies` breaks a copy once per check
and requires that check to fail, so a pass is not a read of a pattern that can
never miss.
"""

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
DOCUMENTS = [README, ROOT / "CONTRIBUTING.md"]
EMBED = (
    "https://raw.githubusercontent.com/AndrewDongminYoo/github-terrarium/"
    "output/terrarium.svg"
)
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


class _Images(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            self.images.append(dict(attrs))


def embed_errors(text):
    """Return problems with the generated-habitat `img` embed in `text`."""
    parser = _Images()
    for line in text.splitlines():
        if line.startswith("<img "):
            parser.feed(line)
    embeds = [i for i in parser.images if "terrarium.svg" in i.get("src", "")]
    if len(embeds) != 1:
        return [f"expected one generated-habitat img, found {len(embeds)}"]
    errors = []
    if embeds[0].get("src") != EMBED:
        errors.append(f"src is not the stable URL: {embeds[0].get('src')}")
    alt = (embeds[0].get("alt") or "").strip()
    if len(alt.split()) < 5:
        errors.append(f"alt text is not descriptive: {alt!r}")
    return errors


def slug(heading):
    """Return GitHub's anchor for a Markdown heading."""
    text = heading.strip().lower().replace("`", "")
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


def anchors(text):
    headings = []
    fenced = False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and line.startswith("#"):
            headings.append(slug(line.lstrip("#")))
    return set(headings)


def link_errors(path, text):
    """Return local links in `text` whose file or heading anchor is missing."""
    errors = []
    fenced = False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        for target in LINK.findall(line):
            if re.match(r"[a-z]+:", target):
                continue
            name, _, anchor = target.partition("#")
            destination = (path.parent / name).resolve() if name else path
            if not destination.exists():
                errors.append(f"{path.name}: missing {target}")
            elif anchor and destination.suffix == ".md":
                if anchor not in anchors(destination.read_text(encoding="utf-8")):
                    errors.append(f"{path.name}: missing anchor {target}")
    return errors


class ReadmeTests(unittest.TestCase):
    def test_readme_embeds_the_stable_output_image(self):
        self.assertEqual(embed_errors(README.read_text(encoding="utf-8")), [])

    def test_local_links_and_anchors_resolve(self):
        for path in DOCUMENTS:
            with self.subTest(document=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertEqual(link_errors(path, text), [])

    def test_slug_matches_github_anchors(self):
        self.assertEqual(slug(" Freshness and caching"), "freshness-and-caching")
        self.assertEqual(slug(" Run the `probe`, again"), "run-the-probe-again")

    def test_checks_fail_on_mutated_copies(self):
        text = README.read_text(encoding="utf-8")
        embeds = [
            text.replace(EMBED, EMBED + "?v=1"),
            text.replace(EMBED, EMBED.replace("/output/", "/main/")),
            re.sub(r'(<img src="[^"]+terrarium\.svg") alt="[^"]*"', r'\1 alt=""', text),
            re.sub(r'<img src="[^"]+terrarium\.svg"[^>]*>', "", text),
        ]
        for index, broken in enumerate(embeds):
            with self.subTest(embed=index):
                self.assertNotEqual(broken, text)
                self.assertNotEqual(embed_errors(broken), [])
        for broken in [
            text.replace("(CONTRIBUTING.md)", "(CONTRIBUTE.md)", 1),
            text.replace("(#daily-workflow)", "(#daily-workflows)", 1),
            text.replace(
                "architecture.md#atomic-publication",
                "architecture.md#atomic-publications",
                1,
            ),
        ]:
            self.assertNotEqual(broken, text)
            self.assertNotEqual(link_errors(README, broken), [])


if __name__ == "__main__":
    unittest.main()
