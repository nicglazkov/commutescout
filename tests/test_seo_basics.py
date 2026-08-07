"""Machine-readable basics every page owes a crawler.

These went missing quietly: /map, the highest-priority entry in the
sitemap, had no heading element at all, and none of the eight marketing
pages carried structured data.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MAP_HTML = ROOT / "src" / "ca_roads_demo" / "static" / "map.html"
# The real export, same reasoning as test_site_assets: CI always builds
# before this suite, a Node-less local run gets a clear skip.
REAL_SITE_OUT = ROOT / "site" / "out"
NEEDS_BUILD = pytest.mark.skipif(
    not REAL_SITE_OUT.exists(),
    reason="site/out is not built; run `cd site && npm run build` first.",
)

MARKETING_PAGES = ["index", "pricing", "about", "contact", "privacy",
                   "terms", "data-sources", "mcp"]


def test_map_page_has_exactly_one_h1():
    html = MAP_HTML.read_text(encoding="utf-8")
    assert len(re.findall(r"<h1[\s>]", html)) == 1


def test_map_h1_is_hidden_without_being_removed_from_the_tree():
    """display:none would hide it from assistive tech too."""
    html = MAP_HTML.read_text(encoding="utf-8")
    assert 'class="visually-hidden"' in html
    rule = re.search(r"\.visually-hidden\s*\{([^}]*)\}", html)
    assert rule, "the class is used but never defined"
    body = rule.group(1)
    assert "display:none" not in body.replace(" ", "")
    assert "clip:" in body.replace(" ", "")


@NEEDS_BUILD
@pytest.mark.parametrize("page", MARKETING_PAGES)
def test_marketing_pages_carry_valid_structured_data(page):
    html = (REAL_SITE_OUT / f"{page}.html").read_text(encoding="utf-8")
    blocks = re.findall(
        r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
        html, re.S)
    assert blocks, f"{page}.html has no structured data"
    for raw in blocks:
        data = json.loads(raw)  # must parse, not just be present
        assert data.get("@context") == "https://schema.org"


@NEEDS_BUILD
def test_structured_data_cannot_close_its_own_script_tag():
    html = (REAL_SITE_OUT / "index.html").read_text(encoding="utf-8")
    block = re.search(
        r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
        html, re.S).group(1)
    assert "<" not in block, "unescaped < inside the JSON-LD payload"


@NEEDS_BUILD
@pytest.mark.parametrize("page", MARKETING_PAGES)
def test_marketing_pages_declare_the_apple_icon_and_manifest(page):
    html = (REAL_SITE_OUT / f"{page}.html").read_text(encoding="utf-8")
    assert "apple-touch-icon" in html, f"{page}.html has no apple icon"
    assert 'rel="manifest"' in html, f"{page}.html has no manifest link"
