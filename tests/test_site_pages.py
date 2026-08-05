"""The marketing site: exported pages served by Starlette."""
import html
import re
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from ca_roads_demo import app as demo_app

FIXTURES = Path(__file__).parent / "fixtures"
# The real build output, not a monkeypatched SITE_DIR + tmp fixture: the
# whole point of this test is pinning what actually ships. CI's site job
# always runs `npm run build` before this suite, so CI always exercises the
# real assertion below; a local run without Node gets a clear skip instead
# of a false failure.
REAL_SITE_OUT = Path(__file__).resolve().parent.parent / "site" / "out"


def _visible(raw_html: str) -> str:
    """Normalize a page to its visible text for content-preservation
    comparisons: strip <script>...</script>, replace every remaining tag
    with a space, decode HTML entities, then collapse whitespace.

    The entity-decoding step is not in the task brief's original sketch;
    it was added because Next's static export HTML-escapes apostrophes,
    quotes, and ampersands in text nodes (e.g. "we'll" -> "we&#x27;ll",
    confirmed against this build's own output), while the pre-reskin
    hand-written privacy.html/terms.html used literal characters. Without
    unescaping, every apostrophe/quote in the legal text would make the
    substring comparison below fail on an encoding artifact, not a wording
    change. tests/fixtures/privacy_text.txt and terms_text.txt were
    generated with this same normalization (see git history for the
    extraction script) from the <main>...</main> content of the pre-reskin
    pages, excluding the inline <style> block and old topbar nav, which are
    chrome, not reviewed legal content."""
    t = re.sub(r"<script.*?</script>", "", raw_html, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    return " ".join(t.split())


@pytest.mark.skipif(
    not REAL_SITE_OUT.exists(),
    reason="site/out is not built; run `cd site && npm run build` first. "
    "CI's site job always builds before this suite runs.",
)
@pytest.mark.parametrize("page", ["privacy", "terms"])
def test_legal_content_survived_the_reskin(page):
    """The reskin moves privacy and terms into the site shell. The words
    themselves are CalOPPA-reviewed and must not change without Nic's
    approval, so this compares normalized visible text against the
    pre-reskin extraction committed in tests/fixtures/."""
    new = _visible((REAL_SITE_OUT / f"{page}.html").read_text(encoding="utf-8"))
    old = (FIXTURES / f"{page}_text.txt").read_text(encoding="utf-8")
    assert old in new


def test_site_pages_serve_when_built(tmp_path, monkeypatch):
    # Simulate a built export without requiring Node in CI for this test.
    # trailingSlash: false emits a flat "<page>.html" sibling file, not a
    # nested "<page>/index.html" (Task 8 fix round 1 ruling: slash-less
    # served URLs).
    (tmp_path / "index.html").write_text("<h1>home</h1>", encoding="utf-8")
    (tmp_path / "pricing.html").write_text("<h1>pricing</h1>",
                                           encoding="utf-8")
    monkeypatch.setattr(demo_app, "SITE_DIR", tmp_path)
    c = TestClient(demo_app.app)
    assert b"home" in c.get("/").content
    assert b"pricing" in c.get("/pricing").content


def test_privacy_and_terms_serve_from_the_export(tmp_path, monkeypatch):
    """Task 10: /privacy and /terms are re-pointed at _site_response, same
    as /pricing, /about, /contact - no more standalone privacy.html /
    terms.html served via FileResponse(STATIC_DIR / ...)."""
    (tmp_path / "privacy.html").write_text("<h1>privacy</h1>", encoding="utf-8")
    (tmp_path / "terms.html").write_text("<h1>terms</h1>", encoding="utf-8")
    monkeypatch.setattr(demo_app, "SITE_DIR", tmp_path)
    c = TestClient(demo_app.app)
    assert b"privacy" in c.get("/privacy").content
    assert b"terms" in c.get("/terms").content


def test_site_page_falls_back_to_nested_index_html(tmp_path, monkeypatch):
    """Older builds (or a trailingSlash: true export) still serve: when the
    flat "<page>.html" is absent, fall back to "<page>/index.html"."""
    (tmp_path / "pricing").mkdir(parents=True)
    (tmp_path / "pricing" / "index.html").write_text("<h1>pricing</h1>",
                                                      encoding="utf-8")
    monkeypatch.setattr(demo_app, "SITE_DIR", tmp_path)
    c = TestClient(demo_app.app)
    assert b"pricing" in c.get("/pricing").content


def test_map_still_serves_when_site_is_not_built(tmp_path, monkeypatch):
    """Local dev without Node: the map and APIs must work; marketing
    pages return a clear 503, not a stack trace."""
    monkeypatch.setattr(demo_app, "SITE_DIR", tmp_path / "missing")
    c = TestClient(demo_app.app)
    r = c.get("/")
    assert r.status_code == 503
    assert "site is not built" in r.text
    assert r.headers["cache-control"] == "no-store"


def test_marketing_pages_are_exempt_from_the_rate_limiter(tmp_path, monkeypatch):
    """Marketing pages must not share the /api/ask bucket (RateLimitMiddleware,
    capacity=20): hammering one well past that burst allowance must never
    produce a 429."""
    (tmp_path / "pricing.html").write_text("<h1>pricing</h1>",
                                           encoding="utf-8")
    monkeypatch.setattr(demo_app, "SITE_DIR", tmp_path)
    c = TestClient(demo_app.app)
    for _ in range(30):
        r = c.get("/pricing")
        assert r.status_code != 429


def test_map_serves_at_map_with_bootgeo(monkeypatch):
    c = TestClient(demo_app.app)
    r = c.get("/map", headers={"x-visitor-lat": "37.77",
                               "x-visitor-lon": "-122.41"})
    assert r.status_code == 200
    assert 'id="bootgeo"' in r.text          # data island still injected
    assert "leaflet" in r.text.lower()


def test_root_serves_homepage_not_map(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<h1>home</h1>", encoding="utf-8")
    monkeypatch.setattr(demo_app, "SITE_DIR", tmp_path)
    c = TestClient(demo_app.app)
    assert b"home" in c.get("/").content
    assert b"leaflet" not in c.get("/").content.lower()
