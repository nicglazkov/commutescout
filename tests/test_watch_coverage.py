# ruff: noqa: F811 - fixtures imported from test_watch are used by name
"""Watches anywhere CommuteScout has road data, not only California.

The checker has collected every state's events for months; only the
geometry guards, the client's copy of the California outline, and the
page copy were California-only. Coverage now comes from the state
registry, so a state added there becomes watchable with no other change.
"""

import re
from pathlib import Path

import pytest

from ca_roads_demo import states, watch
from test_watch import (  # noqa: F401 - fixtures reused by name
    CIRCLE,
    approve,
    approved_client,
    auth,
    client,
    store,
)

KEYED_ENV = {
    "NV511_API_KEY": "x", "AK511_API_KEY": "x", "COTRIP_API_KEY": "x",
    "WSDOT_API_KEY": "x", "AZ511_API_KEY": "x", "UT511_API_KEY": "x",
    "ID511_API_KEY": "x", "CT511_API_KEY": "x", "NC511_API_KEY": "x",
    "TRIPCHECK_API_KEY": "x", "OHGO_API_KEY": "x",
    "SMARTERROADS_USER": "x", "SMARTERROADS_PASS": "x",
}


@pytest.fixture(autouse=True)
def keyed(monkeypatch):
    """Production mounts every feed key; tests do not. Coverage counts a
    keyed state only while its key is present, so mount them all."""
    for k, v in KEYED_ENV.items():
        monkeypatch.setenv(k, v)


# ---------------------------------------------------------------- coverage

def test_coverage_lists_every_registered_state():
    areas = states.coverage_areas()
    names = {a["state"] for a in areas}
    for expected in ("Nevada", "Colorado", "Alaska", "Hawaii", "Maryland",
                     "Iowa", "New York", "Maine", "Florida", "Washington"):
        assert expected in names, expected
    assert "Nationwide" not in names  # the wildfire feed is not a state
    assert "California" not in names  # California is the outline, not a box
    # 36 registry states plus California is the 37 the site advertises.
    assert len(areas) + 1 == 37
    for a in areas:
        lat_min, lon_min, lat_max, lon_max = a["bounds"]
        assert -90 <= lat_min < lat_max <= 90 and -180 <= lon_min < lon_max <= 180


def test_coverage_omits_keyed_states_without_a_key(monkeypatch):
    for k in KEYED_ENV:
        monkeypatch.delenv(k, raising=False)
    names = {a["state"] for a in states.coverage_areas()}
    assert "Nevada" not in names and "Maryland" in names


@pytest.mark.parametrize("lat,lon,expected,label", [
    (36.0, -123.0, True, "offshore California"),
    (37.3, -121.9, True, "San Jose"),
    (39.53, -119.81, True, "Reno NV"),
    (39.74, -104.99, True, "Denver CO"),
    (61.22, -149.90, True, "Anchorage AK"),
    (21.31, -157.86, True, "Honolulu HI"),
    (40.71, -74.01, True, "New York City"),
    (42.36, -71.06, False, "Boston MA (no feed)"),
    (41.14, -104.82, False, "Cheyenne WY (no feed)"),
    (35.08, -106.65, False, "Albuquerque NM (no feed)"),
    (31.87, -116.60, False, "Ensenada MX"),
])
def test_in_coverage_points(lat, lon, expected, label):
    assert watch.in_coverage(lat, lon) is expected, label


def test_every_registered_state_center_is_covered():
    for a in states.coverage_areas():
        lat_min, lon_min, lat_max, lon_max = a["bounds"]
        assert watch.in_coverage((lat_min + lat_max) / 2,
                                 (lon_min + lon_max) / 2), a["state"]


# ---------------------------------------------------------------- API

def _post(client_, body, path="/api/watch/create"):
    return client_.post(path, json=body, headers=auth())


def test_nevada_circle_polygon_and_route_are_created(approved_client):
    circle = {"type": "circle", "name": "Reno", "kinds": ["incident"],
              "center": {"lat": 39.53, "lon": -119.81}, "radius_km": 20}
    assert _post(approved_client, circle).status_code == 200
    poly = {"type": "polygon", "name": "Truckee Meadows", "kinds": ["closure"],
            "points": [[39.4, -120.0], [39.7, -120.0], [39.7, -119.6]]}
    assert _post(approved_client, poly).status_code == 200
    route = {"type": "route", "name": "Reno to Carson", "kinds": ["chain"],
             "points": [[39.53, -119.81], [39.16, -119.77]]}
    assert _post(approved_client, route).status_code == 200


def test_polygon_with_a_corner_in_an_uncovered_state_is_refused(approved_client):
    poly = {"type": "polygon", "name": "Bad", "kinds": ["closure"],
            "points": [[41.0, -105.5], [41.5, -105.5], [41.14, -104.82]]}
    r = _post(approved_client, poly)
    assert r.status_code == 400
    assert "CommuteScout covers" in r.json()["error"]


def test_route_may_cross_into_a_covered_state_but_not_an_uncovered_one(approved_client):
    ok = {"type": "route", "name": "Tahoe to Reno", "kinds": ["chain"],
          "points": [[38.9, -120.0], [39.3, -119.9], [39.53, -119.81]]}
    assert _post(approved_client, ok).status_code == 200
    bad = {"type": "route", "name": "Salt Lake to Cheyenne", "kinds": ["closure"],
           "points": [[40.76, -111.89], [41.14, -104.82]]}
    r = _post(approved_client, bad)
    assert r.status_code == 400 and "CommuteScout covers" in r.json()["error"]


def test_update_obeys_coverage(approved_client, store):
    poly = {"type": "polygon", "name": "Reno", "kinds": ["closure"],
            "points": [[39.4, -120.0], [39.7, -120.0], [39.7, -119.6]]}
    wid = _post(approved_client, poly).json()["id"]
    r = approved_client.patch(f"/api/watch/{wid}", json={
        "points": [[41.0, -105.5], [41.5, -105.5], [41.14, -104.82]]},
        headers=auth())
    assert r.status_code == 400 and "CommuteScout covers" in r.json()["error"]
    assert store.watches[wid]["points"][0] == {"lat": 39.4, "lon": -120.0}
    ok = approved_client.patch(f"/api/watch/{wid}", json={
        "points": [[39.5, -120.0], [39.8, -120.0], [39.8, -119.6]]},
        headers=auth())
    assert ok.status_code == 200
    assert store.watches[wid]["points"][0] == {"lat": 39.5, "lon": -120.0}


def test_circle_in_an_uncovered_state_is_refused(approved_client):
    body = {"type": "circle", "name": "Boston", "kinds": ["incident"],
            "center": {"lat": 42.36, "lon": -71.06}, "radius_km": 10}
    r = _post(approved_client, body)
    assert r.status_code == 400 and "CommuteScout covers" in r.json()["error"]


def test_free_limits_apply_everywhere(approved_client):
    body = {"type": "circle", "name": "big", "kinds": ["incident"],
            "center": {"lat": 39.53, "lon": -119.81}, "radius_km": 41.0}
    r = _post(approved_client, body)
    assert r.status_code == 400 and "free limit" in r.json()["error"]


def test_config_carries_the_coverage(client):
    cov = client.get("/api/watch/config").json()["coverage"]
    assert cov["california"][0] == [42.0, -125.5]
    assert any(a["state"] == "Nevada" for a in cov["states"])
    assert all(len(a["bounds"]) == 4 for a in cov["states"])


# ---------------------------------------------------------------- checker

async def test_nevada_watch_alerts_on_a_nevada_event_only_once(store, monkeypatch):
    await approve(store)
    wid = await store.create_watch({
        "uid": "sam", "name": "Reno", "type": "circle", "active": True,
        "center": {"lat": 39.53, "lon": -119.81}, "radius_km": 20,
        "kinds": ["closure", "incident"], "channels": {"push": True}})
    await store.upsert_push_sub("sub1", {"uid": "sam", "endpoint": "x"})

    markers = [
        {"kind": "lane_closure", "lat": 39.55, "lon": -119.80,
         "cls": "full-roadway", "label": "I-80 EB closed", "route": "I-80",
         "src": "NDOT"},
        {"kind": "incident", "lat": 37.48, "lon": -122.14,
         "label": "collision", "src": "CHP mirror"},
    ]

    async def fake_markers(client_, box, want, **_kw):
        return list(markers)

    monkeypatch.setattr(states, "markers_for_bbox", fake_markers)

    class QuietRoad:
        client = None

        async def _empty(self, *_a, **_k):
            from ca_roads.models import FeedResult
            return FeedResult(source="x", records=[], data_as_of=None)

        incidents = lane_closures = chain_controls = wildfires = _empty

    monkeypatch.setattr(watch.tools, "get_road", lambda: QuietRoad())
    pushed = []

    async def fake_push(subs, payload):
        pushed.append(payload)
        return 1

    monkeypatch.setattr(watch, "_push_to_subs", fake_push)

    async def no_archive(_events):
        return {}

    from ca_roads_demo import archive, tollprices
    monkeypatch.setattr(archive, "observe", no_archive)

    async def no_tolls():
        return None

    monkeypatch.setattr(tollprices, "observe", no_tolls)

    first = await watch.run_check_cycle()   # seeds the seen-set silently
    assert first["alerts"] == 0
    markers.append({"kind": "lane_closure", "lat": 39.50, "lon": -119.85,
                    "cls": "lane", "label": "US-395 lane closed",
                    "route": "US-395", "src": "NDOT"})
    second = await watch.run_check_cycle()
    assert second["alerts"] == 1 and len(pushed) == 1
    assert "US-395" in pushed[0]["title"] or "US-395" in pushed[0]["body"]
    third = await watch.run_check_cycle()
    assert third["alerts"] == 0   # already seen
    assert wid in store.seen


# ---------------------------------------------------------------- the page

def test_watch_page_has_one_coverage_source():
    html = Path("src/ca_roads_demo/static/watch.html").read_text(encoding="utf-8")
    assert "insideCA" not in html and "CA_BOUNDARY" not in html
    assert "insideCoverage" in html and "CFG.coverage" in html
    assert "Draw an area of California" not in html
    assert re.search(r"anywhere CommuteScout covers", html)
