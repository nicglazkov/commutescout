"""/api/route: validation, the budget guards, the five-minute cache, and
a ranked answer built from the router's reply and the live markers."""

import pytest
from starlette.testclient import TestClient
from tests.test_routing import LINE, _trip

from ca_roads_demo import app as demo_app
from ca_roads_mcp import server as tools

LOCS = [{"lat": 37.5, "lon": -122.4}, {"lat": 37.5, "lon": -121.9}]


class _Resp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body

    def json(self):
        return self._body


class _Client:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    async def post(self, url, *, json, headers, timeout):
        self.calls.append((url, json, headers))
        return self.reply


class _Road:
    def __init__(self, client):
        self.client = client


@pytest.fixture
def wired(monkeypatch):
    clean = [[37.6, -122.4 + i * 0.005] for i in range(100)]
    reply = _Resp(200, {"trip": _trip(LINE, 3000),
                        "alternates": [{"trip": _trip(clean, 3300)}]})
    fake = _Client(reply)
    monkeypatch.setattr(tools, "get_road", lambda: _Road(fake))

    async def fake_build(box, want, *, geo_only=False, near=None, corridor=None, feed_budget=None):
        assert want == {"incident", "closure", "chain", "plugin"}
        assert box[0] < 37.5 < box[2] and box[1] < -122.4 and box[3] > -121.9
        return [
            {"kind": "incident", "type": "1183-Trfc Collision", "lat": 37.5, "lon": -122.3},
            {"kind": "incident", "type": "1183-Trfc Collision", "lat": 37.5, "lon": -122.2},
            {"kind": "lane_closure", "cls": "full-roadway", "lat": 38.5, "lon": -121.0},
        ], 1, 1, False

    monkeypatch.setattr(demo_app, "build_markers", fake_build)
    monkeypatch.setenv("STADIA_API_KEY", "test-key")
    demo_app._ROUTE_CACHE.clear()
    demo_app.paid_use._counts.clear() if hasattr(demo_app.paid_use, "_counts") else None
    return fake


def test_validation(wired):
    c = TestClient(demo_app.app)
    assert c.post("/api/route", content=b"nope",
                  headers={"Content-Type": "application/json"}).status_code == 400
    assert c.post("/api/route", json={"locations": [LOCS[0]]}).status_code == 400
    bad = [{"lat": 99, "lon": 0}, LOCS[1]]
    assert c.post("/api/route", json={"locations": bad}).status_code == 400
    assert c.post("/api/route", json={"locations": LOCS, "preset": "teleport"}).status_code == 400


def test_no_key_is_a_503_so_the_page_falls_back(wired, monkeypatch):
    monkeypatch.delenv("STADIA_API_KEY")
    r = TestClient(demo_app.app).post("/api/route", json={"locations": LOCS})
    assert r.status_code == 503 and "not configured" in r.json()["error"]


def test_ranked_answer_with_exclusions_and_a_cached_repeat(wired):
    c = TestClient(demo_app.app)
    r = c.post("/api/route", json={"locations": LOCS})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["preset"] == "fastest" and body["excluded"] == 1
    assert [x["score_s"] for x in body["routes"]] == [3300, 3720]
    assert body["routes"][1]["hassles"][0]["label"] == "2 collisions"
    url, sent, headers = wired.calls[0]
    assert url.endswith("/route/v1") and sent["exclude_locations"] == [{"lat": 38.5, "lon": -121.0}]
    assert headers["Authorization"] == "Stadia-Auth test-key"
    assert r.headers["Cache-Control"] == "no-store"
    # Same trip again within five minutes: no second call upstream.
    r2 = c.post("/api/route", json={"locations": LOCS})
    assert r2.status_code == 200 and r2.headers.get("X-Cache") == "hit"
    assert len(wired.calls) == 1
    # A preset is a different plan.
    r3 = c.post("/api/route", json={"locations": LOCS, "preset": "no_tolls"})
    assert r3.status_code == 200 and len(wired.calls) == 2
    assert wired.calls[1][1]["costing_options"] == {"auto": {"use_tolls": 0}}


def test_router_failure_is_a_404_not_a_crash(wired):
    wired.reply = _Resp(400, {"error": "no path"})
    r = TestClient(demo_app.app).post("/api/route", json={"locations": LOCS})
    assert r.status_code == 404 and r.json()["error"] == "no route found"
    # Tried with exclusions, then plainly.
    assert len(wired.calls) == 2 and "exclude_locations" not in wired.calls[1][1]


def test_route_is_budgeted_and_soft_limited():
    assert "/api/route" in demo_app.SoftLimit.PREFIXES
    # Per client at or under the service-wide cap: one caller must not
    # be able to spend the whole day on its own.
    assert demo_app.PAID_PER_CLIENT_DAILY["route"] <= demo_app.STADIA_ROUTE_DAILY
