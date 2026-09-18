"""The Flare side of plugins/waze-relay: the mapping, the store and the
endpoints, including a conformance run against the app itself.

Nothing here talks to Waze: the source's HTTP client is a mock transport
that fails any call, and the cache is filled by hand.
"""

from __future__ import annotations

import math
import time

import httpx
import mapping
import pytest
import server as relay
import store as store_module
from store import Store, Votes
from waze.cache import AlertQueryResult, WazeAlert
from waze.source import WazeSource

from ca_roads import flare

BBOX = relay.BBOX                  # the shipped default: the United States
SOCAL = [32.5, -119.5, 35.5, -115.5]
LA = (34.05, -118.25)
NOW = 1_700_000_000.0


def _no_network(_: httpx.Request) -> httpx.Response:
    raise AssertionError("a unit test must never call Waze")


def _alert(uuid="abc-123", *, waze_type="POLICE", subtype="POLICE_VISIBLE",
           lat=LA[0], lon=LA[1], magvar=270, pub_s=NOW - 300, thumbs=3,
           street="I-110 N", city="Los Angeles") -> WazeAlert:
    return WazeAlert(uuid, 42, waze_type, subtype, lon, lat, magvar,
                     int(pub_s * 1000), thumbs, street, city)


def _store(*alerts: WazeAlert, clock=None, wall=None, bbox=None) -> Store:
    clock = clock or (lambda: 1000.0)
    wall = wall or (lambda: NOW)
    client = httpx.AsyncClient(transport=httpx.MockTransport(_no_network))
    source = WazeSource(client, now=clock, wall_clock=wall)
    source.cache.submit(AlertQueryResult(list(alerts), []))
    source.last_ok = clock()
    return Store(source, bbox=bbox or BBOX, refresh_s=60, now=clock, wall_clock=wall)


# ---------------------------------------------------------------- mapping


def test_the_subtype_decides_and_the_type_is_the_fallback():
    assert mapping.flare_kind("POLICE", "POLICE_VISIBLE") == "POLICE_VISIBLE"
    assert mapping.flare_kind("POLICE", "POLICE_HIDING") == "POLICE_HIDING"
    # Covert enforcement reads as hidden, the way sabre-plus reads it.
    assert mapping.flare_kind("POLICE", "POLICE_WITH_MOBILE_CAMERA") == "POLICE_HIDING"
    assert mapping.flare_kind("POLICE", "") == "POLICE_VISIBLE"
    assert mapping.flare_kind("ACCIDENT", "ACCIDENT_MAJOR") == "CRASH_MAJOR"
    assert mapping.flare_kind("ACCIDENT", "ACCIDENT_MINOR") == "CRASH_MINOR"
    assert mapping.flare_kind("ACCIDENT", "") == "CRASH_MINOR"
    assert mapping.flare_kind("HAZARD", "HAZARD_ON_SHOULDER_CAR_STOPPED") == \
        "HAZARD_SHOULDER_CAR"
    assert mapping.flare_kind("HAZARD", "HAZARD_ON_ROAD_POT_HOLE") == "HAZARD_POTHOLE"
    assert mapping.flare_kind("HAZARD", "HAZARD_ON_ROAD_CONSTRUCTION") == \
        "HAZARD_CONSTRUCTION"
    assert mapping.flare_kind("HAZARD", "HAZARD_WEATHER_FOG") == "WEATHER_FOG"
    assert mapping.flare_kind("HAZARD", "HAZARD_ON_ROAD_ICE") == "WEATHER_ICE"
    assert mapping.flare_kind("HAZARD", "") == "HAZARD_ON_ROAD"
    assert mapping.flare_kind("JAM", "JAM_LIGHT_TRAFFIC") == "JAM_MODERATE"
    assert mapping.flare_kind("JAM", "JAM_HEAVY_TRAFFIC") == "JAM_HEAVY"
    assert mapping.flare_kind("JAM", "JAM_STAND_STILL_TRAFFIC") == "JAM_STANDSTILL"
    assert mapping.flare_kind("ROAD_CLOSED", "ROAD_CLOSED_EVENT") == "ROAD_CLOSED"
    assert mapping.flare_kind("NEW_LANE_CLOSED", "LANE_CLOSURE_LEFT_LANE") == "LANE_CLOSED"
    assert mapping.flare_kind("CAMERA", "DEFAULT_CAMERA") == "CAMERA_SPEED"
    assert mapping.flare_kind("SOS", "SOS_FLAT_TIRE") == "OTHER"
    assert mapping.flare_kind("SOMETHING_NEW", "SOMETHING_NEWER") == "OTHER"


def test_chatter_and_parking_are_not_road_conditions():
    assert mapping.flare_kind("CHIT_CHAT", "") is None
    assert mapping.flare_kind("PARKING", "") is None


def test_every_mapped_kind_is_in_the_flare_vocabulary():
    assert set(mapping.KINDS) <= flare.KINDS
    assert set(mapping.REPORTABLE_KINDS) <= flare.KINDS


def test_ttls_follow_the_plan():
    assert mapping.ttl_for("POLICE_VISIBLE") == 1200
    assert mapping.ttl_for("HAZARD_OBJECT") == 1200
    assert mapping.ttl_for("WEATHER_FOG") == 1200
    assert mapping.ttl_for("CRASH_MAJOR") == 2700
    assert mapping.ttl_for("ROAD_CLOSED") == 3600
    assert mapping.ttl_for("LANE_CLOSED") == 3600
    assert mapping.ttl_for("JAM_HEAVY") == 300
    assert mapping.ttl_for("OTHER") == 1200


def test_reliability_rises_with_the_confirmation_count():
    assert mapping.reliability(0) == 0.5
    assert mapping.reliability(3) == pytest.approx(0.8)
    assert mapping.reliability(50) == 1.0


def test_report_subtypes_cover_what_waze_takes_and_nothing_else():
    assert mapping.report_subtype("POLICE_HIDING") == (mapping.POLICE, 2)
    assert mapping.report_subtype("CRASH_MAJOR") == (mapping.CRASH, 3)
    assert mapping.report_subtype("JAM_STANDSTILL") == (mapping.TRAFFIC, 2)
    assert mapping.report_subtype("HAZARD_POTHOLE") == (mapping.HAZARD, 5)
    assert mapping.report_subtype("WEATHER_FOG") is None
    assert mapping.report_subtype("CAMERA_SPEED") is None


# ------------------------------------------------------------------ store


def test_a_record_is_a_valid_flare_alert():
    records = _store(_alert()).records()
    assert len(records) == 1
    record = records[0]
    assert flare.validate_alert(record, now=flare.parse_ts(record["report_ts"])) == []
    assert record["id"] == "wz:abc-123"
    assert record["kind"] == "POLICE_VISIBLE"
    assert record["heading_deg"] == 270
    assert record["road_names"] == ["I-110 N"]
    assert record["n_confirmations"] == 3
    assert record["reliability"] == pytest.approx(0.8)
    assert record["ttl_s"] == 1200
    assert record["extra"] == {"waze_type": "POLICE", "waze_subtype": "POLICE_VISIBLE",
                               "city": "Los Angeles"}


def test_an_id_is_the_same_across_polls_so_a_repeat_is_an_update():
    store = _store(_alert(thumbs=1))
    first = store.records()[0]
    store.source.cache.submit(AlertQueryResult([_alert(thumbs=6)], []))
    second = store.records()[0]
    assert first["id"] == second["id"] == "wz:abc-123"
    assert second["n_confirmations"] == 6
    assert second["reliability"] > first["reliability"]
    # A rising thumbs-up count is the only confirmation time the feed has.
    assert "confirm_ts" not in first
    assert "confirm_ts" in second


def test_a_zero_azimuth_is_left_out_rather_than_published_as_due_north():
    assert "heading_deg" not in _store(_alert(magvar=0)).records()[0]


def test_an_alert_past_its_ttl_is_not_served():
    fresh = _store(_alert(pub_s=NOW - 1199))
    assert fresh.records()
    stale = _store(_alert(pub_s=NOW - 1201))
    assert stale.records() == []
    # A crash gets longer before it goes stale.
    crash = _store(_alert(waze_type="ACCIDENT", subtype="ACCIDENT_MAJOR",
                          pub_s=NOW - 2000))
    assert crash.records()


def test_nothing_is_served_once_the_data_stops_being_refreshed():
    clock = [1000.0]
    store = _store(_alert(), clock=lambda: clock[0])
    assert store.fresh and store.records()
    clock[0] += 60 + 300 - 1          # the refresh window plus the grace
    assert store.fresh and store.records()
    clock[0] += 2
    assert not store.fresh
    assert store.records() == []
    assert store.near(*LA, 50_000) == []


def _voter(reporter, address="203.0.113.7", *, trusted=False):
    return Votes.voter(reporter, address, trusted=trusted)


def test_a_confirmation_raises_the_count_and_the_confidence():
    store = _store(_alert(thumbs=0))
    before = store.records()[0]
    store.votes.add("wz:abc-123", "up", _voter("r:someone", trusted=True))
    after = store.records()[0]
    assert after["n_confirmations"] == before["n_confirmations"] + 1
    assert after["reliability"] > before["reliability"]
    assert "confirm_ts" in after
    # The same voter twice is still one vote.
    store.votes.add("wz:abc-123", "up", _voter("r:someone", trusted=True))
    assert store.records()[0]["n_confirmations"] == after["n_confirmations"]


def test_enough_gone_votes_hide_the_alert():
    store = _store(_alert())
    for address in ("203.0.113.7", "198.51.100.4"):
        store.votes.add("wz:abc-123", "gone", _voter("whoever", address))
    assert store.records()
    store.votes.add("wz:abc-123", "gone", _voter("whoever", "192.0.2.9"))
    assert store.records() == []


def test_near_filters_by_distance_and_sorts_by_it():
    close = _alert("close", lat=LA[0], lon=LA[1])
    far = _alert("far", lat=LA[0] + 0.2, lon=LA[1])
    store = _store(far, close)
    ids = [r["id"] for r in store.near(*LA, 50_000)]
    assert ids == ["wz:close", "wz:far"]
    assert [r["id"] for r in store.near(*LA, 5_000)] == ["wz:close"]


def test_only_cells_asked_about_recently_are_kept_in_the_rotation():
    clock = [1000.0]
    store = _store(clock=lambda: clock[0])
    assert store.wanted_cells() == []
    store.want(*LA)
    assert store.wanted_cells() == [(34, -119)]
    clock[0] += 599
    assert store.wanted_cells() == [(34, -119)]
    clock[0] += 2
    assert store.wanted_cells() == []


def test_coverage_is_the_box_with_a_degree_of_slack():
    store = _store(bbox=SOCAL)
    assert store.in_coverage(*LA)
    assert store.in_coverage(36.4, -115.0)       # a degree outside is allowed
    assert not store.in_coverage(45.0, -122.0)


def test_the_shipped_coverage_answers_for_anywhere_in_the_country():
    store = _store()
    for place in (LA, (40.7, -74.0), (47.6, -122.3), (25.8, -80.2),
                  (61.2, -149.9), (21.3, -157.8)):
        assert store.in_coverage(*place), place
    assert not store.in_coverage(51.5, -0.12)    # London is not the United States


def test_the_busiest_cells_are_the_ones_kept_fresh():
    clock = [1000.0]
    store = _store(clock=lambda: clock[0])
    store.hot_limit = 2
    busy, quieter, quietest = (34.05, -118.25), (40.7, -74.0), (41.9, -87.6)
    for _ in range(5):
        store.want(*busy)
    for _ in range(3):
        store.want(*quieter)
    store.want(*quietest)
    assert store.wanted_cells() == [(34, -119), (40, -74), (41, -88)]
    assert store.hot_cells() == [(34, -119), (40, -74)]
    assert len(store.wanted_points()) == 2 * 4    # only the hot cells are swept


def test_the_hot_set_holds_still_while_a_sweep_runs():
    clock = [1000.0]
    store = _store(clock=lambda: clock[0])
    store.hot_limit = 1
    store.want(34.05, -118.25)
    assert store.hot_cells() == [(34, -119)]
    # A busier newcomer does not yank the sweep away mid-flight.
    for _ in range(9):
        store.want(40.7, -74.0)
    assert store.hot_cells() == [(34, -119)]
    clock[0] += 31                                 # ...but it wins on recheck
    assert store.hot_cells() == [(40, -74)]


def test_a_cell_that_stops_being_asked_about_leaves_the_hot_set():
    clock = [1000.0]
    store = _store(clock=lambda: clock[0])
    store.want(34.05, -118.25)
    assert store.hot_cells() == [(34, -119)]
    clock[0] += 601                                # past the ten-minute window
    assert store.wanted_cells() == []
    assert store.hot_cells() == []
    assert store.wanted_points() == []


def test_a_cell_is_swept_by_a_lattice_that_covers_its_corners():
    store = _store()
    store.want(*LA)
    assert len(store.wanted_points()) == 4        # a two by two lattice
    centers = [store_module.sub_cell_center(p[:2], p[2], p[3], 2)
               for p in store.wanted_points()]
    assert sorted(centers) == [(34.25, -118.75), (34.25, -118.25),
                               (34.75, -118.75), (34.75, -118.25)]
    # Downtown Los Angeles sits at the edge of its cell, so the cell center is
    # too far away to be the only place the plugin looks.
    assert store_module.meters(*LA, *store_module.cell_center((34, -119))) > 50_000
    nearest = min(store_module.meters(*LA, *c) for c in centers)
    assert nearest < 30_000
    # And the radius asked for still covers a lattice square once the client
    # shrinks its primary viewport.
    assert store_module.sub_cell_radius_m(34.5, 2) > math.hypot(0.25 * 110574,
                                                               0.25 * 91000)


async def test_the_poller_takes_the_stalest_point_and_waits_its_turn():
    clock = [1000.0]
    polled: list[tuple[float, float]] = []

    async def fake_refresh(lat, lon, radius_m):
        polled.append((round(lat, 2), round(lon, 2)))
        return 0

    store = _store(clock=lambda: clock[0])
    store.source.refresh = fake_refresh
    assert await store.poll_once() is False           # nothing asked for yet

    store.want(*LA)
    for _ in range(4):
        assert await store.poll_once() is True
        clock[0] += 1
    assert sorted(polled) == [(34.25, -118.75), (34.25, -118.25),
                              (34.75, -118.75), (34.75, -118.25)]
    # The whole cell is swept now, so the next tick waits out the window.
    assert await store.poll_once() is False
    clock[0] += 61
    assert await store.poll_once() is True


async def test_a_failed_cell_is_recorded_and_held_off_not_retried_at_once():
    clock = [1000.0]

    async def boom(lat, lon, radius_m):
        raise RuntimeError("waze said no")

    store = _store(clock=lambda: clock[0])
    store.source.refresh = boom
    store.want(*LA)
    await store.poll_once()
    assert store.source.last_error == "RuntimeError: waze said no"
    assert store.source.backoff_remaining_s() > 0
    assert await store.poll_once() is False           # holding off


# -------------------------------------------------------------- endpoints


def _client(store: Store) -> httpx.AsyncClient:
    relay.store = store
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=relay.app),
                             base_url="http://localhost")


async def test_the_handshake_is_valid_and_says_what_it_is():
    async with _client(_store()) as client:
        response = await client.get("/flare/v1/handshake")
    assert response.status_code == 200
    handshake = response.json()
    assert flare.validate_handshake(handshake) == []
    assert handshake["attribution"]["name"] == "Unofficial Waze relay (community)"
    assert handshake["attribution"]["url"] == "https://commutescout.com/plugins"
    # The marketplace card reads this, so it says what it is and what it is not.
    assert handshake["description"] == (
        "Crowd reports from Waze: police, crashes, hazards, jams. "
        "Unofficial, at your own risk.")
    # Coverage is the United States, Alaska and Hawaii included.
    south, west, north, east = handshake["coverage"]["bbox"]
    for lat, lon in ((34.05, -118.25), (40.7, -74.0), (61.2, -149.9), (21.3, -157.8)):
        assert south <= lat <= north and west <= lon <= east
    assert handshake["capabilities"] == {"alerts": True, "report": False,
                                         "confirm": True, "notify": False}
    assert flare.tier_of({"visibility": "public", "trust": "community"}) == "unreviewed"


async def test_alerts_answers_inside_the_box_and_refuses_outside_it():
    store = _store(_alert())
    async with _client(store) as client:
        inside = await client.get("/flare/v1/alerts",
                                  params={"lat": LA[0], "lon": LA[1], "r": 25_000})
        outside = await client.get("/flare/v1/alerts",
                                   params={"lat": 51.5, "lon": -0.12, "r": 25_000})
        missing = await client.get("/flare/v1/alerts")
    assert inside.status_code == 200
    body = inside.json()
    assert [a["id"] for a in body["alerts"]] == ["wz:abc-123"]
    assert body["ttl_s"] == 60 and flare.parse_ts(body["as_of"]) is not None
    assert store.wanted_cells() == [(34, -119)]       # the ask joined the rotation
    # A refusal must not put the caller's cell into the rotation.
    assert (51, -1) not in store.wanted_cells()
    assert outside.status_code == 422
    assert outside.json()["error"]["code"] == "outside_coverage"
    assert missing.status_code == 400


async def test_an_oversize_radius_is_clamped_not_refused():
    async with _client(_store(_alert())) as client:
        response = await client.get("/flare/v1/alerts",
                                    params={"lat": LA[0], "lon": LA[1], "r": 1_000_000})
    assert response.status_code == 200


async def test_confirm_takes_a_vote_and_404s_an_unknown_alert():
    store = _store(_alert(thumbs=0))
    async with _client(store) as client:
        unknown = await client.post("/flare/v1/confirm",
                                    json={"alert_id": "wz:nope", "vote": "up"})
        bad = await client.post("/flare/v1/confirm",
                                json={"alert_id": "wz:abc-123", "vote": "maybe"})
        good = await client.post("/flare/v1/confirm",
                                 json={"alert_id": "wz:abc-123", "vote": "up",
                                       "reporter": "r:someone"})
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "unknown_alert"
    assert bad.status_code == 400
    assert good.status_code == 200
    assert good.json()["n_confirmations"] == 1


async def test_reports_are_refused_while_the_capability_is_off():
    async with _client(_store()) as client:
        response = await client.post("/flare/v1/report",
                                     json={"kind": "POLICE_VISIBLE",
                                           "lat": LA[0], "lon": LA[1]})
    assert response.status_code == 404
    assert relay.PLUGIN["capabilities"]["report"] is False


async def test_status_reports_counts_and_no_secrets():
    async with _client(_store(_alert())) as client:
        body = (await client.get("/status")).json()
    assert body["alerts"] == 1 and body["served"] == 1
    assert body["registered"] is False
    assert "secret" not in str(body).lower()


async def test_the_conformance_check_passes_against_the_app():
    # The check asks at the middle of the coverage box, and judges staleness
    # against the real clock, so these records sit there and are minutes old.
    middle_lat, middle_lon = (BBOX[0] + BBOX[2]) / 2, (BBOX[1] + BBOX[3]) / 2
    now = time.time()
    here = {"lat": middle_lat, "lon": middle_lon}
    store = _store(
        _alert(pub_s=now - 120, **here),
        _alert("crash-1", waze_type="ACCIDENT", subtype="ACCIDENT_MAJOR",
               magvar=0, pub_s=now - 600, **here),
        _alert("jam-1", waze_type="JAM", subtype="JAM_HEAVY_TRAFFIC", pub_s=now - 100,
               thumbs=0, street=None, city=None, **here),
        wall=time.time)
    async with _client(store) as client:
        report = await flare.check_plugin("http://localhost", client=client)
    assert report.success, report.text()
    assert "alerts: 3 valid record(s)" in report.passed


def test_the_grid_matches_the_one_the_backend_polls_with():
    from ca_roads_demo import flare_sources

    assert store_module.CELL_DEG == flare_sources.CELL_DEG
    assert store_module.CELL_RADIUS_M == flare_sources.CELL_RADIUS_M


def test_a_record_survives_the_backend_marker_builder():
    from ca_roads_demo import flare_sources

    source = {"id": "wz-flare", "name": "Unofficial Waze relay (community)",
              "visibility": "public", "trust": "community",
              "attribution": {"name": "Unofficial Waze relay (community)",
                              "url": "https://commutescout.com/plugins"}}
    marker = flare_sources.alert_marker(source, _store(_alert()).records()[0])
    assert marker["kind"] == "plugin"
    assert marker["id"] == "wz-flare:wz:abc-123"
    assert marker["flare_kind"] == "POLICE_VISIBLE"
    assert marker["tier"] == "unreviewed"
    assert marker["source_url"] == "https://commutescout.com/plugins"
    # The backend splits a marker id on the first colon to route a vote back.
    sid, _, local = marker["id"].partition(":")
    assert (sid, local) == ("wz-flare", "wz:abc-123")


def test_as_of_is_when_the_data_was_last_refreshed():
    clock = [1000.0]
    store = _store(_alert(), clock=lambda: clock[0])
    assert flare.parse_ts(store.as_of).timestamp() == pytest.approx(NOW, abs=1)
    clock[0] += 45                       # forty-five seconds since the last poll
    assert flare.parse_ts(store.as_of).timestamp() == pytest.approx(NOW - 45, abs=1)
