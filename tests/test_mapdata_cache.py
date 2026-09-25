"""/api/mapdata: viewports snap to a grid so near-identical bboxes share
one built response, and the endpoint sits in the soft limiter."""

from starlette.testclient import TestClient

from ca_roads_demo import app as demo_app


class _Req:
    def __init__(self, bbox):
        self.query_params = {"bbox": bbox}


def test_bbox_snaps_outward_to_the_grid():
    assert demo_app._bbox_params(_Req("37.123456,-122.987654,37.2,-122.9")) == (
        37.1, -123.0, 37.2, -122.9)
    # Never past the poles or the antimeridian.
    assert demo_app._bbox_params(_Req("-89.99,-179.99,89.99,179.99")) == (
        -90.0, -180.0, 90.0, 180.0)
    assert demo_app._bbox_params(_Req("40,-120,39,-121")) is None


def test_near_identical_bboxes_share_one_build(monkeypatch):
    calls = []

    async def fake_build(box, want, *, geo_only=False, near=None, corridor=None, feed_budget=None):
        calls.append(box)
        return [], 1, 1, False

    monkeypatch.setattr(demo_app, "build_markers", fake_build)
    demo_app._MAPDATA_CACHE.clear()
    client = TestClient(demo_app.app)
    for sixth in ("1", "2", "3"):
        r = client.get(f"/api/mapdata?bbox=37.00000{sixth},-122.00000{sixth},37.01,-121.99")
        assert r.status_code == 200
    assert len(calls) == 1


def test_mapdata_is_soft_limited():
    assert "/api/mapdata" in demo_app.SoftLimit.PREFIXES


def test_a_cached_answer_keeps_only_its_gzipped_body(monkeypatch):
    """Each entry used to hold the raw body as well, five times the size
    of the gzipped one, and a full cache of nationwide answers was enough
    to push the instance past its memory limit. A client that does not
    take gzip still gets the right body, rebuilt on the way out."""
    async def fake_build(box, want, *, geo_only=False, near=None, corridor=None, feed_budget=None):
        return [{"kind": "incident", "lat": 37.0, "lon": -122.0}], 1, 1, False

    monkeypatch.setattr(demo_app, "build_markers", fake_build)
    demo_app._MAPDATA_CACHE.clear()
    client = TestClient(demo_app.app)
    url = "/api/mapdata?bbox=37.0,-122.0,37.01,-121.99"
    first = client.get(url, headers={"Accept-Encoding": "gzip"})
    assert first.status_code == 200
    entry = next(iter(demo_app._MAPDATA_CACHE.values()))
    assert not any(isinstance(v, bytes) and v.startswith(b"{") for v in entry)
    plain = client.get(url, headers={"Accept-Encoding": "identity"})
    assert plain.status_code == 200
    assert plain.json()["markers"][0]["kind"] == "incident"
    assert plain.headers["ETag"] == first.headers["ETag"]


def test_the_cache_is_bounded_in_bytes(monkeypatch):
    async def fake_build(box, want, *, geo_only=False, near=None, corridor=None, feed_budget=None):
        return [{"kind": "incident", "lat": 37.0, "lon": -122.0, "n": i}
                for i in range(50)], 1, 1, False

    monkeypatch.setattr(demo_app, "build_markers", fake_build)
    monkeypatch.setattr(demo_app, "_MAPDATA_CACHE_BYTES", 1)
    demo_app._MAPDATA_CACHE.clear()
    client = TestClient(demo_app.app)
    for lat in ("36", "37", "38"):
        client.get(f"/api/mapdata?bbox={lat}.0,-122.0,{lat}.01,-121.99")
    assert len(demo_app._MAPDATA_CACHE) <= 1


def test_a_route_ahead_is_its_own_answer_and_keeps_the_relay_warm(monkeypatch):
    calls, noted = [], []

    async def fake_build(box, want, *, geo_only=False, near=None, corridor=None, feed_budget=None):
        calls.append(corridor)
        return [], 1, 1, False

    monkeypatch.setattr(demo_app, "build_markers", fake_build)
    monkeypatch.setattr(demo_app.flare_sources.poller, "note_route",
                        lambda path: noted.append(list(path)))
    demo_app._MAPDATA_CACHE.clear()
    client = TestClient(demo_app.app)
    base = "/api/mapdata?bbox=37.0,-122.0,37.01,-121.99&at=37.005,-121.995"
    assert client.get(base).status_code == 200
    assert client.get(base + "&ahead=37.005,-121.995;37.05,-121.9").status_code == 200
    ahead = [(37.005, -121.995), (37.05, -121.9)]
    assert calls == [None, [ahead]], "a route ahead is never served from the plain answer"
    assert noted == [ahead]
    # A malformed stretch is ignored, and the plain answer comes from cache.
    assert client.get(base + "&ahead=37.005,-121.995;bogus").status_code == 200
    assert len(calls) == 2
