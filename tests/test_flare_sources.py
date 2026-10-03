"""Flare sources: the poller reads a plugin cell by cell, keeps only
what the spec accepts, serves markers for a bbox, and the admin
endpoints manage the registry."""

import json
from pathlib import Path
import time
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient
from tests.test_flare import GOOD, FakePlugin
from tests.test_watch import auth, store  # noqa: F401 - fixture

from ca_roads import flare
from ca_roads_demo import flare_sources, routing

NOW = datetime(2026, 9, 17, 1, 0, tzinfo=UTC)
# Plugin alerts are only ever served around somebody's own position, so
# every test that expects to see one has to say where it is standing.
HERE = (GOOD["lat"], GOOD["lon"])
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
    markers = p.markers_for_bbox((37.0, -122.5, 38.0, -121.0), near=HERE)
    assert len(markers) == 1
    m = markers[0]
    assert m["kind"] == "plugin" and m["id"] == "sabreplus:" + GOOD["id"]
    assert m["flare_kind"] == "POLICE_VISIBLE" and m["road"] == "I-280 N"
    assert m["source"] == "SABRE Plus" and m["trust"] == "community" and m["tier"] == "unreviewed"
    assert m["path"] == [[37.34, -121.89], [37.35, -121.87]]  # GeoJSON lon,lat -> lat,lon
    assert p.markers_for_bbox((40.0, -122.5, 41.0, -121.0), near=HERE) == []
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
    assert st["ok"] is False and "HTTP 500" in st["last_error"]
    assert ("off" not in p.sources
            and p.markers_for_bbox((-90, -180, 90, 180), near=HERE) == [])


def test_plugin_alerts_shape_the_route():
    # A closure steers the router only from a reviewed source; see
    # test_unconfirmed_community_closures_never_steer_the_router.
    closed = {"kind": "plugin", "flare_kind": "ROAD_CLOSED", "lat": 37.5, "lon": -122.2,
              "source_id": "sabreplus", "tier": "approved"}
    crash = {"kind": "plugin", "flare_kind": "CRASH_MAJOR", "lat": 37.5, "lon": -122.3}
    police = {"kind": "plugin", "flare_kind": "POLICE_VISIBLE", "lat": 37.5, "lon": -122.25}
    assert routing.exclusions([closed, crash]) == [{"lat": 37.5, "lon": -122.2}]
    unreviewed = dict(closed, tier="unreviewed")
    assert routing.exclusions([unreviewed, crash]) == []
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


def test_admin_adds_a_plugin_by_its_url(admin_app):
    # The plugin's own handshake supplies id, name and attribution; the tier
    # is public and unreviewed unless the body says otherwise.
    c, mem = admin_app
    r = c.post("/api/admin/flare", json={"action": "add", "base": "http://plugins.example.com"},
               headers=auth("tok-admin"))
    assert r.status_code == 400
    r = c.post("/api/admin/flare", json={"action": "add", "base": "https://plugins.example.com/"},
               headers=auth("tok-admin"))
    assert r.status_code == 200, r.text
    src = r.json()["source"]
    assert src["id"] in mem.docs and src["base"] == "https://plugins.example.com"
    assert src["visibility"] == "public" and src["trust"] == "community"
    assert mem.docs[src["id"]]["enabled"] is True


@pytest.mark.asyncio
async def test_polling_follows_people_and_sweeps_a_box_it_can_finish():
    # A plugin covering ten by ten degrees: where somebody actually is gets
    # asked for every cycle, tightly; the rest of a box this size is swept
    # a slice at a time, and a point's alerts survive the cycles it is not
    # polled in.
    plugin = FakePlugin(handshake={"coverage": {"bbox": [30.0, -125.0, 40.0, -115.0]}})
    asked: list[tuple[float, float, float]] = []
    orig = plugin.handler

    def counting(req):
        if req.url.path.endswith("/alerts"):
            asked.append((float(req.url.params["lat"]), float(req.url.params["lon"]),
                          float(req.url.params["r"])))
        return orig(req)

    mem = flare_sources.MemorySourceStore()
    await mem.put("sabreplus", dict(MANIFEST, enabled=True))
    p = flare_sources.Poller(mem, now=lambda: NOW)
    here = flare_sources.snap_point(GOOD["lat"], GOOD["lon"])
    p.note_at(GOOD["lat"], GOOD["lon"])
    async with httpx.AsyncClient(transport=httpx.MockTransport(counting)) as c:
        await p.run_once(c)
        first = list(asked)
        points = [(a, o) for a, o, _ in first]
        assert here in points
        # Where somebody is gets the tight radius, not the cell-wide one.
        assert [r for a, o, r in first if (a, o) == here] == [
            float(flare_sources.NEAR_FETCH_M)]
        assert len(first) <= flare_sources.SWEEP_PER_POLL + flare_sources.PRODUCTIVE_PER_POLL + 1
        assert p.status["sabreplus"]["count"] == 1
        # Next cycle: a different sweep slice, the same person still there.
        asked.clear()
        p._last_poll.clear()
        await p.run_once(c)
        assert here in [(a, o) for a, o, _ in asked]
        assert set(asked) != set(first)
        assert p.status["sabreplus"]["count"] == 1


@pytest.mark.asyncio
async def test_a_box_too_big_to_sweep_is_polled_from_demand_alone():
    """The relay covers the whole country. A national box is about 5,400
    one-degree cells, and a dozen a minute is seven hours a lap against a
    fifteen-minute memory, so the sweep never built a picture: it dragged
    one small patch around and everything behind it expired. A box that
    big is asked only about the places people are in.
    """
    national = [18.0, -168.0, 71.5, -66.5]
    plugin = FakePlugin(handshake={"coverage": {"bbox": national}})
    asked: list[tuple[float, float]] = []
    orig = plugin.handler

    def counting(req):
        if req.url.path.endswith("/alerts"):
            asked.append((float(req.url.params["lat"]), float(req.url.params["lon"])))
        return orig(req)

    mem = flare_sources.MemorySourceStore()
    await mem.put("sabreplus", dict(MANIFEST, enabled=True))
    p = flare_sources.Poller(mem, now=lambda: NOW)
    assert len(flare_sources.lattice(national)) > flare_sources.SWEEP_MAX_CELLS
    # Nobody anywhere: nothing is asked for at all.
    assert p.cells_to_poll("sabreplus", national) == []
    p.note_at(GOOD["lat"], GOOD["lon"])
    async with httpx.AsyncClient(transport=httpx.MockTransport(counting)) as c:
        await p.run_once(c)
    assert asked == [flare_sources.snap_point(GOOD["lat"], GOOD["lon"])]


def test_a_position_is_snapped_before_it_is_stored_or_sent():
    """A plugin is told the neighbourhood somebody is in, never the
    address. Snapping is also what makes a whole town cost one poll."""
    p = flare_sources.Poller(flare_sources.MemorySourceStore())
    p.note_at(37.33712, -121.88951)
    p.note_at(37.34102, -121.89400)
    assert list(p.near) == [(37.3, -121.9)], "one town, one point"
    for lat, lon in p.near:
        assert flare_sources.meters_between(lat, lon, 37.33712, -121.88951) < 6_200


@pytest.mark.asyncio
async def test_one_persons_plugin_alerts_never_reach_another():
    """Two people, two states, one shared cache of alerts. Each is served
    a small circle around themselves. Neither is told the other exists,
    because an alert only exists because somebody was standing there.
    """
    national = [18.0, -168.0, 71.5, -66.5]
    plugin = FakePlugin(handshake={"coverage": {"bbox": national}})
    far = {k: v for k, v in GOOD.items() if k != "geometry"}
    far.update(id="texas", lat=30.27, lon=-97.74)
    plugin.alerts["texas"] = far
    mem = flare_sources.MemorySourceStore()
    await mem.put("sabreplus", dict(MANIFEST, enabled=True))
    p = flare_sources.Poller(mem, now=lambda: NOW)
    p.note_at(GOOD["lat"], GOOD["lon"])
    p.note_at(far["lat"], far["lon"])
    async with httpx.AsyncClient(transport=httpx.MockTransport(plugin.handler)) as c:
        await p.run_once(c)

    world = (-90.0, -180.0, 90.0, 180.0)
    # A map zoomed out to the whole world is still only answered for here.
    mine = p.markers_for_bbox(world, near=(GOOD["lat"], GOOD["lon"]))
    theirs = p.markers_for_bbox(world, near=(far["lat"], far["lon"]))
    assert [m["id"] for m in mine] == ["sabreplus:" + GOOD["id"]]
    assert [m["id"] for m in theirs] == ["sabreplus:texas"]
    # And with nobody asking, nothing at all: this is the case the
    # published snapshots hit, and they are one file for every visitor.
    assert p.markers_for_bbox(world) == []


def test_a_region_sized_view_is_not_a_place():
    """A viewport stands in for a position only when it is small enough
    to be somewhere. Zoomed out to a region there is no "here" to answer
    for, and treating one as demand is what sent the poller to sea."""
    p = flare_sources.Poller(flare_sources.MemorySourceStore())
    p.note_view((36.0, -123.0, 50.0, -110.0))
    assert p.near == {}
    p.note_view((37.3, -122.0, 37.5, -121.8))
    assert list(p.near) == [(37.4, -121.9)]


@pytest.mark.asyncio
async def test_catalog_holds_the_last_good_count_and_flags_staleness():
    plugin = FakePlugin()
    mem = flare_sources.MemorySourceStore()
    await mem.put("sabreplus", dict(MANIFEST, enabled=True))
    clock = {"now": NOW}
    p = flare_sources.Poller(mem, now=lambda: clock["now"])
    async with httpx.AsyncClient(transport=httpx.MockTransport(plugin.handler)) as c:
        await p.run_once(c)
    src = p.public_sources()[0]
    assert src["count"] == 1 and src["stale"] is False
    # Every cell expires while nobody looks: the catalog still says 1, not 0.
    p.cells["sabreplus"].clear()
    p._last_poll.clear()
    plugin.alerts.clear()
    async with httpx.AsyncClient(transport=httpx.MockTransport(plugin.handler)) as c:
        await p.run_once(c)
    assert p.status["sabreplus"]["count"] == 0
    src = p.public_sources()[0]
    assert src["count"] == 1 and src["stale"] is False
    # A failing poll keeps the count and says so.
    p._last_poll.clear()

    def down(request):
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(down)) as c:
        await p.run_once(c)
    src = p.public_sources()[0]
    assert src["count"] == 1 and src["stale"] is True
    # An hour of nothing: the held count lapses.
    clock["now"] = NOW + timedelta(seconds=flare_sources.COUNT_HOLD_S + 1)
    src = p.public_sources()[0]
    assert src["count"] == 0 and src["stale"] is True


def test_an_unlisted_plugin_is_found_by_id_only(admin_app):
    c, mem = admin_app
    r = c.post("/api/admin/flare", json={"manifest": dict(MANIFEST, visibility="unlisted")},
               headers=auth("tok-admin"))
    assert r.status_code == 200, r.text
    r = c.post("/api/admin/flare", json={"manifest": dict(MANIFEST, id="secret", name="Secret",
                                                          visibility="private", trust="private")},
               headers=auth("tok-admin"))
    assert r.status_code == 200, r.text
    flare_sources.poller._sources_loaded = 0.0
    import asyncio
    asyncio.run(flare_sources.poller.refresh_sources())
    assert c.get("/api/flare/sources").json()["sources"] == []
    card = c.get("/api/flare/sources?id=sabreplus").json()["sources"][0]
    assert card["id"] == "sabreplus" and card["visibility"] == "unlisted"
    assert c.get("/api/flare/sources?id=secret").status_code == 404
    assert c.get("/api/flare/sources?id=nope").status_code == 404


def test_a_plugin_base_must_be_a_public_https_address():
    assert flare.fetchable_base("https://plugins.example.com")
    assert flare.fetchable_base("https://8.8.8.8/flare")
    for bad in ("http://plugins.example.com", "https://127.0.0.1", "https://169.254.169.254",
                "https://10.0.0.5", "https://192.168.1.1", "https://[::1]", "https://0.0.0.0",
                "", None, 42):
        assert not flare.fetchable_base(bad), bad
    assert flare.validate_manifest(dict(MANIFEST, base="https://169.254.169.254"))


@pytest.mark.asyncio
async def test_the_poller_refuses_redirects_and_oversized_bodies():
    mem = flare_sources.MemorySourceStore()
    await mem.put("sabreplus", dict(MANIFEST, enabled=True))

    def redirecting(request):
        return httpx.Response(302, headers={"location": "https://169.254.169.254/"})

    p = flare_sources.Poller(mem, now=lambda: NOW)
    async with httpx.AsyncClient(transport=httpx.MockTransport(redirecting),
                                 follow_redirects=True) as c:
        await p.run_once(c)
    assert p.status["sabreplus"]["ok"] is False
    assert "302" in p.status["sabreplus"]["last_error"]

    def huge(request):
        return httpx.Response(200, content=b"x" * (flare.MAX_BYTES + 1))

    p2 = flare_sources.Poller(mem, now=lambda: NOW)
    async with httpx.AsyncClient(transport=httpx.MockTransport(huge)) as c:
        await p2.run_once(c)
    assert p2.status["sabreplus"]["ok"] is False
    assert "bytes" in p2.status["sabreplus"]["last_error"]


@pytest.mark.asyncio
async def test_a_failing_source_is_backed_off_not_asked_every_minute():
    mem = flare_sources.MemorySourceStore()
    await mem.put("sabreplus", dict(MANIFEST, enabled=True))
    p = flare_sources.Poller(mem, now=lambda: NOW)
    src = dict(MANIFEST, enabled=True)
    for expected in range(1, 5):
        p._last_poll.pop("sabreplus", None)
        async with httpx.AsyncClient(
                transport=httpx.MockTransport(lambda r: httpx.Response(503))) as c:
            await p.run_once(c)
        assert p._fails["sabreplus"] == expected
    # Three strikes in, the next poll is not due at the usual interval.
    p._last_poll["sabreplus"] = time.monotonic()
    assert not p.due(src)
    # A good answer clears it.
    plugin = FakePlugin()
    p._last_poll.pop("sabreplus", None)
    async with httpx.AsyncClient(transport=httpx.MockTransport(plugin.handler)) as c:
        await p.run_once(c)
    assert "sabreplus" not in p._fails


@pytest.mark.asyncio
async def test_a_private_source_is_never_polled_for_the_shared_map():
    mem = flare_sources.MemorySourceStore()
    await mem.put("mine", dict(MANIFEST, id="mine", visibility="private",
                               trust="private", enabled=True))
    p = flare_sources.Poller(mem, now=lambda: NOW)
    plugin = FakePlugin()
    async with httpx.AsyncClient(transport=httpx.MockTransport(plugin.handler)) as c:
        await p.run_once(c)
    assert p.sources == {} and p.markers_for_bbox((-90, -180, 90, 180), near=HERE) == []



@pytest.mark.asyncio
async def test_a_cold_plugin_gets_time_to_start():
    """A plugin is usually a small service that scales to zero, and a
    cold container can take a minute to answer. Giving up sooner
    deadlocks the pair: it only stays warm because we poll it, and we
    only poll it if it answers. The handshake waits, and retries once."""
    mem = flare_sources.MemorySourceStore()
    await mem.put("sabreplus", dict(MANIFEST, enabled=True))
    plugin = FakePlugin()
    attempts = {"n": 0}

    def cold_once(request):
        if "handshake" in str(request.url):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise httpx.ConnectError("connection refused", request=request)
        return plugin.handler(request)

    p = flare_sources.Poller(mem, now=lambda: NOW)
    async with httpx.AsyncClient(transport=httpx.MockTransport(cold_once)) as c:
        await p.run_once(c)
    assert attempts["n"] == 2, "the first attempt should be retried"
    assert p.status["sabreplus"]["ok"] is True
    assert flare_sources.COLD_START_TIMEOUT_S >= 60


@pytest.mark.asyncio
async def test_cells_that_produced_alerts_are_asked_before_the_blind_sweep():
    """A plugin's coverage is a rectangle, and a rectangle over the
    United States is mostly ocean. A purely rotating sweep spends its
    turns on water, so a cell that has produced alerts before goes
    first."""
    mem = flare_sources.MemorySourceStore()
    await mem.put("sabreplus", dict(MANIFEST, enabled=True))
    plugin = FakePlugin()
    p = flare_sources.Poller(mem, now=lambda: NOW)
    async with httpx.AsyncClient(transport=httpx.MockTransport(plugin.handler)) as c:
        await p.run_once(c)
    good = p.productive.get("sabreplus", {})
    assert good, "cells that returned alerts should be remembered"
    bbox = p.handshakes["sabreplus"][1]["coverage"]["bbox"]
    # Nothing is hot, so the front of the queue is the productive cells
    # rather than wherever the rotating sweep happens to be pointing.
    asked = [point for point, _radius in p.cells_to_poll("sabreplus", bbox)]
    front = asked[: flare_sources.PRODUCTIVE_PER_POLL]
    assert set(front) <= set(good), front
    # A cell nobody has ever got anything from is not promoted.
    assert (0.5, 0.5) not in asked


@pytest.mark.asyncio
async def test_one_cell_a_cycle_waits_out_a_cold_start():
    """The handshake is cached for an hour, so most cycles never make one
    and the first thing to touch a cold container is a cell. One cell is
    allowed to wait; the rest keep the normal timeout, so a plugin that
    is genuinely down costs one wait per cycle rather than one per cell."""
    mem = flare_sources.MemorySourceStore()
    await mem.put("sabreplus", dict(MANIFEST, enabled=True))
    plugin = FakePlugin()
    waits = []

    def cold_cells(request):
        if "alerts" in str(request.url):
            waits.append(request.extensions.get("timeout", {}).get("connect"))
            if len(waits) == 1:
                raise httpx.ConnectTimeout("cold", request=request)
        return plugin.handler(request)

    p = flare_sources.Poller(mem, now=lambda: NOW)
    async with httpx.AsyncClient(transport=httpx.MockTransport(cold_cells)) as c:
        await p.run_once(c)
    # The first cell was retried, and the retry used the long timeout.
    assert len(waits) >= 2
    assert waits[1] == flare_sources.COLD_START_TIMEOUT_S
    # Later cells did not each pay for a wait.
    assert all(w == 20.0 for w in waits[2:]), waits
    assert p.status["sabreplus"]["ok"] is True


def test_a_route_becomes_a_chain_of_snapped_neighbourhoods():
    """A planned route is demand too, sampled every few kilometres and
    snapped before it is stored, so the plugin is asked about a chain of
    neighbourhoods and never handed the route itself."""
    p = flare_sources.Poller(flare_sources.MemorySourceStore())
    p.note_route([(37.0, -122.0), (37.0, -121.5)])       # about 44 km east
    points = list(p.routes)
    assert 5 <= len(points) <= 8
    step = flare_sources.ROUTE_SNAP_DEG
    for lat, lon in points:
        assert abs(lat / step - round(lat / step)) < 1e-6
        assert abs(lon / step - round(lon / step)) < 1e-6
    asked = p.cells_to_poll("sabreplus", [18.0, -168.0, 71.5, -66.5])
    assert len(asked) == len(points)
    assert {r for _, r in asked} == {float(flare_sources.ROUTE_FETCH_M)}


@pytest.mark.asyncio
async def test_alerts_along_a_corridor_reach_only_the_driver():
    """An alert a few hundred metres off the route is the driver's to see;
    one five kilometres off is not, and nobody without that route sees
    either."""
    national = [18.0, -168.0, 71.5, -66.5]
    plugin = FakePlugin(handshake={"coverage": {"bbox": national}})
    on = {k: v for k, v in GOOD.items() if k != "geometry"}
    on.update(id="on", lat=37.005, lon=-121.75)          # ~550 m north of the line
    off = dict(on, id="off", lat=37.05, lon=-121.75)      # ~5.5 km north of it
    plugin.alerts = {"on": on, "off": off}
    mem = flare_sources.MemorySourceStore()
    await mem.put("sabreplus", dict(MANIFEST, enabled=True))
    p = flare_sources.Poller(mem, now=lambda: NOW)
    path = [(37.0, -122.0), (37.0, -121.5)]
    p.note_route(path)
    async with httpx.AsyncClient(transport=httpx.MockTransport(plugin.handler)) as c:
        await p.run_once(c)
    world = (-90.0, -180.0, 90.0, 180.0)
    assert [m["id"] for m in p.markers_for_bbox(world, corridor=[path])] == ["sabreplus:on"]
    assert p.markers_for_bbox(world) == []
    assert p.markers_for_bbox(world, near=(34.0, -118.0)) == []


async def test_a_new_place_is_polled_at_once_then_followed_up(monkeypatch):
    # A relay has nothing for a neighbourhood nobody has asked about, and
    # fills it in over the next half minute. So a new place makes a
    # source due right away, and the poll that carried it owes two more.
    clock = [10_000.0]
    monkeypatch.setattr(flare_sources.time, "monotonic", lambda: clock[0])
    mem = flare_sources.MemorySourceStore()
    await mem.put("sabreplus", dict(MANIFEST, enabled=True))
    p = flare_sources.Poller(mem, now=lambda: NOW)
    plugin = FakePlugin()
    async with httpx.AsyncClient(transport=httpx.MockTransport(plugin.handler)) as c:
        await p.run_once(c)                # the first poll ever
        src = p.sources["sabreplus"]
        clock[0] += 1
        assert not p.due(src)              # just polled, nothing new

        p.note_at(*HERE)
        assert not p.due(src)              # new, but inside the floor
        clock[0] += flare_sources.URGENT_FLOOR_S
        assert p.due(src)                  # long before the 60 s period
        started = clock[0]
        await p.run_once(c)                # this poll carries the new place
        assert not p.due(src)
        assert p._rechecks["sabreplus"] == [started + d for d in flare_sources.RECHECKS_S]
        assert p._idle_wait() == min(flare_sources.IDLE_WAIT_S, flare_sources.RECHECKS_S[0])

        clock[0] = started + flare_sources.RECHECKS_S[0]
        assert p.due(src)                  # the first follow-up
        await p.run_once(c)
        assert p._rechecks["sabreplus"] == [started + flare_sources.RECHECKS_S[1]]
        clock[0] = started + flare_sources.RECHECKS_S[1]
        assert p.due(src)                  # the second
        await p.run_once(c)
        assert p._rechecks["sabreplus"] == []
        clock[0] += flare_sources.URGENT_FLOOR_S
        assert not p.due(src)              # and then back to the ordinary period


def test_a_place_already_warm_does_not_hurry_anything(monkeypatch):
    clock = [10_000.0]
    monkeypatch.setattr(flare_sources.time, "monotonic", lambda: clock[0])
    p = flare_sources.Poller(flare_sources.MemorySourceStore(), now=lambda: NOW)
    src = {"id": "sabreplus"}
    p.note_at(*HERE)
    p._last_poll["sabreplus"] = p._polled_from["sabreplus"] = clock[0] + 1
    clock[0] += 30
    p.note_at(*HERE)                       # the same person, still there
    p.note_at(HERE[0] + 0.0001, HERE[1])   # snaps to the same place
    assert not p.due(src)
    clock[0] += flare_sources.POLL_FLOOR_S
    assert p.due(src)                      # the ordinary period still applies


def test_a_new_stretch_of_route_hurries_the_poll_but_a_failing_source_waits(monkeypatch):
    clock = [10_000.0]
    monkeypatch.setattr(flare_sources.time, "monotonic", lambda: clock[0])
    p = flare_sources.Poller(flare_sources.MemorySourceStore(), now=lambda: NOW)
    ok, bad = {"id": "ok"}, {"id": "bad"}
    for sid in ("ok", "bad"):
        p._last_poll[sid] = p._polled_from[sid] = clock[0]
    p._fails["bad"] = flare_sources.FAILS_BEFORE_BACKOFF
    clock[0] += flare_sources.URGENT_FLOOR_S
    p.note_route([(37.30, -121.90), (37.40, -122.10)])
    assert p.due(ok)
    assert not p.due(bad)                  # backoff is never cut short


async def test_new_demand_wakes_the_loop_instead_of_waiting_out_the_tick():
    import asyncio

    p = flare_sources.Poller(flare_sources.MemorySourceStore(), now=lambda: NOW)
    passes = []

    async def fake_run_once(client):
        passes.append(time.monotonic())

    p.run_once = fake_run_once
    task = asyncio.create_task(p.run(lambda: None))
    try:
        for _ in range(50):
            if passes:
                break
            await asyncio.sleep(0.01)
        assert len(passes) == 1
        p.note_at(*HERE)
        for _ in range(100):
            if len(passes) > 1:
                break
            await asyncio.sleep(0.01)
        assert len(passes) == 2            # woke in well under the 15 s tick
    finally:
        task.cancel()


# ------------------------------------------------------------- shared data
def _shared_poller(alerts, *, shared=True, snapshot=True):
    p = flare_sources.Poller(store=flare_sources.MemorySourceStore())
    src = {"id": "cams", "name": "Cameras", "base": "https://cams.example",
           "visibility": "public", "trust": "community", "shared": shared}
    p.sources = {"cams": src}
    hs = {"capabilities": {"alerts": True, "snapshot": snapshot}, "kinds": ["CAMERA_SPEED"]}
    p.handshakes = {"cams": (0.0, hs)}
    p.alerts = {"cams": alerts}
    return p


def _camera(i, lat, lon):
    return {"id": f"c{i}", "kind": "CAMERA_SPEED", "lat": lat, "lon": lon,
            "report_ts": datetime.now(UTC).isoformat(), "ttl_s": 86400}


def test_a_shared_source_shows_across_the_map_with_nobody_near():
    """Fixed cameras are the same for everyone: a region-wide view, with
    no position of the asker's at all, still gets them."""
    p = _shared_poller([_camera(1, 37.78, -122.42), _camera(2, 41.88, -87.63)])
    got = p.markers_for_bbox([24.0, -125.0, 50.0, -66.0], near=None)
    assert sorted(m["id"] for m in got) == ["cams:c1", "cams:c2"]
    assert [m["id"] for m in p.markers_for_bbox([37.0, -123.0, 38.0, -122.0])] == ["cams:c1"]


def test_shared_is_the_catalog_entrys_call_and_needs_a_snapshot():
    """A plugin cannot declare itself shared, and a catalog entry marked
    shared without the snapshot capability is not treated as one: in both
    cases the small circle around the asker still applies."""
    cams = [_camera(1, 37.78, -122.42)]
    for shared, snapshot in ((False, True), (True, False)):
        p = _shared_poller(cams, shared=shared, snapshot=snapshot)
        assert p.markers_for_bbox([24.0, -125.0, 50.0, -66.0], near=None) == []
        near = p.markers_for_bbox([37.0, -123.0, 38.0, -122.0], near=(37.78, -122.42))
        assert [m["id"] for m in near] == ["cams:c1"]
    snap = {"capabilities": {"snapshot": True}}
    assert flare_sources.Poller.is_shared({"shared": True}, snap) is True
    assert flare_sources.Poller.is_shared({}, snap) is False


class _SnapshotClient:
    """Answers the handshake and the snapshot; records the paths asked for."""

    def __init__(self, alerts):
        self.alerts, self.paths = alerts, []

    def stream(self, method, url, **kwargs):
        path = url.split("cams.example")[1]
        self.paths.append(path)
        hs = {"protocol": "flare/1", "id": "cams", "name": "Cameras",
              "capabilities": {"alerts": True, "snapshot": True}, "kinds": ["CAMERA_SPEED"],
              "coverage": {"bbox": [18.0, -168.0, 71.5, -66.5]}, "refresh_s": 3600,
              "attribution": {"name": "x"}, "auth": "none"}
        body = hs if path.endswith("handshake") else {"alerts": self.alerts, "ttl_s": 3600}

        class R:
            status_code = 200

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def aclose(self):
                pass

            async def aiter_bytes(self):
                yield json.dumps(body).encode()
        return R()


@pytest.mark.asyncio
async def test_a_shared_source_is_read_whole_in_one_request():
    p = flare_sources.Poller(store=flare_sources.MemorySourceStore())
    src = {"id": "cams", "name": "Cameras", "base": "https://cams.example",
           "visibility": "public", "trust": "community", "shared": True}
    p.sources = {"cams": src}
    client = _SnapshotClient([_camera(i, 30.0 + i * 0.01, -100.0) for i in range(700)])
    assert await p.poll_source(src, client) == 700   # past the 500 cap of an alerts answer
    assert client.paths == ["/flare/v1/handshake", "/flare/v1/snapshot"]
    assert p.status["cams"]["ok"] is True and p.card("cams")["shared"] is True
    # A fixed list is re-read on its own period, not whenever somebody
    # looks somewhere new.
    p.note_at(40.0, -100.0)
    assert p.due(src) is False


def test_the_circle_around_a_person_is_the_decided_size():
    """2026-10-03: about 25 miles around the person, a view up to 4
    degrees across. Serving must stay inside what is fetched, with room
    for half a snap step (6.2 km at most)."""
    assert flare_sources.NEAR_SERVE_M == 40_000
    assert flare_sources.VIEW_MAX_DEG == 4.0
    assert flare_sources.NEAR_FETCH_M >= flare_sources.NEAR_SERVE_M + 6_200
    # The web map asks for community alerts up to the same view width.
    app_js = (Path(__file__).resolve().parents[1] / "src/ca_roads_demo/static/map-app.js").read_text(encoding="utf-8")
    assert "if (span <= 4.0) {" in app_js
