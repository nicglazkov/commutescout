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
    assert c.get("/map").status_code == 200


def test_marketing_pages_are_exempt_from_the_rate_limiter(tmp_path, monkeypatch):
    """Marketing pages must not share the /api/ask bucket (RateLimitMiddleware,
    capacity=20): hammering one well past that burst allowance must never
    produce a 429."""
    (tmp_path / "pricing.html").write_text("<h1>pricing</h1>",
                                           encoding="utf-8")
    (tmp_path / "privacy.html").write_text("<h1>privacy</h1>",
                                           encoding="utf-8")
    monkeypatch.setattr(demo_app, "SITE_DIR", tmp_path)
    c = TestClient(demo_app.app)
    for _ in range(30):
        r = c.get("/pricing")
        assert r.status_code != 429
    # A legal page (as opposed to a product marketing page) must be exempt
    # too: it shares the exempt_prefixes entry with /pricing, /about, and
    # /contact, but a regression that only re-added the product pages
    # would slip past a test that never actually hammers /privacy.
    for _ in range(30):
        r = c.get("/privacy")
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


def test_resolve_site_file_prefers_the_default_dir_over_the_repo_fallback(
        tmp_path, monkeypatch):
    """Dev-only fallback (nothing populates STATIC_DIR/site outside
    Docker): when SITE_DIR is at its built-in default, a missing file
    there falls back to REPO_SITE_OUT (the repo checkout's own
    `site/out`), but a file present in both is served from the default,
    never from the fallback."""
    primary = tmp_path / "primary"
    fallback = tmp_path / "fallback"
    primary.mkdir()
    fallback.mkdir()
    (primary / "shared.html").write_text("primary", encoding="utf-8")
    (fallback / "shared.html").write_text("fallback", encoding="utf-8")
    (fallback / "only_in_fallback.html").write_text("fallback-only",
                                                     encoding="utf-8")
    monkeypatch.setattr(demo_app, "_DEFAULT_SITE_DIR", primary)
    monkeypatch.setattr(demo_app, "REPO_SITE_OUT", fallback)
    monkeypatch.setattr(demo_app, "SITE_DIR", primary)

    assert demo_app._resolve_site_file("shared.html").read_text(
        encoding="utf-8") == "primary"
    assert demo_app._resolve_site_file("only_in_fallback.html").read_text(
        encoding="utf-8") == "fallback-only"
    assert demo_app._resolve_site_file("nope.html") is None


def test_resolve_site_file_skips_the_fallback_when_site_dir_is_monkeypatched(
        tmp_path, monkeypatch):
    """When a test (or a future caller) points SITE_DIR somewhere other
    than the built-in default, the repo fallback must not leak files in
    from a real checkout sitting alongside the test run - it must behave
    as though only SITE_DIR exists."""
    other = tmp_path / "other"
    fallback = tmp_path / "fallback"
    other.mkdir()
    fallback.mkdir()
    (fallback / "only_in_fallback.html").write_text("fallback-only",
                                                     encoding="utf-8")
    monkeypatch.setattr(demo_app, "_DEFAULT_SITE_DIR", tmp_path / "default")
    monkeypatch.setattr(demo_app, "REPO_SITE_OUT", fallback)
    monkeypatch.setattr(demo_app, "SITE_DIR", other)

    assert demo_app._resolve_site_file("only_in_fallback.html") is None


def test_asset_source_dir_prefers_the_default_when_it_has_next(
        tmp_path, monkeypatch):
    """The /_next and /shots mounts are wired up once at import time (see
    _asset_source_dir in app.py); this checks the directory-selection
    logic directly, since it can't be exercised through a monkeypatched
    request the way _resolve_site_file can."""
    primary = tmp_path / "primary"
    fallback = tmp_path / "fallback"
    (primary / "_next").mkdir(parents=True)
    (fallback / "_next").mkdir(parents=True)
    monkeypatch.setattr(demo_app, "SITE_DIR", primary)
    monkeypatch.setattr(demo_app, "REPO_SITE_OUT", fallback)

    assert demo_app._asset_source_dir() == primary

    # Docker image layout absent (no _next under SITE_DIR): falls back to
    # the repo checkout's own build.
    (primary / "_next").rmdir()
    assert demo_app._asset_source_dir() == fallback
