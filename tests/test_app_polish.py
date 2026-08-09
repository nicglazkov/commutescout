"""P2/P3 polish: branded 404, security.txt, /health, expired-trip."""
import pathlib

import pytest
from starlette.testclient import TestClient

from ca_roads_demo import app as demo_app

REAL_SITE_OUT = (pathlib.Path(__file__).resolve().parent.parent
                 / "site" / "out")
NEEDS_BUILD = pytest.mark.skipif(
    not REAL_SITE_OUT.exists(),
    reason="site/out is not built; CI's site job builds first.")


@pytest.fixture()
def client():
    with TestClient(demo_app.app) as c:
        yield c


def test_health_does_not_leak_the_model(client):
    body = client.get("/health").json()
    assert body["ok"] is True and "version" in body
    assert "model" not in body


def test_security_txt_is_served(client):
    r = client.get("/.well-known/security.txt")
    assert r.status_code == 200
    assert "Contact:" in r.text and "Expires:" in r.text
    assert "security/advisories" in r.text


def test_api_404_stays_json(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")


@NEEDS_BUILD
def test_page_404_is_branded(client, monkeypatch):
    monkeypatch.setattr(demo_app, "SITE_DIR", REAL_SITE_OUT)
    r = client.get("/no-such-page-xyz")
    assert r.status_code == 404
    # The site shell, not a bare heading: header nav + footer are present.
    assert "text/html" in r.headers["content-type"]
    assert "CommuteScout" in r.text


@NEEDS_BUILD
def test_expired_trip_gets_the_branded_404(client, monkeypatch):
    monkeypatch.setattr(demo_app, "SITE_DIR", REAL_SITE_OUT)

    class _NoStore:
        async def get_trip(self, tid):
            return None

    from ca_roads_demo import watch as watch_mod
    monkeypatch.setattr(watch_mod, "get_store", lambda: _NoStore())
    r = client.get("/trip/abc123")
    assert r.status_code == 404
    assert "CommuteScout" in r.text          # branded, not a bare <h1>
    assert "<h1>This trip link" not in r.text
