"""The marketing site: exported pages served by Starlette."""
from starlette.testclient import TestClient

from ca_roads_demo import app as demo_app


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
