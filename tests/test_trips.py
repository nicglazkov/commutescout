"""Shareable trip snapshots: polyline codec, creation, and the
server-rendered page."""

import pytest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient
from tests.test_watch import MemoryStore

from ca_roads_demo import trips, watch


class TripStore(MemoryStore):
    def __init__(self):
        super().__init__()
        self.trips = {}

    async def create_trip(self, trip_id, data):
        from tests.test_watch import _firestore_would_reject

        if _firestore_would_reject(data):
            raise ValueError("400 Nested arrays are not allowed")
        self.trips[trip_id] = dict(data)

    async def get_trip(self, trip_id):
        return dict(self.trips[trip_id]) if trip_id in self.trips else None


@pytest.fixture
def client(monkeypatch):
    mem = TripStore()
    monkeypatch.setattr(watch, "get_store", lambda: mem)
    app = Starlette(routes=[
        Route("/api/trip", trips.api_trip_create, methods=["POST"]),
        Route("/api/trip/{trip_id}", trips.api_trip_get),
        Route("/trip/{trip_id}", trips.trip_page),
    ])
    return TestClient(app)


ROUTE = {
    "from_name": "San Jose", "to_name": "San Francisco",
    "miles": 54.2, "minutes": 66, "via": "Bayshore Freeway",
    "latlngs": [[37.34, -121.89], [37.45, -122.0], [37.6, -122.15],
                [37.77, -122.42]],
    "steps": [{"text": "Head north on CA-87", "miles": 1.2},
              {"text": "Merge onto US-101 N", "miles": 44.0}],
}


def test_polyline_roundtrip():
    pts = [[37.33821, -121.88633], [37.44987, -122.00021],
           [38.0, -120.5]]
    assert trips.decode_polyline(trips.encode_polyline(pts)) == pts


def test_create_and_fetch_trip(client):
    r = client.post("/api/trip", json=ROUTE)
    assert r.status_code == 200
    trip_id = r.json()["id"]
    assert r.json()["url"].endswith("/trip/" + trip_id)
    got = client.get("/api/trip/" + trip_id).json()
    assert got["from_name"] == "San Jose"
    assert got["miles"] == 54.2
    assert trips.decode_polyline(got["polyline"])[0] == [37.34, -121.89]
    assert "expire_at" not in got  # internal field stays internal


def test_trip_validation(client):
    assert client.post("/api/trip", json={}).status_code == 400
    ny = {**ROUTE, "latlngs": [[40.7, -74.0], [40.8, -74.1]]}
    assert client.post("/api/trip", json=ny).status_code == 400
    too_many = {**ROUTE,
                "latlngs": [[37.3 + i / 10000, -121.9] for i in range(600)]}
    assert client.post("/api/trip", json=too_many).status_code == 400


def test_trip_page_renders_og_and_data(client):
    trip_id = client.post("/api/trip", json=ROUTE).json()["id"]
    html = client.get("/trip/" + trip_id).text
    assert "San Jose → San Francisco · 54 mi · CA Roads" in html
    assert 'property="og:image"' in html and "/api/staticmap" in html
    assert '"from_name": "San Jose"' in html
    assert client.get("/trip/nope").status_code == 404


def test_trip_page_escapes_names(client):
    evil = {**ROUTE, "from_name": '<script>x</script>'}
    trip_id = client.post("/api/trip", json=evil).json()["id"]
    html = client.get("/trip/" + trip_id).text
    assert "<script>x</script>" not in html.split("__TRIP_JSON__")[0]
    assert "&lt;script&gt;" in html
