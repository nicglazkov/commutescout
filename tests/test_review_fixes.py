"""Fixes from the fresh-eyes review of the 2026-09-16 merges."""

import asyncio
import contextlib
import dataclasses

from starlette.testclient import TestClient

from ca_roads.budget import DailyCounter
from ca_roads_mcp import corridors as corr
from ca_roads_mcp import server
from ca_roads_mcp.ratelimit import RateLimiter, RateLimitMiddleware
from test_mcp_live_fixes import BASE_CLOSURE, FakeRoad


def test_basin_trips_do_not_resolve_to_a_few_miles_of_i15():
    # Los Angeles is no longer an alias, so alias resolution fails...
    assert corr.resolve_corridor("Los Angeles", "Riverside") is None
    # ...and snapping still puts Los Angeles ON the corridor (I-10 leg).
    i15 = next(c for c in corr.CORRIDORS if "I-15" in c.routes)
    dist, along = corr.distance_to_corridor(i15, 34.05, -118.24)
    assert dist < 2_000 and along < 5_000


async def test_same_stretch_pair_is_refused(monkeypatch):
    """San Bernardino and Ontario both sit near the I-15 junction; that
    corridor is not the drive between them."""
    monkeypatch.setattr(server, "get_road", lambda: FakeRoad())
    res = await server.check_route("Ontario, CA", "San Bernardino",
                                   from_coords="34.07,-117.55",
                                   to_coords="34.11,-117.29")
    assert "error" in res and "same stretch" in res["error"]


async def test_los_angeles_to_las_vegas_has_no_off_corridor_note(monkeypatch):
    monkeypatch.setattr(server, "get_road", lambda: FakeRoad())
    res = await server.check_route("Los Angeles", "Las Vegas",
                                   from_coords="34.05,-118.24",
                                   to_coords="36.17,-115.14")
    assert "error" not in res
    # Las Vegas sits past the state-line end, so a note about IT is
    # honest; Los Angeles now snaps onto the I-10 leg and gets none.
    assert not any("Los Angeles" in n for n in res.get("notes", []))


async def test_closures_sorted_by_distance_before_the_cap(monkeypatch):
    far = dataclasses.replace(BASE_CLOSURE, index="far", begin_lat=41.0,
                              begin_lon=-121.0)
    near = dataclasses.replace(BASE_CLOSURE, index="near", begin_lat=37.05,
                               begin_lon=-121.95)
    monkeypatch.setattr(server, "get_road", lambda: FakeRoad(closures=[far, near]))
    monkeypatch.setattr(server, "_attach_scenery", _noop_attach)
    res = await server.get_lane_closures(center="37.0,-121.9", radius_km=600)
    assert [c["index"] for c in res["closures"]] == ["near", "far"]


async def _noop_attach(*_a, **_k):
    return None


async def test_daily_cap_counts_only_requests_the_bucket_let_through():
    served = []

    async def inner(scope, receive, send):
        served.append(1)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    app = RateLimitMiddleware(inner, RateLimiter(capacity=1, refill_per_second=0),
                              daily_limit=1)
    statuses = []

    async def send(msg):
        if msg["type"] == "http.response.start":
            statuses.append(msg["status"])

    async def receive():
        return {"type": "http.request"}

    scope = {"type": "http", "path": "/mcp", "headers": [],
             "client": ("203.0.113.9", 1)}
    await app(scope, receive, send)   # served: bucket 1 -> 0, day 1 -> 0
    await app(scope, receive, send)   # bucket empty: 429, day untouched
    assert statuses == [200, 429] and len(served) == 1
    assert app.daily.used("203.0.113.9") == 1


def test_daily_counter_prune_keeps_the_heavy_keys():
    c = DailyCounter(max_keys=4)
    for _ in range(9):
        c.allow("heavy", 100)
    for k in ("a", "b", "c"):
        c.allow(k, 100)
    assert c.allow("fresh", 100)  # triggers a prune
    assert c.used("heavy") == 9
    assert "fresh" in c.counts


def test_staticmap_with_a_refused_tile_is_not_cached(monkeypatch):
    from ca_roads_demo import app as demo_app

    monkeypatch.setenv("STADIA_API_KEY", "k")
    monkeypatch.delenv("STATICMAP_SIGNING_KEY", raising=False)
    monkeypatch.setattr(demo_app, "STADIA_TILES_DAILY", 0)  # budget spent
    demo_app._STATICMAP_CACHE.clear()
    client = TestClient(demo_app.app)
    r = client.get("/api/staticmap?lat=37.3382&lon=-121.8863&z=11&k=incident")
    assert r.status_code == 200
    assert r.headers["Cache-Control"] == "no-store"
    assert not demo_app._STATICMAP_CACHE


def test_signing_key_is_its_own_secret(monkeypatch):
    from ca_roads_demo import staticmap_sig

    monkeypatch.delenv("STATICMAP_SIGNING_KEY", raising=False)
    monkeypatch.setenv("TELEMETRY_SALT", "x" * 32)
    assert staticmap_sig.verify({"lat": "1", "lon": "2"})  # no key: check off
    monkeypatch.setenv("STATICMAP_SIGNING_KEY", "y" * 32)
    assert not staticmap_sig.verify({"lat": "1", "lon": "2"})


async def test_lifespan_load_completes_before_background_tasks(monkeypatch):
    from ca_roads_demo import app, roadsnap, snapshot, vitals

    order = []

    async def load():
        await asyncio.sleep(0.02)
        order.append("load")
        return True

    async def prewarm():
        order.append("prewarm")

    async def quiet():
        return None

    monkeypatch.setattr(roadsnap, "load_persisted", load)
    monkeypatch.setattr(app, "_prewarm", prewarm)
    monkeypatch.setattr(snapshot, "run", quiet)
    monkeypatch.setattr(vitals, "run", quiet)
    async with app._lifespan(None):
        await asyncio.sleep(0.01)
    assert order[0] == "load" and "prewarm" in order


def test_mapdata_warming_build_is_never_served_from_cache(monkeypatch):
    from ca_roads_demo import app as demo_app

    calls = []

    async def build(box, want, *, geo_only=False, near=None):
        calls.append(1)
        warming = len(calls) == 1
        return [], (0 if warming else 1), 1, False

    monkeypatch.setattr(demo_app, "build_markers", build)
    demo_app._MAPDATA_CACHE.clear()
    client = TestClient(demo_app.app)
    url = "/api/mapdata?bbox=37.0,-122.0,37.05,-121.95"
    first = client.get(url)
    assert first.headers["Cache-Control"] == "no-store"
    second = client.get(url)
    assert "max-age=30" in second.headers["Cache-Control"]
    third = client.get(url)
    assert "max-age=30" in third.headers["Cache-Control"]
    assert len(calls) == 2  # warming, then one real build, then a hit


async def test_keyless_worker_never_tries_the_mirror(monkeypatch):
    from ca_roads_demo import roadsnap

    monkeypatch.delenv("STADIA_API_KEY", raising=False)
    loads = []

    async def load():
        loads.append(1)
        return False

    async def stop(_s):
        raise asyncio.CancelledError

    monkeypatch.setattr(roadsnap, "load_persisted", load)
    monkeypatch.setattr(roadsnap, "_sleep", stop)
    with contextlib.suppress(asyncio.CancelledError):
        await roadsnap._drain(None)
    assert not loads
