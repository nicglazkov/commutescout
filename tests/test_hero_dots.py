"""/api/hero-dots: the home page's national map gets every live event as
a bare point (kind, lat, lon), small, gzipped, cached for 30 s, and
outside the strict rate limiter like /api/stats."""

import gzip
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from ca_roads_demo import app as demo_app
from ca_roads_demo import hero_dots

MARKERS = [
    {"kind": "incident", "lat": 37.12345, "lon": -122.98765,
     "type": "Crash", "location": "somewhere", "id": "x1"},
    # Rounds to the same spot as the first: sent once.
    {"kind": "incident", "lat": 37.1249, "lon": -122.9851},
    {"kind": "lane_closure", "lat": 40.0, "lon": -105.0,
     "path": [[40.0, -105.0], [40.1, -105.1]], "label": "long text"},
    {"kind": "chain_control", "lat": 39.3, "lon": -120.3},
    {"kind": "wildfire", "lat": 34.5, "lon": -118.1},
    # Not a hero kind, and a marker with no position: both dropped.
    {"kind": "camera", "lat": 38.0, "lon": -121.0},
    {"kind": "incident", "lat": None, "lon": -121.0},
]


@pytest.fixture
def built(monkeypatch):
    calls = []

    async def fake_build(box, want, *, geo_only=False, near=None,
                         corridor=None, feed_budget=None):
        calls.append((box, set(want)))
        return list(MARKERS), 3, 3, False

    monkeypatch.setattr(demo_app, "build_markers", fake_build)
    hero_dots.clear_cache()
    yield calls
    hero_dots.clear_cache()


def test_only_position_and_kind_rounded_and_deduplicated(built):
    r = TestClient(demo_app.app).get("/api/hero-dots")
    assert r.status_code == 200
    body = r.json()
    assert body["i"] == [37.12, -122.99]
    assert body["c"] == [40.0, -105.0]
    assert body["h"] == [39.3, -120.3]
    assert body["f"] == [34.5, -118.1]
    assert set(body) == {"at", "i", "c", "h", "f"}
    assert "long text" not in r.text and "Crash" not in r.text


def test_asks_for_the_four_road_kinds_everywhere(built):
    TestClient(demo_app.app).get("/api/hero-dots")
    box, want = built[0]
    assert want == {"incident", "closure", "chain", "fire"}
    assert box == hero_dots.WORLD_BOX


def test_gzipped_and_cached_for_thirty_seconds(built):
    client = TestClient(demo_app.app)
    first = client.get("/api/hero-dots", headers={"Accept-Encoding": "gzip"})
    assert first.headers["Content-Encoding"] == "gzip"
    assert "max-age=30" in first.headers["Cache-Control"]
    client.get("/api/hero-dots")
    assert len(built) == 1
    # A client that already has this body gets a 304.
    again = client.get("/api/hero-dots",
                       headers={"If-None-Match": first.headers["ETag"]})
    assert again.status_code == 304


def test_rebuilds_after_the_cache_expires(built, monkeypatch):
    client = TestClient(demo_app.app)
    client.get("/api/hero-dots")
    ts, etag, body = hero_dots._cache
    monkeypatch.setattr(hero_dots, "_cache", (ts - 31, etag, body))
    client.get("/api/hero-dots")
    assert len(built) == 2


def test_a_warming_answer_is_not_cached(monkeypatch):
    async def warming(box, want, **_kw):
        return [], 1, 5, False

    monkeypatch.setattr(demo_app, "build_markers", warming)
    hero_dots.clear_cache()
    r = TestClient(demo_app.app).get("/api/hero-dots")
    assert r.headers["Cache-Control"] == "no-store"
    assert hero_dots._cache is None


def test_the_wire_body_is_small():
    markers = [{"kind": "lane_closure", "lat": 30 + i / 100,
                "lon": -100 - i / 100, "label": "x" * 80}
               for i in range(5000)]
    raw = hero_dots.compact(markers, "2026-11-19T00:00:00+00:00")
    gz = gzip.compress(json.dumps(raw, separators=(",", ":")).encode())
    assert len(gz) < 40_000


def test_exempt_from_the_strict_limiter_like_stats():
    src = Path(demo_app.__file__).read_text()
    exempt = src[src.index("exempt_prefixes=("):]
    exempt = exempt[:exempt.index(")")]
    assert '"/api/hero-dots"' in exempt and '"/api/stats"' in exempt
