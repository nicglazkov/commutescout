"""Report-type filters for watch areas: the taxonomy, which options a
drawn shape is offered, validation, the checker honoring a watch's
choice (and ignoring it on watches made before filters existed), route
stops, and weather alerts."""
# ruff: noqa: F811 - pytest fixtures shared from test_watch shadow their imports

import pytest
from tests.test_watch import (  # noqa: F401 - pytest fixtures
    CIRCLE,
    EVENT,
    approve,
    approved_client,
    auth,
    checker,
    client,
    seed_watch,
    store,
)

from ca_roads_demo import watch
from ca_roads_demo import watch_filters as wf


@pytest.fixture(autouse=True)
def _fresh_catalog(monkeypatch):
    wf.reset()
    monkeypatch.setattr(watch, "_catalog_io", {"loaded": True, "saved": 0.0})
    yield
    wf.reset()


# Bounds stand-ins for coverage_areas(): one covered state far from
# California, one overlapping its east edge.
AREAS = [
    {"state": "Maryland", "bounds": [37.9, -79.5, 39.8, -74.9]},
    {"state": "Iowa", "bounds": [40.3, -96.7, 43.6, -90.0]},
]


# ---------------------------------------------------------------- taxonomy

@pytest.mark.parametrize("raw,sub", [
    ("1182-Trfc Collision-No Inj", "crash"),
    ("1179-Trfc Collision-1141 Enrt", "crash"),
    ("1125-Traffic Hazard", "hazard"),
    ("CFIRE-Car Fire", "vehicle_fire"),
    ("CLOSURE of a Road", "closed"),
    ("ESCORT for Road Conditions", "police"),
    ("SNOW Information", "conditions"),
    ("CZP-Assist with Construction", "work"),
    ("TADV-Traffic Advisory", "advisory"),
    ("Disabled Vehicle", "stall"),
    ("SPINOUT", "crash"),
    ("20002-Hit and Run No Injuries", "crash"),
    ("SIG Alert", "closed"),
    ("1125A-Animal Hazard", "hazard"),
    ("Property Damage", "crash"),
    ("Police Activity", "police"),
    ("Something nobody expected", "other"),
])
def test_incident_types_classify(raw, sub):
    assert wf.classify("incident", raw) == sub


def test_every_chp_type_has_a_specific_report_type():
    for raw in wf.CHP_TYPES:
        assert wf.classify("incident", raw) != "other", raw


def test_closure_chain_and_weather_classify():
    assert wf.classify("closure", cls="full-roadway") == "full"
    assert wf.classify("closure", cls="alternating-lanes") == "lanes"
    assert wf.classify("closure", cls="traffic-break") == "moving"
    assert wf.classify("closure", cls="ramp") == "ramp"
    assert wf.classify("chain", status="R-2") == "r2"
    assert wf.classify("chain", status="MAX") == "trucks"
    assert wf.classify("chain", status="ROAD CLOSED") == "closed"
    assert wf.classify("chain", status=None) == "advisory"
    assert wf.classify("weather", "Winter Storm Warning") == "winter"
    assert wf.classify("weather", "Dust Storm Warning") == "wind"
    assert wf.classify("weather", "Red Flag Warning") == "fire_weather"
    assert wf.classify("fire") is None


def test_every_report_type_list_ends_in_a_catch_all():
    for kind, subs in wf.SUBTYPES.items():
        if kind in ("fire", "chain"):
            continue
        assert subs[-1][0] == "other", kind


# ---------------------------------------------------------------- area options

def _kind(opts, kid):
    return next(k for k in opts["kinds"] if k["id"] == kid)


def _sub_ids(opts, kid):
    return [s["id"] for s in _kind(opts, kid)["subtypes"]]


def test_california_circle_offers_chp_types_and_r_codes():
    shape = {"type": "circle", "center": {"lat": 37.3, "lon": -121.9},
             "radius_km": 20}
    states = wf.states_for_shape(shape, AREAS, watch.in_california,
                                 watch.point_in_polygon)
    assert states == ["California"]
    opts = wf.area_options(states)
    assert _sub_ids(opts, "chain") == ["r1", "r2", "r3", "trucks", "closed"]
    assert "moving" in _sub_ids(opts, "closure")
    crash = next(s for s in _kind(opts, "incident")["subtypes"]
                 if s["id"] == "crash")
    chp = crash["sources"][0]
    assert chp["id"] == "chp"
    labels = [t["label"] for t in chp["types"]]
    assert "1182-Trfc Collision-No Inj" in labels
    assert all(t["key"].startswith("chp|") for t in chp["types"])


def test_elsewhere_offers_its_own_learned_categories_not_chp():
    events = [
        {"id": f"st:{i}", "kind": "incident", "lat": 39.0, "lon": -76.8,
         "src_id": "mdot-chart", "src_label": "MDOT CHART",
         "raw_type": raw, "subtype": wf.classify("incident", raw)}
        for i, raw in enumerate(["Property Damage", "Property Damage",
                                 "Vehicle Fire", "Vehicle Fire",
                                 "One-off text seen once"])
    ]
    wf.observe(events, AREAS, watch.in_california)
    shape = {"type": "polygon", "points": [[39.2, -77.0], [39.2, -76.5],
                                           [38.8, -76.6]]}
    states = wf.states_for_shape(shape, AREAS, watch.in_california,
                                 watch.point_in_polygon)
    assert states == ["Maryland"]
    opts = wf.area_options(states)
    # No California sources, no R-codes, no CHP vocabulary.
    assert not _kind(opts, "chain")["available"]
    assert _sub_ids(opts, "chain") == []
    sources = [src for s in _kind(opts, "incident")["subtypes"]
               for src in s["sources"]]
    assert {s["id"] for s in sources} == {"mdot-chart"}
    labels = {t["label"] for s in sources for t in s["types"]}
    assert labels == {"Property Damage", "Vehicle Fire"}  # one-offs hidden
    # Weather and wildfires are nationwide.
    assert _kind(opts, "weather")["available"]
    assert _kind(opts, "fire")["available"]


def test_unlearned_state_gets_defaults_and_a_closure_only_state_stays_so():
    opts = wf.area_options(["Iowa"])
    assert _kind(opts, "incident")["available"]
    assert _sub_ids(opts, "closure") == ["full", "lanes"]
    wf.observe([{"id": "st:x", "kind": "closure", "lat": 42.0, "lon": -93.0,
                 "src_id": "iowa-dot", "src_label": "Iowa DOT",
                 "subtype": "lanes"}], AREAS, watch.in_california)
    opts = wf.area_options(["Iowa"])
    assert not _kind(opts, "incident")["available"]
    assert _sub_ids(opts, "closure") == ["lanes"]


def test_route_across_states_reaches_each():
    shape = {"type": "route", "points": [[38.6, -121.5], [39.3, -76.6]]}
    states = wf.states_for_shape(shape, AREAS, watch.in_california,
                                 watch.point_in_polygon)
    assert states == ["California", "Maryland"]


def test_catalog_survives_a_restart():
    wf.observe([{"id": f"e{i}", "kind": "incident", "lat": 39.0, "lon": -76.8,
                 "src_id": "mdot-chart", "src_label": "MDOT CHART",
                 "raw_type": "Debris", "subtype": "hazard"} for i in range(3)],
               AREAS, watch.in_california)
    assert wf.take_dirty()
    snap = wf.catalog_snapshot()
    assert not any(isinstance(v, list) and any(isinstance(x, list) for x in v)
                   for v in snap["mdot-chart"].values())
    wf.reset()
    wf.load_snapshot(snap)
    opts = wf.area_options(["Maryland"])
    hazard = next(s for s in _kind(opts, "incident")["subtypes"]
                  if s["id"] == "hazard")
    assert hazard["sources"][0]["types"][0]["key"] == "mdot-chart|Debris"


def test_options_endpoint(approved_client):
    r = approved_client.post("/api/watch/options", headers=auth(), json={
        "type": "circle", "center": {"lat": 39.3, "lon": -120.2},
        "radius_km": 20})
    assert r.status_code == 200
    assert "California" in r.json()["states"]
    assert approved_client.post("/api/watch/options", json={
        "type": "circle"}).status_code == 401
    assert approved_client.post("/api/watch/options", headers=auth(), json={
        "type": "blob"}).status_code == 400


# ---------------------------------------------------------------- validation

def test_create_stores_filters(approved_client, store):
    body = {**CIRCLE, "kinds": ["incident", "chain"],
            "filters": {"incident": {"subtypes": ["crash"],
                                     "raw": ["chp|1125-Traffic Hazard",
                                             "chp|1182-Trfc Collision-No Inj"]},
                        "chain": {"subtypes": ["r2", "r3"]}}}
    r = approved_client.post("/api/watch/create", json=body, headers=auth())
    assert r.status_code == 200, r.text
    saved = store.watches[r.json()["id"]]
    # The CHP collision type is already covered by "crash": dropped.
    assert saved["filters"]["incident"] == {
        "subtypes": ["crash"], "raw": ["chp|1125-Traffic Hazard"]}
    assert saved["filters"]["chain"] == {"subtypes": ["r2", "r3"], "raw": []}


@pytest.mark.parametrize("filters,needle", [
    ({"incident": {"subtypes": ["nope"]}}, "unknown report type"),
    ({"incident": {"subtypes": [], "raw": []}}, "at least one report type"),
    ({"incident": {"raw": ["no separator"]}}, "source|type"),
    ({"bogus": {}}, "unknown alert kind"),
    ({"fire": {"subtypes": ["x"]}}, "no report types"),
    ("everything", "must be an object"),
])
def test_bad_filters_refuse(approved_client, filters, needle):
    body = {**CIRCLE, "kinds": ["incident", "fire"], "filters": filters}
    r = approved_client.post("/api/watch/create", json=body, headers=auth())
    assert r.status_code == 400 and needle in r.json()["error"], r.text


def test_all_report_types_picked_means_no_filter(approved_client, store):
    every = [s for s, _ in wf.SUBTYPES["incident"]]
    body = {**CIRCLE, "filters": {"incident": {"subtypes": every},
                                  "closure": {"subtypes": ["full"]}}}
    r = approved_client.post("/api/watch/create", json=body, headers=auth())
    saved = store.watches[r.json()["id"]]
    # closure is not one of the watch's kinds: its filter is dropped too.
    assert "filters" not in saved


def test_legacy_create_body_has_no_filters(approved_client, store):
    r = approved_client.post("/api/watch/create", json=CIRCLE, headers=auth())
    assert "filters" not in store.watches[r.json()["id"]]


def test_update_filters_and_kinds(approved_client, store):
    wid = approved_client.post("/api/watch/create", json=CIRCLE,
                               headers=auth()).json()["id"]
    r = approved_client.patch(f"/api/watch/{wid}", headers=auth(), json={
        "filters": {"incident": {"subtypes": ["crash", "hazard"]}}})
    assert r.status_code == 200, r.text
    assert store.watches[wid]["filters"]["incident"]["subtypes"] == [
        "crash", "hazard"]
    # Kinds change alone: stored filters that still apply are kept.
    r = approved_client.patch(f"/api/watch/{wid}", headers=auth(),
                              json={"kinds": ["incident", "fire"]})
    assert store.watches[wid]["filters"]["incident"]["subtypes"] == [
        "crash", "hazard"]
    # Clearing filters goes back to everything.
    approved_client.patch(f"/api/watch/{wid}", headers=auth(),
                          json={"filters": {}})
    assert store.watches[wid]["filters"] == {}


# ---------------------------------------------------------------- checker

async def _seed(store, **extra):
    await approve(store)
    wid = await store.create_watch({
        "uid": "sam", "name": "Home", "type": "circle",
        "center": {"lat": 37.3, "lon": -121.9}, "radius_km": 20,
        "kinds": ["incident"], "channels": {"push": True}, "active": True,
        **extra})
    await store.upsert_push_sub("dev1", {
        "uid": "sam", "subscription": {"endpoint": "https://p/1"}})
    await store.set_seen(wid, {"chp:0"})
    return wid


CHP_CRASH = {**EVENT, "id": "chp:crash", "title": "1182-Trfc Collision-No Inj",
             "src_id": "chp", "raw_type": "1182-Trfc Collision-No Inj",
             "subtype": "crash"}
CHP_HAZARD = {**EVENT, "id": "chp:haz", "title": "1125-Traffic Hazard",
              "src_id": "chp", "raw_type": "1125-Traffic Hazard",
              "subtype": "hazard"}
CHP_ANIMAL = {**EVENT, "id": "chp:ani", "title": "ANIMAL-Live or Dead Animal",
              "src_id": "chp", "raw_type": "ANIMAL-Live or Dead Animal",
              "subtype": "hazard"}


def _titles(pushes):
    return sorted(p[1]["event"]["title"] for p in pushes)


async def test_kind_only_watch_gets_every_report_type(checker):
    store, events, pushes = checker
    await _seed(store)
    events.extend([CHP_CRASH, CHP_HAZARD, CHP_ANIMAL])
    await watch.run_check_cycle()
    assert len(pushes) == 3


async def test_legacy_watch_without_facets_on_events(checker):
    """A watch made before filters, and events with no facet fields
    (the shape every older test and source used), alert as before."""
    store, events, pushes = checker
    await seed_watch(store)
    wid = next(iter(store.watches))
    await store.set_seen(wid, {"chp:0"})
    events.append(EVENT)
    stats = await watch.run_check_cycle()
    assert stats["alerts"] == 1


async def test_report_type_watch_gets_only_that_type(checker):
    store, events, pushes = checker
    await _seed(store, filters={"incident": {"subtypes": ["crash"], "raw": []}})
    events.extend([CHP_CRASH, CHP_HAZARD, CHP_ANIMAL])
    await watch.run_check_cycle()
    assert _titles(pushes) == ["1182-Trfc Collision-No Inj"]


async def test_source_type_watch_gets_only_that_exact_type(checker):
    store, events, pushes = checker
    await _seed(store, filters={"incident": {
        "subtypes": [], "raw": ["chp|ANIMAL-Live or Dead Animal"]}})
    events.extend([CHP_CRASH, CHP_HAZARD, CHP_ANIMAL])
    await watch.run_check_cycle()
    assert _titles(pushes) == ["ANIMAL-Live or Dead Animal"]


async def test_filters_classify_events_without_facets(checker):
    store, events, pushes = checker
    await _seed(store, filters={"incident": {"subtypes": ["crash"], "raw": []}})
    events.extend([{**EVENT, "id": "a", "title": "Crash"},
                   {**EVENT, "id": "b", "title": "Debris in lane"}])
    await watch.run_check_cycle()
    assert _titles(pushes) == ["Crash"]


async def test_closure_and_chain_filters(checker):
    store, events, pushes = checker
    await _seed(store, kinds=["closure", "chain"], filters={
        "closure": {"subtypes": ["full"], "raw": []},
        "chain": {"subtypes": ["r3"], "raw": []}})
    events.extend([
        {**EVENT, "id": "lcs:1", "kind": "closure", "title": "full",
         "payload": {"class": "full-roadway"}},
        {**EVENT, "id": "lcs:2", "kind": "closure", "title": "lane",
         "payload": {"class": "lane"}},
        {**EVENT, "id": "chain:1:R-1", "kind": "chain", "title": "r1",
         "payload": {"status": "R-1"}},
        {**EVENT, "id": "chain:1:R-3", "kind": "chain", "title": "r3",
         "payload": {"status": "R-3"}},
    ])
    await watch.run_check_cycle()
    assert _titles(pushes) == ["full", "r3"]


async def test_weather_alerts_reach_weather_watches(checker, monkeypatch):
    store, events, pushes = checker
    await _seed(store, kinds=["weather"], filters={
        "weather": {"subtypes": ["winter"], "raw": ["nws|Dense Fog Advisory"]}})
    asked = []

    async def fake_alerts(client, points, with_ids=False):
        asked.append(points)
        assert with_ids
        return [
            {"id": "a1", "event": "Winter Storm Warning", "headline": "Snow",
             "point": (37.3, -121.9)},
            {"id": "a2", "event": "Wind Advisory", "headline": "Gusts",
             "point": (37.3, -121.9)},
            {"id": "a3", "event": "Dense Fog Advisory", "headline": "Fog",
             "point": (37.3, -121.9)},
        ]

    from ca_roads.feeds import nws
    monkeypatch.setattr(nws, "alerts_at_points", fake_alerts)
    monkeypatch.setattr(watch.tools, "get_road", lambda: type("R", (), {"client": None})())
    await watch.run_check_cycle()
    assert _titles(pushes) == ["Dense Fog Advisory", "Winter Storm Warning"]
    assert 1 <= len(asked[0]) <= watch.MAX_WEATHER_POINTS
    assert all(p[1]["url"].endswith("/watch") for p in pushes)
    # Same alerts next cycle: nothing new.
    await watch.run_check_cycle()
    assert len(pushes) == 2


async def test_no_weather_lookups_for_watches_without_weather(checker, monkeypatch):
    store, events, pushes = checker
    await _seed(store)

    async def boom(*a, **k):
        raise AssertionError("asked the Weather Service for nothing")

    from ca_roads.feeds import nws
    monkeypatch.setattr(nws, "alerts_at_points", boom)
    await watch.run_check_cycle()


def test_weather_points_are_bounded():
    route = {"type": "route", "points": [{"lat": 37 + i / 100, "lon": -121.9}
                                         for i in range(80)]}
    pts = watch._weather_points(route)
    assert len(pts) == watch.MAX_WEATHER_POINTS
    assert pts[0] == (37.0, -121.9) and pts[-1] == (37.79, -121.9)


# ---------------------------------------------------------------- route stops

ROUTE = [[37.34, -121.89], [37.5, -122.1], [37.77, -122.42]]


def _stops(n):
    return [{"lat": 37.3 + i * 0.05, "lon": -121.9 - i * 0.05,
             "label": f"Stop {i}"} for i in range(n)]


def test_route_with_stops_is_stored(approved_client, store):
    body = {"type": "route", "name": "Errands", "kinds": ["incident"],
            "points": ROUTE, "stops": _stops(5), "buffer_km": 3.2}
    r = approved_client.post("/api/watch/create", json=body, headers=auth())
    assert r.status_code == 200, r.text
    saved = store.watches[r.json()["id"]]
    assert [s["label"] for s in saved["stops"]] == [f"Stop {i}" for i in range(5)]


def test_stop_count_is_capped(approved_client):
    assert watch.MAX_ROUTE_STOPS == 8
    base = {"type": "route", "name": "R", "kinds": ["incident"],
            "points": ROUTE, "buffer_km": 3.2}
    ok = approved_client.post("/api/watch/create", headers=auth(),
                              json={**base, "stops": _stops(8)})
    assert ok.status_code == 200
    for n in (1, 9):
        r = approved_client.post("/api/watch/create", headers=auth(),
                                 json={**base, "stops": _stops(n)})
        assert r.status_code == 400 and "2 to 8 stops" in r.json()["error"]
    reno = approved_client.post("/api/watch/create", headers=auth(), json={
        **base, "stops": [*_stops(2), {"lat": 39.53, "lon": -119.81}]})
    assert reno.status_code == 400


def test_route_edit_adds_stops_and_reroutes(approved_client, store):
    body = {"type": "route", "name": "R", "kinds": ["incident"],
            "points": ROUTE[:2], "stops": _stops(2), "buffer_km": 3.2}
    wid = approved_client.post("/api/watch/create", json=body,
                               headers=auth()).json()["id"]
    before = store.watches[wid]["length_km"]
    r = approved_client.patch(f"/api/watch/{wid}", headers=auth(), json={
        "points": ROUTE, "stops": _stops(4)})
    assert r.status_code == 200, r.text
    assert len(store.watches[wid]["stops"]) == 4
    assert store.watches[wid]["length_km"] > before
    too_long = approved_client.patch(f"/api/watch/{wid}", headers=auth(), json={
        "points": [[33.0, -117.2], [41.9, -122.3]], "stops": _stops(2)})
    assert too_long.status_code == 400


def test_circle_points_still_refuse(approved_client):
    wid = approved_client.post("/api/watch/create", json=CIRCLE,
                               headers=auth()).json()["id"]
    r = approved_client.patch(f"/api/watch/{wid}", headers=auth(),
                              json={"points": ROUTE})
    assert r.status_code == 400


def test_config_lists_every_kind_and_the_stop_cap(client):
    cfg = client.get("/api/watch/config").json()
    assert [k["id"] for k in cfg["alertKinds"]] == list(wf.KIND_IDS)
    assert cfg["limits"]["route_stops"] == watch.MAX_ROUTE_STOPS
    inc = cfg["alertKinds"][0]
    assert inc["subtypes"][0] == {"id": "crash", "label": "Crashes"}


# ---------------------------------------------------------------- collectors

async def test_collected_events_carry_report_type_facets(monkeypatch):
    from types import SimpleNamespace as NS

    chp = NS(id="X1", lat=37.3, lon=-121.9, log_type="1182-Trfc Collision-No Inj",
             reported_at=None, location="US101 N", area="San Jose",
             details=[], units=[], location_desc=None)
    chain = NS(index=4, status="R-2", lat=39.3, lon=-120.3, route="I-80",
               status_description="Chains required", location_name="Kingvale")

    class Road:
        client = None

        async def incidents(self):
            return NS(records=[chp])

        async def lane_closures(self):
            return NS(records=[])

        async def chain_controls(self):
            return NS(records=[chain])

        async def wildfires(self):
            return NS(records=[])

    async def expansion(client):
        return []

    monkeypatch.setattr(watch.tools, "get_road", lambda: Road())
    monkeypatch.setattr(watch.lanecount, "chp_layout", lambda i: None)
    monkeypatch.setattr(watch, "_collect_expansion_events", expansion)
    events = await watch._collect_events()
    inc = next(e for e in events if e["kind"] == "incident")
    assert (inc["src_id"], inc["raw_type"], inc["subtype"]) == (
        "chp", "1182-Trfc Collision-No Inj", "crash")
    ch = next(e for e in events if e["kind"] == "chain")
    assert ch["subtype"] == "r2"


async def test_expansion_events_carry_source_and_type(monkeypatch):
    from ca_roads_demo import states as expansion

    async def fake_markers(client, box, want):
        return [{"kind": "incident", "lat": 39.0, "lon": -76.8,
                 "type": "Disabled Vehicle", "label": "I-95 N",
                 "src": "MDOT CHART"},
                {"kind": "lane_closure", "lat": 39.0, "lon": -76.7,
                 "cls": "full-roadway", "label": "MD-295", "src": "MDOT CHART"}]

    monkeypatch.setattr(expansion, "markers_for_bbox", fake_markers)
    events = await watch._collect_expansion_events(None)
    inc, clo = events
    assert (inc["src_id"], inc["raw_type"], inc["subtype"]) == (
        "mdot-chart", "Disabled Vehicle", "stall")
    assert clo["subtype"] == "full" and clo["raw_type"] is None
