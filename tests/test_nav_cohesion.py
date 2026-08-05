"""Nav cohesion guard (feat/nav-cohesion): the five surfaces that render a
CommuteScout header - the four legacy static pages under
src/ca_roads_demo/static/ and the Next site's global SiteHeader, exported to
site/out/index.html - must all expose the same header shape: the
logo/wordmark links home, the nav destination set is exactly
{/watch, /data-sources, /mcp, /pricing, /map}, the four text nav links
appear in that exact order with their exact labels, the /map link's label
is exactly "Live map", and none of them has a leftover "Home" nav item
(the logo IS the home affordance now).

Order/label checks look only at the four text-nav anchors' relative order
among themselves (filtering out the logo and the /map link first), not at
their raw position in the DOM: the site header's two-row mobile layout
(components/site-header.tsx) puts the Live map CTA before <nav> in source
order so it can sit next to the brand on row 1, while the legacy pages'
Live map link (a .navcta sibling of <nav>, see e.g.
src/ca_roads_demo/static/map.html) comes after it. That's an intentional
per-surface layout difference, not something this guard should flag.

This is a guard test, not a design doc: if the target nav changes, update
REQUIRED_TEXT_NAV_ORDER / TEXT_NAV_LABELS / LIVE_MAP_LABEL here alongside
the header markup.
"""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = REPO_ROOT / "src" / "ca_roads_demo" / "static"
SITE_OUT = REPO_ROOT / "site" / "out"

# Order matters: this is the exact left-to-right sequence the four text nav
# links must appear in on every surface.
REQUIRED_TEXT_NAV_ORDER = ["/watch", "/data-sources", "/mcp", "/pricing"]
TEXT_NAV_LABELS = {
    "/watch": "Watch areas",
    "/data-sources": "Data sources",
    "/mcp": "Developers",
    "/pricing": "Pricing",
}
LIVE_MAP_HREF = "/map"
LIVE_MAP_LABEL = "Live map"

REQUIRED_NAV_DESTINATIONS = set(REQUIRED_TEXT_NAV_ORDER) | {LIVE_MAP_HREF}

STATIC_PAGES = ["map", "watch", "trip", "admin"]


class _AnchorCollector(HTMLParser):
    """Collects every <a href="..."> in a fragment, in document order, with
    its attributes and visible (stripped-tag) text."""

    def __init__(self):
        super().__init__()
        self.anchors: list[dict] = []
        self._stack: list[dict] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._stack.append({"attrs": dict(attrs), "text": []})

    def handle_data(self, data):
        if self._stack:
            self._stack[-1]["text"].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._stack:
            entry = self._stack.pop()
            self.anchors.append({
                "href": entry["attrs"].get("href", ""),
                "attrs": entry["attrs"],
                "text": "".join(entry["text"]).strip(),
            })


def _extract_header_block(html_text: str, start_marker: str) -> str:
    """The substring from the first `start_marker` through its matching
    </header> close tag. Good enough here: every surface has exactly one
    <header>...</header> pair (confirmed for the site export: SiteHeader is
    the only component in site/ that renders a <header> element)."""
    start = html_text.index(start_marker)
    end = html_text.index("</header>", start) + len("</header>")
    return html_text[start:end]


def _anchors_in(html_fragment: str) -> list[dict]:
    parser = _AnchorCollector()
    parser.feed(html_fragment)
    return parser.anchors


def _check_surface(name: str, anchors: list[dict]) -> None:
    logo = [a for a in anchors if a["attrs"].get("aria-label") == "CommuteScout home"]
    assert logo, (
        f"{name}: no logo/wordmark link found "
        f'(expected an <a aria-label="CommuteScout home">)'
    )
    assert len(logo) == 1, f"{name}: expected exactly one logo link, found {len(logo)}"
    assert logo[0]["href"] == "/", (
        f"{name}: logo/wordmark links to {logo[0]['href']!r}, want '/'"
    )

    # Every other header link is a nav destination (the legacy pages' text
    # links plus the Live map CTA; the site header's Live map link too,
    # even though it sits outside the <nav> element proper).
    nav_hrefs = {a["href"] for a in anchors} - {"/"}
    assert nav_hrefs == REQUIRED_NAV_DESTINATIONS, (
        f"{name}: nav destinations {sorted(nav_hrefs)} != "
        f"{sorted(REQUIRED_NAV_DESTINATIONS)}"
    )

    # Order + exact labels for the four text nav links, filtered to just
    # those hrefs so an unrelated anchor (the logo, or /map, which sits on
    # either side of <nav> depending on the surface) can't shift the
    # comparison.
    text_links = [a for a in anchors if a["href"] in TEXT_NAV_LABELS]
    actual_order = [a["href"] for a in text_links]
    assert actual_order == REQUIRED_TEXT_NAV_ORDER, (
        f"{name}: text nav order {actual_order} != {REQUIRED_TEXT_NAV_ORDER}"
    )
    for a in text_links:
        expected_label = TEXT_NAV_LABELS[a["href"]]
        assert a["text"] == expected_label, (
            f"{name}: {a['href']} label is {a['text']!r}, want {expected_label!r}"
        )

    live_map_links = [a for a in anchors if a["href"] == LIVE_MAP_HREF]
    assert len(live_map_links) == 1, (
        f"{name}: expected exactly one {LIVE_MAP_HREF} link, found {len(live_map_links)}"
    )
    assert live_map_links[0]["text"] == LIVE_MAP_LABEL, (
        f"{name}: {LIVE_MAP_HREF} link text is {live_map_links[0]['text']!r}, "
        f"want {LIVE_MAP_LABEL!r}"
    )

    for a in anchors:
        assert a["text"].strip().lower() != "home", (
            f"{name}: found a nav item whose text is \"Home\" (href={a['href']!r}); "
            "the logo/wordmark is the only home affordance now"
        )


@pytest.mark.parametrize("page", STATIC_PAGES)
def test_static_page_header_matches_target_nav(page):
    html_text = (STATIC_DIR / f"{page}.html").read_text(encoding="utf-8")
    block = _extract_header_block(html_text, '<header class="topbar">')
    _check_surface(page, _anchors_in(block))


@pytest.mark.skipif(
    not (SITE_OUT / "index.html").exists(),
    reason="site/out is not built; run `cd site && npm run build` first. "
    "CI's site job always builds before this suite runs.",
)
def test_site_header_matches_target_nav():
    html_text = (SITE_OUT / "index.html").read_text(encoding="utf-8")
    block = _extract_header_block(html_text, "<header")
    _check_surface("site (site/out/index.html)", _anchors_in(block))
