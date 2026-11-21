"""The watch detail pane's "inside now" list and the editor's live preview."""

import pytest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient
from tests.test_watch import USERS, MemoryStore  # noqa: F401 - shared fixtures

from ca_roads_demo import watch

EVENTS = [
    # Along I-80 from Sacramento toward Reno.
    {"id": "a", "kind": "incident", "lat": 38.75, "lon": -121.28, "title": "Traffic hazard",
     "body": "I-80 W at Atlantic St", "meta": "CHP", "subtype": "hazard", "src_id": "chp"},
    {"id": "b", "kind": "closure", "lat": 39.214, "lon": -120.40, "title": "Road closed",
     "body": "Donner Pass Rd", "meta": "Caltrans", "subtype": "full", "src_id": "lcs"},
    {"id": "c", "kind": "fire", "lat": 38.60, "lon": -121.45, "title": "Wildfire: Test",
     "body": "", "meta": "", "subtype": None, "src_id": "calfire"},
    # Far away: never inside.
    {"id": "z", "kind": "incident", "lat": 47.60, "lon": -122.33, "title": "Crash",
     "body": "Seattle", "meta": "", "subtype": "crash", "src_id": "wsdot"},
]

ROUTE = [{"lat": 38.58, "lon": -121.49}, {"lat": 38.75, "lon": -121.28},
         {"lat": 39.33, "lon": -120.18}, {"lat": 39.53, "lon": -119.81}]


@pytest.fixture
def mem(monkeypatch):
    m = MemoryStore()
    monkeypatch.setattr(watch, "get_store", lambda: m)

    async def fake_verify(request):
        header = request.headers.get("authorization") or ""
        return USERS.get(header.removeprefix("Bearer ").strip())

    async def fake_events():
        return [dict(e) for e in EVENTS]

    async def no_weather(w):
        return []

    monkeypatch.setattr(watch, "verify_user", fake_verify)
    monkeypatch.setattr(watch, "_collect_events", fake_events)
    monkeypatch.setattr(watch, "_weather_events", no_weather)
    return m


@pytest.fixture
def client(mem):
    return TestClient(Starlette(routes=[
        Route("/api/watch/preview", watch.api_watch_preview, methods=["POST"]),
        Route("/api/watch/{watch_id}/inside", watch.api_watch_inside),
    ]))


def auth(tok="tok-sam"):
    return {"Authorization": f"Bearer {tok}"}


def test_route_mile_counts_from_the_start():
    assert watch.route_mile_km(ROUTE, 38.58, -121.49) == pytest.approx(0, abs=0.01)
    mid = watch.route_mile_km(ROUTE, 38.75, -121.28)
    end = watch.route_mile_km(ROUTE, 39.53, -119.81)
    assert 0 < mid < end
    assert watch.route_mile_km(ROUTE[:1], 38.0, -121.0) == 0.0


def test_inside_lists_route_items_in_order(client, mem):
    mem.watches["w1"] = {"uid": "sam", "type": "route", "points": ROUTE, "buffer_km": 3.0,
                         "kinds": ["incident", "closure"], "filters": {}}
    r = client.get("/api/watch/w1/inside", headers=auth())
    assert r.status_code == 200
    body = r.json()
    assert [i["id"] for i in body["items"]] == ["a", "b"]
    assert body["count"] == 2 and body["by_kind"] == {"incident": 1, "closure": 1}
    assert body["items"][0]["at_km"] < body["items"][1]["at_km"]
    assert "checked_at" in body


def test_inside_is_owner_only(client, mem):
    mem.watches["w1"] = {"uid": "someone-else", "type": "circle",
                         "center": {"lat": 38.6, "lon": -121.4}, "radius_km": 30,
                         "kinds": ["incident"]}
    assert client.get("/api/watch/w1/inside", headers=auth()).status_code == 404
    assert client.get("/api/watch/w1/inside").status_code == 401
    assert client.get("/api/watch/nope/inside", headers=auth()).status_code == 404


def test_circle_items_sort_most_serious_first(client, mem):
    mem.watches["w2"] = {"uid": "sam", "type": "circle",
                         "center": {"lat": 38.65, "lon": -121.35}, "radius_km": 40,
                         "kinds": ["incident", "fire"]}
    items = client.get("/api/watch/w2/inside", headers=auth()).json()["items"]
    assert [i["kind"] for i in items] == ["fire", "incident"]
    assert all("at_km" not in i for i in items)


def test_preview_honors_kinds_and_filters(client, mem):
    mem.users["sam"] = {"status": "approved"}
    body = {"type": "route", "points": ROUTE, "buffer_km": 3,
            "kinds": ["incident", "closure"]}
    r = client.post("/api/watch/preview", headers=auth(), json=body)
    assert r.status_code == 200 and r.json()["count"] == 2
    r = client.post("/api/watch/preview", headers=auth(), json={**body, "kinds": ["closure"]})
    assert [i["id"] for i in r.json()["items"]] == ["b"]


def test_preview_needs_approval_and_a_valid_body(client, mem):
    assert client.post("/api/watch/preview", json={}).status_code == 401
    mem.users["sam"] = {"status": "pending"}
    assert client.post("/api/watch/preview", headers=auth(), json={
        "type": "circle", "center": {"lat": 1, "lon": 2}, "radius_km": 5,
        "kinds": ["incident"]}).status_code == 403
    mem.users["sam"] = {"status": "approved"}
    assert client.post("/api/watch/preview", headers=auth(), json={
        "type": "circle", "kinds": []}).status_code == 400
    assert client.post("/api/watch/preview", headers=auth(), json={
        "type": "blob", "kinds": ["incident"]}).status_code == 400
