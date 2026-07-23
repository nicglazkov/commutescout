"""Road snapper: quality gates, caching, and marker application."""

import httpx
import respx

from ca_roads_demo import roadsnap


def setup_function(_fn):
    roadsnap._mem.clear()
    roadsnap._queue.clear()
    roadsnap._queued.clear()
    roadsnap._pairs.clear()


def _route(coords, distance):
    return {"routes": [{"distance": distance,
                        "geometry": {"type": "LineString",
                                     "coordinates": coords}}]}


async def test_snap_returns_road_shape():
    coords = [[-121.9, 37.3], [-121.91, 37.31], [-121.92, 37.33]]
    with respx.mock:
        respx.get(url__regex=r".*router\.project-osrm\.org.*").mock(
            return_value=httpx.Response(200, json=_route(coords, 4000)))
        async with httpx.AsyncClient() as client:
            path = await roadsnap._snap(client, 37.3, -121.9, 37.33, -121.92)
    assert path[0] == [37.3, -121.9] and path[-1] == [37.33, -121.92]


async def test_snap_rejects_absurd_detours():
    # Straight distance ~3.7 km but the route is 40 km: endpoints are
    # on different roads; the gate refuses to draw a wrong shape.
    coords = [[-121.9, 37.3], [-121.92, 37.33]]
    with respx.mock:
        respx.get(url__regex=r".*router\.project-osrm\.org.*").mock(
            return_value=httpx.Response(200, json=_route(coords, 40000)))
        async with httpx.AsyncClient() as client:
            path = await roadsnap._snap(client, 37.3, -121.9, 37.33, -121.92)
    assert path is None


async def test_snap_skips_tiny_and_huge_pairs():
    async with httpx.AsyncClient() as client:
        assert await roadsnap._snap(client, 37.3, -121.9,
                                    37.3001, -121.9001) is None
        assert await roadsnap._snap(client, 37.3, -121.9,
                                    47.0, -100.0) is None


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
