"""plugins/osm-cameras: the OpenStreetMap response becomes the right
records, and the service is a conforming, read-only Flare plugin."""

import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest

from ca_roads import flare

HERE = Path(__file__).resolve().parent.parent / "plugins" / "osm-cameras"

OVERPASS = {
    "osm3s": {"timestamp_osm_base": "2026-10-01T00:00:00Z"},
    "elements": [
        {"type": "node", "id": 1, "lat": 38.9001, "lon": -77.0301,
         "tags": {"highway": "speed_camera", "maxspeed": "25 mph"}},
        {"type": "node", "id": 2, "lat": 38.9002, "lon": -77.0302,
         "tags": {"highway": "speed_camera", "enforcement": "traffic_signals"}},
        {"type": "node", "id": 3, "lat": 38.9003, "lon": -77.0303,
         "tags": {"highway": "speed_camera", "maxspeed": "signals"}},
        # A relation's device: first with tags that say nothing about what
        # it enforces, then again as a bare skeleton.
        {"type": "node", "id": 4, "lat": 38.9004, "lon": -77.0304,
         "tags": {"highway": "speed_camera"}},
        {"type": "relation", "id": 9,
         "tags": {"type": "enforcement", "enforcement": "traffic_signals"},
         "members": [{"type": "node", "ref": 4, "role": "device"},
                     {"type": "way", "ref": 77, "role": "from"}]},
        {"type": "node", "id": 4, "lat": 38.9004, "lon": -77.0304},
        # A device that is not tagged as a camera on its own.
        {"type": "relation", "id": 10, "tags": {"type": "enforcement", "enforcement": "maxspeed",
                                                "maxspeed": "45"},
         "members": [{"type": "node", "ref": 5, "role": "device"}]},
        {"type": "node", "id": 5, "lat": 40.0, "lon": -105.0},
        # Not a camera at all.
        {"type": "node", "id": 6, "lat": 40.1, "lon": -105.1, "tags": {"highway": "crossing"}},
    ],
}


def load(name: str, **env):
    spec = importlib.util.spec_from_file_location(f"osm_cameras_{name}", HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def server(tmp_path, monkeypatch):
    refresh = load("refresh")
    data = tmp_path / "cameras.json"
    data.write_text(json.dumps({"as_of": "2026-10-01T00:00:00Z",
                                "cameras": refresh.cameras(OVERPASS)}), encoding="utf-8")
    monkeypatch.setenv("CAMERAS_FILE", str(data))
    return load("server")


def test_overpass_elements_become_camera_records():
    found = {c["id"]: c for c in load("refresh").cameras(OVERPASS)}
    assert sorted(found) == [1, 2, 3, 4, 5]
    assert found[1] == {"id": 1, "kind": "CAMERA_SPEED", "lat": 38.9001, "lon": -77.0301, "mph": 25}
    assert found[2]["kind"] == "CAMERA_RED_LIGHT" and "mph" not in found[2]
    assert found[3]["kind"] == "CAMERA_SPEED" and "mph" not in found[3]   # "signals" is no limit
    assert found[4]["kind"] == "CAMERA_RED_LIGHT"                         # the relation decides
    assert found[5] == {"id": 5, "kind": "CAMERA_SPEED", "lat": 40.0, "lon": -105.0, "mph": 45}


def test_limits_are_read_as_miles_per_hour_or_not_at_all():
    limit = load("refresh").limit_mph
    assert limit("35 mph") == 35 and limit("35") == 35 and limit(" 55MPH ") == 55
    assert limit("signals") is None and limit("50 km/h") is None and limit(None) is None
    assert limit("300") is None


def test_a_refresh_that_lost_most_cameras_is_refused(tmp_path, monkeypatch, capsys):
    refresh = load("refresh")
    out = tmp_path / "cameras.json"
    out.write_text(json.dumps({"as_of": "x", "cameras": [{"id": i} for i in range(100)]}),
                   encoding="utf-8")
    saved = tmp_path / "overpass.json"
    saved.write_text(json.dumps(OVERPASS), encoding="utf-8")
    monkeypatch.setattr(refresh, "OUT", out)
    assert refresh.main([str(saved)]) == 1
    assert len(json.loads(out.read_text(encoding="utf-8"))["cameras"]) == 100


@pytest.mark.asyncio
async def test_the_plugin_passes_the_conformance_check(server):
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="https://plugin.example") as c:
        rep = await flare.check_plugin("https://plugin.example", client=c)
    assert rep.success, rep.text()


@pytest.mark.asyncio
async def test_alerts_are_valid_nearest_first_and_link_to_their_record(server):
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="https://plugin.example") as c:
        hs = (await c.get("/flare/v1/handshake")).json()
        assert flare.validate_handshake(hs) == []
        assert hs["capabilities"] == {"alerts": True, "report": False, "confirm": False,
                                      "notify": False}
        body = (await c.get("/flare/v1/alerts",
                            params={"lat": 38.9, "lon": -77.03, "r": 2000})).json()
        got = body["alerts"]
        assert [a["id"] for a in got] == [f"osm-cameras:n{i}" for i in (1, 2, 3, 4)]
        for a in got:
            assert flare.validate_alert(a) == [], a
            assert a["notify"] is False
        assert got[0]["description"] == "Speed camera, limit 25 mph."
        assert got[0]["extra"] == {"limit_mph": 25}
        assert got[0]["source_url"] == "https://www.openstreetmap.org/node/1"
        assert got[1]["description"] == "Red light camera."
        assert body["as_of"] == "2026-10-01T00:00:00Z"
        # Denver's camera is not in a search around Washington.
        far = (await c.get("/flare/v1/alerts",
                           params={"lat": 40.0, "lon": -105.0, "r": 500})).json()["alerts"]
        assert [a["id"] for a in far] == ["osm-cameras:n5"]


@pytest.mark.asyncio
async def test_bad_and_out_of_range_requests_are_refused(server):
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="https://plugin.example") as c:
        r = await c.get("/flare/v1/alerts", params={"lat": 51.5, "lon": -0.1, "r": 1000})
        assert r.status_code == 422 and r.json()["error"]["code"] == "outside_coverage"
        r = await c.get("/flare/v1/alerts", params={"lat": "nan", "lon": -77, "r": 1000})
        assert r.status_code == 400
        r = await c.get("/flare/v1/alerts", params={"lon": -77})
        assert r.status_code == 400
        assert (await c.post("/flare/v1/report", json={})).status_code in (404, 405)


def test_the_shipped_file_is_what_the_server_expects():
    data = json.loads((HERE / "cameras.json").read_text(encoding="utf-8"))
    assert data["as_of"] and len(data["cameras"]) > 1000
    for cam in data["cameras"]:
        assert cam["kind"] in ("CAMERA_SPEED", "CAMERA_RED_LIGHT")
        assert 18 <= cam["lat"] <= 71.5 and -168 <= cam["lon"] <= -66.5, cam
