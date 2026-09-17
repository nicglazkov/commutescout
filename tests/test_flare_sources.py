"""Flare sources: the poller reads a plugin cell by cell, keeps only
what the spec accepts, serves markers for a bbox, and the admin
endpoints manage the registry."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient
from tests.test_flare import GOOD, FakePlugin
from tests.test_watch import auth, store  # noqa: F401 - fixture

from ca_roads_demo import flare_sources, routing

NOW = datetime(2026, 9, 17, 1, 0, tzinfo=UTC)
MANIFEST = {"id": "sabreplus", "name": "SABRE Plus", "base": "https://plugins.example.com",
            "protocol": "flare/1", "visibility": "public", "trust": "community",
            "attribution": {"name": "SABRE Plus", "url": "https://example.com"}}


def test_cells_tile_the_box_and_cap_from_the_middle():
    cells = flare_sources.cells_for([37.0, -123.0, 39.0, -121.0])
    assert cells == [(37.5, -122.5), (37.5, -121.5), (38.5, -122.5), (38.5, -121.5)]
    big = flare_sources.cells_for([24.0, -125.0, 50.0, -66.0])
    assert len(big) == flare_sources.MAX_CELLS
    assert abs(big[0][0] - 37.0) < 1.5 and abs(big[0][1] + 95.5) < 1.5  # nearest the center


@pytest.mark.asyncio
async def test_poller_accepts_valid_alerts_and_serves_markers():
    plugin = FakePlugin()
    plugin.alerts["stale"] = dict(GOOD, id="stale",
                                  report_ts=(NOW - timedelta(days=1)).isoformat())
    plugin.alerts["bad"] = dict(GOOD, id="bad", kind="UFO")
    mem = flare_sources.MemorySourceStore()
    await mem.put("sabreplus", dict(MANIFEST, enabled=True))
    p = flare_sources.Poller(mem, now=lambda: NOW)
    async with httpx.AsyncClient(transport=httpx.MockTransport(plugin.handler)) as c:
        await p.run_once(c)
    assert p.status["sabreplus"]["ok"] and p.status["sabreplus"]["count"] == 1
    markers = p.markers_for_bbox((37.0, -122.5, 38.0, -121.0))
    assert len(markers) == 1
    m = markers[0]
    assert m["kind"] == "plugin" and m["id"] == "sabreplus:" + GOOD["id"]
    assert m["flare_kind"] == "POLICE_VISIBLE" and m["road"] == "I-280 N"
    assert m["source"] == "SABRE Plus" and m["trust"] == "community" and m["tier"] == "unreviewed"
    assert m["path"] == [[37.34, -121.89], [37.35, -121.87]]  # GeoJSON lon,lat -> lat,lon
    assert p.markers_for_bbox((40.0, -122.5, 41.0, -121.0)) == []
    assert p.public_sources()[0]["count"] == 1
    # A second cycle inside the refresh interval does not poll again.
    calls = len(plugin.alerts)
    async with httpx.AsyncClient(transport=httpx.MockTransport(plugin.handler)) as c:
        await p.run_once(c)
    assert len(plugin.alerts) == calls


@pytest.mark.asyncio
async def test_a_failing_source_is_recorded_not_fatal():
    def broken(request):
        return httpx.Response(500, text="boom")

    mem = flare_sources.MemorySourceStore()
    await mem.put("sabreplus", dict(MANIFEST, enabled=True))
    await mem.put("off", dict(MANIFEST, id="off", enabled=False))
    p = flare_sources.Poller(mem, now=lambda: NOW)
    async with httpx.AsyncClient(transport=httpx.MockTransport(broken)) as c:
        await p.run_once(c)
    st = p.status["sabreplus"]
    assert st["ok"] is False and "HTTPStatusError" in st["last_error"]
    assert "off" not in p.sources and p.markers_for_bbox((-90, -180, 90, 180)) == []


def test_plugin_alerts_shape_the_route():
    closed = {"kind": "plugin", "flare_kind": "ROAD_CLOSED", "lat": 37.5, "lon": -122.2}
    crash = {"kind": "plugin", "flare_kind": "CRASH_MAJOR", "lat": 37.5, "lon": -122.3}
    police = {"kind": "plugin", "flare_kind": "POLICE_VISIBLE", "lat": 37.5, "lon": -122.25}
    assert routing.exclusions([closed, crash]) == [{"lat": 37.5, "lon": -122.2}]
    line = [[37.5, -122.4 + i * 0.005] for i in range(100)]
    s = routing.score(line, [crash, police])
    assert s["penalty_min"] == routing.PENALTY_MIN["collision"] + routing.PENALTY_MIN["police"]
    assert [h["kind"] for h in s["hassles"]] == ["collision", "police"]


@pytest.fixture
def admin_app(store, monkeypatch):  # noqa: F811 - fixture
    mem = flare_sources.MemorySourceStore()
    flare_sources.set_source_store(mem)
    plugin = FakePlugin()

    class _Road:
        client = httpx.AsyncClient(transport=httpx.MockTransport(plugin.handler))

    from ca_roads_mcp import server as tools
    monkeypatch.setattr(tools, "get_road", lambda: _Road())
    monkeypatch.setattr(flare_sources, "poller", flare_sources.Poller(mem, now=lambda: NOW))
    app = Starlette(routes=[
        Route("/api/admin/flare", flare_sources.api_admin_flare, methods=["GET", "POST"]),
        Route("/api/flare/sources", flare_sources.api_flare_sources),
    ])
    yield TestClient(app), mem
    flare_sources.set_source_store(None)


def test_admin_adds_validates_and_manages_sources(admin_app):
    c, mem = admin_app
    assert c.get("/api/admin/flare").status_code == 401 or \
        c.get("/api/admin/flare").status_code == 403
    assert c.post("/api/admin/flare", json={"manifest": MANIFEST},
                  headers=auth()).status_code == 403
    r = c.post("/api/admin/flare", json={"manifest": dict(MANIFEST, base="http://x")},
               headers=auth("tok-admin"))
    assert r.status_code == 400 and "base" in r.json()["error"]
    r = c.post("/api/admin/flare", json={"manifest": dict(MANIFEST, token="secret-1")},
               headers=auth("tok-admin"))
    assert r.status_code == 200, r.text
    assert "token" not in r.json()["source"] and mem.docs["sabreplus"]["token"] == "secret-1"
    listed = c.get("/api/admin/flare", headers=auth("tok-admin")).json()["sources"]
    assert listed[0]["id"] == "sabreplus" and "token" not in listed[0]
    assert c.post("/api/admin/flare", json={"action": "disable", "id": "sabreplus"},
                  headers=auth("tok-admin")).json()["action"] == "disable"
    assert mem.docs["sabreplus"]["enabled"] is False
    assert c.post("/api/admin/flare", json={"action": "remove", "id": "sabreplus"},
                  headers=auth("tok-admin")).status_code == 200
    assert mem.docs == {}
    assert c.post("/api/admin/flare", json={"action": "remove", "id": "nope"},
                  headers=auth("tok-admin")).status_code == 404
    assert c.get("/api/flare/sources").json()["sources"] == []


def test_a_source_never_polled_is_due_even_on_a_freshly_booted_machine(monkeypatch):
    # CI runners boot seconds before the tests run: the monotonic clock is
    # below the poll floor, and "clock - 0 >= period" said "not yet".
    monkeypatch.setattr(flare_sources.time, "monotonic", lambda: 3.0)
    p = flare_sources.Poller(flare_sources.MemorySourceStore(), now=lambda: NOW)
    assert p.due({"id": "sabreplus"})
    p._last_poll["sabreplus"] = 3.0
    assert not p.due({"id": "sabreplus"})
