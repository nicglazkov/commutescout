"""The marketing site: exported pages served by Starlette."""
from starlette.testclient import TestClient

from ca_roads_demo import app as demo_app


def test_site_pages_serve_when_built(tmp_path, monkeypatch):
    # Simulate a built export without requiring Node in CI for this test.
    (tmp_path / "pricing").mkdir(parents=True)
    (tmp_path / "index.html").write_text("<h1>home</h1>", encoding="utf-8")
    (tmp_path / "pricing" / "index.html").write_text("<h1>pricing</h1>",
                                                     encoding="utf-8")
    monkeypatch.setattr(demo_app, "SITE_DIR", tmp_path)
    c = TestClient(demo_app.app)
    assert b"home" in c.get("/site-preview").content
    assert b"pricing" in c.get("/pricing").content


def test_map_still_serves_when_site_is_not_built(tmp_path, monkeypatch):
    """Local dev without Node: the map and APIs must work; marketing
    pages return a clear 503, not a stack trace."""
    monkeypatch.setattr(demo_app, "SITE_DIR", tmp_path / "missing")
    c = TestClient(demo_app.app)
    r = c.get("/site-preview")
    assert r.status_code == 503
    assert "site is not built" in r.text
