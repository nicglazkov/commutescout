import json

import pytest
from starlette.testclient import TestClient

from ca_roads_demo.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_event_beacon_accepts_allowlisted(client, capsys):
    r = client.post("/api/event", json={"event": "pageview"})
    assert r.status_code == 200
    logged = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert logged["event"] == "pageview"
    assert "visitor" in logged and len(logged["visitor"]) == 12


def test_event_beacon_rejects_unknown(client):
    assert client.post("/api/event", json={"event": "evil"}).status_code == 400
    assert client.post("/api/event", content=b"junk").status_code == 400


def test_feedback_carries_question(client, capsys):
    r = client.post("/api/event", json={
        "event": "feedback_down", "question": "Is 17 clear?" * 100,
    })
    assert r.status_code == 200
    logged = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert logged["event"] == "feedback_down"
    assert len(logged["question"]) <= 300  # capped


def test_safe_zone_falls_back_to_pacific():
    from ca_roads_demo.app import _safe_zone

    assert _safe_zone("America/New_York").key == "America/New_York"
    assert _safe_zone("Not/AZone").key == "America/Los_Angeles"
    assert _safe_zone(None).key == "America/Los_Angeles"
    assert _safe_zone("x" * 500).key == "America/Los_Angeles"


def test_geocode_endpoint_validates_and_resolves(client):
    assert client.get("/api/geocode").status_code == 400
    assert client.get("/api/geocode?q=" + "x" * 300).status_code == 400
    # Gazetteer hit: resolves offline, no network involved.
    r = client.get("/api/geocode?q=Sacramento")
    assert r.status_code == 200
    cands = r.json()["candidates"]
    assert cands and "Sacramento" in cands[0]["name"]


def test_mapdata_rejects_bad_bbox(client):
    assert client.get("/api/mapdata").status_code == 400
    assert client.get("/api/mapdata?bbox=1,2,3").status_code == 400
    assert client.get("/api/mapdata?bbox=40,-120,39,-121").status_code == 400


def test_suggest_keeps_typed_house_number(client, monkeypatch):
    import httpx
    import respx

    from ca_roads_mcp import geocode as geo

    with respx.mock:
        respx.get(geo.PHOTON_URL).mock(return_value=httpx.Response(200, json={
            "features": [{
                "geometry": {"coordinates": [-122.26, 37.39]},
                "properties": {"name": "Skyline Boulevard",
                               "osm_key": "highway",
                               "osm_value": "residential",
                               "city": "Woodside", "state": "California"},
            }]
        }))
        r = client.get("/api/suggest?q=2101%20skyline%20blvd&lat=37.35&lon=-121.94")
    s = r.json()["suggestions"][0]
    assert s["name"].startswith("2101 Skyline Boulevard")
    assert s["approx"] is True


def test_flow_endpoint_without_key_returns_nulls(client, monkeypatch):
    monkeypatch.delenv("TOMTOM_API_KEY", raising=False)
    r = client.get("/api/flow?pts=37.5,-122.2|38.0,-121.5")
    assert r.status_code == 200
    assert r.json()["flow"] == [None, None]
    assert client.get("/api/flow").status_code == 400


def test_traffic_tile_404_without_key(client, monkeypatch):
    monkeypatch.delenv("TOMTOM_API_KEY", raising=False)
    assert client.get("/api/traffictile/10/163/395.png").status_code == 404


def test_snap_path_downsamples_and_rejects_wanderers():
    from ca_roads_demo.app import _snap_path

    coords = [[-121.0 + i * 0.001, 38.0 + i * 0.001] for i in range(300)]
    path = _snap_path(coords, straight_km=40.0, route_km=45.0)
    assert path is not None
    assert len(path) <= 62
    assert path[0] == [38.0, -121.0]
    assert path[-1] == [38.299, -120.701]
    # A route three times the crow-flies distance is a detour tour, not
    # the closed stretch: keep the straight line instead.
    assert _snap_path(coords, straight_km=4.0, route_km=30.0) is None
    assert _snap_path([], straight_km=4.0, route_km=4.0) is None
