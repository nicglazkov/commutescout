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

    async def fake_build(box, want, *, geo_only=False, near=None):
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
