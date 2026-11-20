"""The /watch page in the site's Clear Coat look.

/watch is a static page served by the demo app, not a page of the Next
site, so it carries its own copy of the site header, footer and colour
tokens. These guards read the site's sources and fail when the copy
drifts: the nav items, the footer links, the token values, and the
free-tier figures the page quotes from the server's limits.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

from ca_roads_demo import watch

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "src" / "ca_roads_demo" / "static"
SITE = ROOT / "site"
WATCH_HTML = (STATIC / "watch.html").read_text(encoding="utf-8")
WATCH_APP_JS = (STATIC / "watch-app.js").read_text(encoding="utf-8")


def _block(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i:text.index(end, i) + len(end)]


HEADER = _block(WATCH_HTML, '<header class="topbar sitebar">', "</header>")
FOOTER = _block(WATCH_HTML, '<footer class="sitefoot">', "</footer>")


class _Links(HTMLParser):
    """(href, text) for every <a>, plus the text of .devnote spans."""

    def __init__(self):
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self.notes: list[str] = []
        self._a: list | None = None
        self._note: list | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a":
            self._a = [a.get("href", ""), ""]
        elif tag == "span" and a.get("class") == "devnote":
            self._note = [""]

    def handle_endtag(self, tag):
        if tag == "a" and self._a is not None:
            self.links.append((self._a[0], " ".join(self._a[1].split())))
            self._a = None
        elif tag == "span" and self._note is not None:
            self.notes.append(" ".join(self._note[0].split()))
            self._note = None

    def handle_data(self, data):
        if self._a is not None:
            self._a[1] += data
        if self._note is not None:
            self._note[0] += data


def _parse(fragment: str) -> _Links:
    p = _Links()
    p.feed(fragment)
    return p


# ── Header ────────────────────────────────────────────────────────────

def _site_nav_items() -> list[tuple[str, str, str | None]]:
    """(href, label, note) in source order from site-header.tsx's
    before, developers and after arrays."""
    src = (SITE / "components" / "site-header.tsx").read_text(encoding="utf-8")
    items = []
    for name in ("before", "developers", "after"):
        m = re.search(rf"const {name}\b[^=]*=\s*\[(.*?)\n\];", src, re.S)
        assert m, f"site-header.tsx no longer defines {name}; update this test"
        for obj in re.finditer(r"\{(.*?)\}", m.group(1), re.S):
            body = obj.group(1)
            href = re.search(r'href:\s*"([^"]+)"', body)
            label = re.search(r'label:\s*"([^"]+)"', body)
            note = re.search(r'note:\s*"([^"]+)"', body)
            if href and label:
                items.append((href.group(1), label.group(1), note and note.group(1)))
    return items


def test_header_nav_matches_site_header_source():
    site = _site_nav_items()
    assert len(site) == 7, site
    page = _parse(_block(HEADER, "<nav", "</nav>"))
    assert [(h, t) for h, t in page.links] == [(h, label) for h, label, _ in site]
    assert page.notes == [n for _, _, n in site if n]


def test_header_brand_cta_and_current_page():
    links = _parse(HEADER).links
    assert links[0] == ("/", "CommuteScout")
    assert 'aria-label="CommuteScout home"' in HEADER
    assert links[-1] == ("/map", "Live map")
    assert HEADER.count('aria-current="page"') == 1
    assert '<a class="tl" href="/watch" aria-current="page">Watch areas</a>' in HEADER
    # The Developers menu, theme switch and mobile menu are real buttons.
    assert 'class="tl devbtn" aria-expanded="false" aria-controls="devpop"' in HEADER
    assert 'class="themetoggle"' in HEADER
    assert ('class="navmenu" aria-expanded="false" aria-controls="topnav" '
            'aria-label="Menu"') in HEADER


def test_header_holds_account_identity():
    # watch-app.js writes the signed-in email and the Sign out button into
    # #who; the header's account menu shows it.
    assert '<div class="who" id="who"></div>' in HEADER
    assert '<li class="acct" hidden>' in HEADER


# ── Footer ────────────────────────────────────────────────────────────

def test_footer_links_match_site_footer_source():
    src = (SITE / "components" / "site-footer.tsx").read_text(encoding="utf-8")
    want = re.findall(r'\{\s*href:\s*"([^"]+)",\s*label:\s*"([^"]+)"', src)
    assert len(want) >= 10, want
    got = [link for link in _parse(FOOTER).links if link[0] != "/"]
    assert got[:len(want)] == want


def test_footer_figures_match_site_stats():
    stats = (SITE / "lib" / "stats.ts").read_text(encoding="utf-8")
    feeds = re.search(r"AGENCY_FEED_COUNT = (\d+);", stats).group(1)
    states = re.search(r"STATE_COUNT = (\d+);", stats).group(1)
    assert f"{feeds} sources, {states} states" in FOOTER


# ── Tokens ────────────────────────────────────────────────────────────

_HEX = re.compile(r"(--cs-[a-z0-9-]+):\s*(#[0-9a-fA-F]{3,8});")


def _hex_vars(css: str, selector: str) -> dict[str, str]:
    body = _block(css, selector + " {", "}")
    return dict(_HEX.findall(body))


def test_clear_coat_tokens_match_site_globals():
    tokens = (STATIC / "tokens.css").read_text(encoding="utf-8")
    site = (SITE / "app" / "globals.css").read_text(encoding="utf-8")
    pairs = [
        (_hex_vars(tokens, ":root.cc"), _hex_vars(site, ":root")),
        (_hex_vars(tokens, ':root.cc[data-theme="dark"]'),
         _hex_vars(site, ':root[data-theme="dark"]')),
        (_hex_vars(tokens, ':root.cc:not([data-theme="light"])'),
         _hex_vars(site, ':root:not([data-theme="light"])')),
    ]
    for ours, theirs in pairs:
        assert len(ours) >= 20, ours
        for name, value in ours.items():
            assert theirs.get(name, "").lower() == value.lower(), (name, value, theirs.get(name))


def test_page_opts_into_clear_coat():
    assert '<html lang="en" class="cc">' in WATCH_HTML
    assert '<script src="/static/basemap-early.js?v=__ASSET_V__"></script>' in WATCH_HTML
    for css in ("tokens", "sitebar", "watch", "watch-page"):
        assert f'<link rel="stylesheet" href="/static/{css}.css?v=__ASSET_V__">' in WATCH_HTML
    assert (STATIC / "sitebar.css").exists() and (STATIC / "watch-page.css").exists()


def test_page_styles_stay_scoped():
    # watch-page.css only restyles /watch (body.wp); sitebar.css only the
    # Clear Coat pages (html.cc). Neither may leak into map.html.
    page = (STATIC / "watch-page.css").read_text(encoding="utf-8")
    bar = (STATIC / "sitebar.css").read_text(encoding="utf-8")
    for css, scopes in ((page, (".wp", "#signin")), (bar, (".cc", ":root.cc", ".skip"))):
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        for sel in re.findall(r"(?:^|})\s*([^@{}][^{}]*?)\s*\{", css):
            for part in re.split(r",(?![^()]*\))", sel):  # not commas inside :where()
                part = part.strip()
                if not part or part.startswith(("@", "from", "to")) or part[0].isdigit():
                    continue
                assert part.startswith(scopes), f"unscoped selector {part!r}"


# ── Copy ──────────────────────────────────────────────────────────────

def _text(html: str) -> str:
    html = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S)
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    return " ".join(re.sub(r"<[^>]+>", " ", html).replace("&nbsp;", " ").split())


def test_free_tier_figures_come_from_watch_limits():
    text = _text(WATCH_HTML)
    km_per_mi = 1.609344
    radius_mi = round(watch.FREE_MAX_RADIUS_KM / km_per_mi)
    route_mi = round(watch.FREE_MAX_ROUTE_KM / km_per_mi)
    buffer_mi = round(watch.FREE_MAX_BUFFER_KM / km_per_mi)
    area_sq_mi = round(watch.FREE_MAX_POLYGON_SQ_KM / km_per_mi ** 2, -2)
    assert f"up to {radius_mi} mi ({round(watch.FREE_MAX_RADIUS_KM)} km)" in text
    assert f"3 to {watch.MAX_POLY_POINTS} corners" in text
    assert f"up to {int(area_sq_mi):,} sq mi" in text
    assert f"up to {route_mi} mi long" in text
    assert f"up to {buffer_mi} mi either side" in text
    assert f"up to {watch.FREE_MAX_WATCHES} watch areas" in text
    assert 'max="40.2"' in WATCH_HTML and watch.FREE_MAX_RADIUS_KM == 40.2


def test_check_interval_matches_scheduler():
    deploy = (ROOT / "docs" / "deploy.md").read_text(encoding="utf-8")
    assert "*/5 * * * *" in deploy
    assert "about every 5 minutes" in _text(WATCH_HTML)


def test_copy_is_location_agnostic():
    text = _text(WATCH_HTML)
    for word in ("California", "Caltrans", "quickmap", "CHP"):
        assert word not in text, word
    assert "your state's 511" in text


# ── Accessibility ─────────────────────────────────────────────────────

def test_one_h1_per_state_and_labelled_inputs():
    for sec in ("signin", "gate", "appzone"):
        assert f'<section id="{sec}"' in WATCH_HTML
    # Each input in the page markup has a <label for> or wraps in a label.
    for m in re.finditer(r'<input\b[^>]*\bid="([^"]+)"[^>]*>', WATCH_HTML):
        iid = m.group(1)
        before = WATCH_HTML[:m.start()]
        wrapped = before.rfind("<label") > before.rfind("</label>")
        assert wrapped or f'for="{iid}"' in WATCH_HTML, f"#{iid} has no label"
    for mid in ("signinmsg", "gatemsg", "createmsg", "listmsg", "devmsg", "acctmsg"):
        assert re.search(rf'id="{mid}" role="status"', WATCH_HTML), mid


def test_row_icon_buttons_have_names():
    # Saved-area rows use icon buttons; each gets a spoken name.
    assert "const iconBtn = (icon, label)" in WATCH_APP_JS
    assert "setAttribute('aria-label', label)" in WATCH_APP_JS
    for label in ("Pause alerts for ", "Resume alerts for ", "Edit ", "Delete "):
        assert label in WATCH_APP_JS, label


def test_consent_state_is_a_class_on_signin():
    assert "$('signin').classList.toggle('consent', termsGate);" in WATCH_APP_JS
    page = (STATIC / "watch-page.css").read_text(encoding="utf-8")
    assert "#signin.consent .wp-intro" in page
