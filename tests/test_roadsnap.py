"""Road snapper: quality gates, caching, and marker application."""

import httpx
import pytest
import respx

from ca_roads_demo import roadsnap

from test_valhalla import encode_polyline6

ROUTE_RE = r".*api\.stadiamaps\.com/route/v1.*"


def setup_function(_fn):
    roadsnap._mem.clear()
    roadsnap._queue.clear()
    roadsnap._queued.clear()
    roadsnap._pairs.clear()


@pytest.fixture(autouse=True)
def _routing_key(monkeypatch):
    monkeypatch.setenv("STADIA_API_KEY", "test-key")


def _trip(points, km, maneuvers=None):
    """Valhalla response: points are [lat, lon], length in kilometers."""
    leg = {"shape": encode_polyline6(points)}
    if maneuvers is not None:
        leg["maneuvers"] = maneuvers
    return {"trip": {"legs": [leg],
                     "summary": {"length": km, "time": 600}}}


async def test_snap_returns_road_shape():
    points = [[37.3, -121.9], [37.31, -121.91], [37.33, -121.92]]
    with respx.mock:
        respx.post(url__regex=ROUTE_RE).mock(
            return_value=httpx.Response(200, json=_trip(points, 4.0)))
        async with httpx.AsyncClient() as client:
            path = await roadsnap._snap(client, 37.3, -121.9, 37.33, -121.92)
    assert path[0] == [37.3, -121.9] and path[-1] == [37.33, -121.92]


async def test_snap_rejects_absurd_detours():
    # Straight distance ~3.7 km but the route is 40 km: endpoints are
    # on different roads; the gate refuses to draw a wrong shape.
    points = [[37.3, -121.9], [37.33, -121.92]]
    with respx.mock:
        respx.post(url__regex=ROUTE_RE).mock(
            return_value=httpx.Response(200, json=_trip(points, 40.0)))
        async with httpx.AsyncClient() as client:
            path = await roadsnap._snap(client, 37.3, -121.9, 37.33, -121.92)
    assert path is None


async def test_snap_skips_tiny_and_huge_pairs():
    async with httpx.AsyncClient() as client:
        assert await roadsnap._snap(client, 37.3, -121.9,
                                    37.3001, -121.9001) is None
        assert await roadsnap._snap(client, 37.3, -121.9,
                                    47.0, -100.0) is None


async def test_snap_without_key_raises_not_tombstones(monkeypatch):
    """A keyless process must never write pairs off as unroutable: the
    drain loop gates on _ready() and a direct call raises (the generic
    requeue path) instead of returning the cached-forever None."""
    monkeypatch.delenv("STADIA_API_KEY", raising=False)
    assert roadsnap._ready() is False
    async with httpx.AsyncClient() as client:
        with pytest.raises(RuntimeError):
            await roadsnap._snap(client, 37.3, -121.9, 37.33, -121.92)


async def test_snap_toll_sends_heading_and_validates():
    points = [[37.30, -121.90], [37.31, -121.91], [37.33, -121.92]]
    maneuvers = [{"street_names": ["US 101"], "length": 4.0}]
    with respx.mock:
        route = respx.post(url__regex=ROUTE_RE).mock(
            return_value=httpx.Response(
                200, json=_trip(points, 4.0, maneuvers)))
        async with httpx.AsyncClient() as client:
            got = await roadsnap._snap_toll(
                client, 37.30, -121.90, 37.33, -121.92, 330.0, "101")
    body = route.calls[0].request.read()
    assert b'"heading"' in body and b'"heading_tolerance"' in body
    assert b'"radius"' in body
    assert got["path"][0] == [37.3, -121.9]
    assert got["a"] == [37.3, -121.9] and got["b"] == [37.33, -121.92]


async def test_snap_toll_rejects_off_route_legs():
    points = [[37.30, -121.90], [37.33, -121.92]]
    maneuvers = [{"street_names": ["Airport Blvd"], "length": 4.0}]
    with respx.mock:
        respx.post(url__regex=ROUTE_RE).mock(
            return_value=httpx.Response(
                200, json=_trip(points, 4.0, maneuvers)))
        async with httpx.AsyncClient() as client:
            got = await roadsnap._snap_toll(
                client, 37.30, -121.90, 37.33, -121.92, 330.0, "101")
    assert got is None


async def test_snap_toll_widens_then_transient():
    """Both search radii coming back with no edge candidate is a
    transient miss (retryable), not a tombstone."""
    with respx.mock:
        route = respx.post(url__regex=ROUTE_RE).mock(
            return_value=httpx.Response(400, json={"error": "no edges"}))
        async with httpx.AsyncClient() as client:
            with pytest.raises(roadsnap.TransientSnapError):
                await roadsnap._snap_toll(
                    client, 37.30, -121.90, 37.33, -121.92, 330.0, "101")
    assert route.call_count == 2  # 60 m then 150 m


def test_apply_attaches_cached_and_queues_unknown():
    key = roadsnap._key(37.3, -121.9, 37.33, -121.92)
    roadsnap._mem[key] = [[37.3, -121.9], [37.31, -121.905],
                          [37.33, -121.92]]
    known = {"kind": "lane_closure", "lat": 37.3, "lon": -121.9,
             "end": [37.33, -121.92]}
    unknown = {"kind": "lane_closure", "lat": 38.0, "lon": -120.0,
               "end": [38.1, -120.1]}
    native = {"kind": "lane_closure", "lat": 39.0, "lon": -119.0,
              "path": [[39.0, -119.0], [39.01, -119.01], [39.02, -119.0]]}
    two_pt = {"kind": "lane_closure", "lat": 40.0, "lon": -118.0,
              "path": [[40.0, -118.0], [40.2, -118.3]]}
    roadsnap.apply([known, unknown, native, two_pt])
    assert len(known["path"]) == 3            # cached snap attached
    assert "path" not in unknown              # queued, dot for now
    assert len(roadsnap._queue) == 2          # unknown + the 2pt pair
    assert native["path"][1] == [39.01, -119.01]   # untouched


def test_failed_snaps_are_remembered_as_no_line():
    key = roadsnap._key(37.3, -121.9, 37.33, -121.92)
    roadsnap._mem[key] = None
    m = {"kind": "lane_closure", "lat": 37.3, "lon": -121.9,
         "end": [37.33, -121.92]}
    roadsnap.apply([m])
    assert "path" not in m and not roadsnap._queue
