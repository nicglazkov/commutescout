"""The MCP server treats every covered state alike: local time is the
place's own zone, ambiguous names are asked about (or picked with a
note) instead of silently landing in one state, sources are never
borrowed from California, and the California-only tools say so and point
elsewhere. Every upstream is faked; nothing here touches the network."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from ca_roads.feeds import nws as nws_feed
from ca_roads.feeds import tomtom as tomtom_feed
from ca_roads_mcp import history as hist
from ca_roads_mcp import planning, server, snapshots

# ── Time zones ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("lat", "lon", "zone"), [
    (40.71, -74.01, "America/New_York"),        # New York
    (25.76, -80.19, "America/New_York"),        # Miami
    (30.44, -84.28, "America/New_York"),        # Tallahassee
    (30.42, -87.22, "America/Chicago"),         # Pensacola
    (30.16, -85.66, "America/Chicago"),         # Panama City, FL
    (41.88, -87.63, "America/Chicago"),         # Chicago
    (36.16, -86.78, "America/Chicago"),         # Nashville
    (39.74, -104.99, "America/Denver"),         # Denver
    (31.76, -106.49, "America/Denver"),         # El Paso
    (33.45, -112.07, "America/Phoenix"),        # Phoenix (no DST)
    (43.62, -116.20, "America/Boise"),          # Boise (Mountain)
    (47.68, -116.78, "America/Los_Angeles"),    # Coeur d'Alene (Pacific)
    (47.61, -122.33, "America/Los_Angeles"),    # Seattle
    (61.22, -149.90, "America/Anchorage"),      # Anchorage
    (64.50, -165.41, "America/Anchorage"),      # Nome: west of Hawaii's lon
    (60.79, -161.76, "America/Anchorage"),      # Bethel
    (51.88, -176.66, "America/Adak"),           # Adak (Hawaii-Aleutian)
    (21.31, -157.86, "Pacific/Honolulu"),       # Honolulu
    (19.72, -155.08, "Pacific/Honolulu"),       # Hilo
    (18.47, -66.11, "America/Puerto_Rico"),     # San Juan
])
def test_zone_guess_is_each_places_own(lat, lon, zone):
    assert planning.guess_zone(lat, lon) == zone


PLACES = {
    "America/New_York": ((40.7128, -74.0060), (42.3601, -71.0589)),
    "America/Chicago": ((41.8781, -87.6298), (43.0389, -87.9065)),
    "America/Denver": ((39.7392, -104.9903), (40.0150, -105.2705)),
    "America/Phoenix": ((33.4484, -112.0740), (32.2226, -110.9747)),
    "America/Anchorage": ((61.2181, -149.9003), (61.5814, -149.4394)),
    "Pacific/Honolulu": ((21.3069, -157.8583), (21.4022, -157.7394)),
    "America/Los_Angeles": ((38.5816, -121.4944), (38.5449, -121.7405)),
}


def _fake_trip(monkeypatch, origin, destination, zones, minutes=60,
               forecast_word="Sunny"):
    """Two trip ends, each with its own NWS zone, and a straight route."""
    async def resolve(client, place, coords, near, which):
        lat, lon = origin if which == "origin" else destination
        return {"lat": lat, "lon": lon, "name": which}

    async def point_info(client, lat, lon):
        return {"time_zone": zones[0] if (lat, lon) == origin else zones[1]}

    async def forecast(client, lat, lon, hours=48):
        tz = ZoneInfo(zones[0] if (lat, lon) == origin else zones[1])
        start = datetime.now(UTC).astimezone(tz).replace(
            minute=0, second=0, microsecond=0)
        return [{"start": (start + timedelta(hours=h)).isoformat(),
                 "temp_f": 50, "precip_pct": 0, "wind_mph": 5,
                 "forecast": forecast_word, "daytime": True}
                for h in range(160)]

    async def alerts(client, points):
        return []

    line = [(origin[0] + (destination[0] - origin[0]) * i / 50,
             origin[1] + (destination[1] - origin[1]) * i / 50)
            for i in range(51)]

    async def markers(client, box, kinds):
        return [], []

    async def stadia(client, ms, a, b, preference):
        return None

    async def route_times(client, a, b, depart_at=None, *, with_points=False):
        return {"travel_s": minutes * 60, "historic_s": minutes * 60,
                "no_traffic_s": minutes * 60, "length_m": 60_000,
                "points": line}

    async def history(points, meters, days, tz):
        return hist.unavailable("not in tests")

    monkeypatch.setattr(planning, "resolve", resolve)
    monkeypatch.setattr(nws_feed, "point_info", point_info)
    monkeypatch.setattr(nws_feed, "hourly_forecast", forecast)
    monkeypatch.setattr(nws_feed, "alerts_at_points", alerts)
    monkeypatch.setattr(planning, "live_markers", markers)
    monkeypatch.setattr(planning, "_stadia_plan", stadia)
    monkeypatch.setattr(tomtom_feed, "route_times", route_times)
    monkeypatch.setattr(tomtom_feed, "api_key", lambda: "k")
    monkeypatch.setattr(hist, "history", history)
    planning._plan_cache.clear()


def _offset(zone: str, when: datetime) -> str:
    return when.replace(tzinfo=ZoneInfo(zone)).isoformat(timespec="minutes")[-6:]


@pytest.mark.parametrize("zone", sorted(PLACES))
async def test_plan_trip_speaks_the_origins_own_local_time(monkeypatch, zone):
    a, b = PLACES[zone]
    _fake_trip(monkeypatch, a, b, (zone, zone))
    # July: Phoenix and Honolulu keep standard time, everyone else is on
    # daylight time; a Pacific assumption shows up as -07:00 everywhere.
    out = await planning.plan_trip(None, "a", "b", depart_at="2027-07-01T08:00")
    expected = _offset(zone, datetime(2027, 7, 1, 8, 0))
    assert out["departure_local"] == "2027-07-01T08:00" + expected
    assert out["arrival_local"] == "2027-07-01T09:00" + expected
    assert "leaving Thursday Jul 1 at 8:00 AM, arriving around 9:00 AM;" \
        in out["summary"]


async def test_cross_zone_trip_labels_the_arrival_zone(monkeypatch):
    chicago, indianapolis = (41.8781, -87.6298), (39.7684, -86.1581)
    _fake_trip(monkeypatch, chicago, indianapolis,
               ("America/Chicago", "America/Indiana/Indianapolis"),
               minutes=180)
    out = await planning.plan_trip(None, "a", "b", depart_at="2027-01-15T08:00")
    assert out["departure_local"] == "2027-01-15T08:00-06:00"
    assert out["arrival_local"] == "2027-01-15T12:00-05:00"
    assert "arriving around 12:00 PM EST (destination time)" in out["summary"]


@pytest.mark.parametrize("zone", ["America/New_York", "America/Phoenix",
                                  "Pacific/Honolulu", "America/Anchorage"])
async def test_best_time_sweeps_in_the_origins_zone(monkeypatch, zone):
    a, b = PLACES[zone]
    _fake_trip(monkeypatch, a, b, (zone, zone))
    out = await planning.best_time_to_go(None, "a", "b", day="tomorrow",
                                         earliest="6am", latest="9am")
    assert out["time_zone"] == zone and out["arrival_time_zone"] == zone
    first = datetime.fromisoformat(out["departures"][0]["leave_local"])
    assert first.hour == 6 and first.tzinfo.utcoffset(first) == \
        first.astimezone(ZoneInfo(zone)).utcoffset()
    assert out["departures"][0]["leave"] == "6:00 AM"
    assert "destination time" not in out["summary"]


async def test_hurricane_forecast_is_a_severe_departure(monkeypatch):
    a, b = PLACES["America/New_York"]
    _fake_trip(monkeypatch, a, b, ("America/New_York",) * 2,
               forecast_word="Hurricane Conditions")
    out = await planning.best_time_to_go(None, "a", "b", day="tomorrow",
                                         earliest="6am", latest="9am")
    assert "A hurricane is in the forecast" in out["summary"]
    assert "Snow or ice" not in out["summary"]


@pytest.mark.parametrize("event", [
    "Hurricane Warning", "Tornado Warning", "Tropical Storm Watch",
    "Extreme Cold Warning", "Tsunami Warning", "Ashfall Advisory",
    "Winter Storm Warning", "Dense Fog Advisory", "Excessive Heat Warning"])
def test_every_regions_driving_alerts_count(event):
    assert nws_feed._road_relevant(event)


def test_non_driving_alerts_stay_out():
    assert not nws_feed._road_relevant("Beach Hazards Statement")
    assert not nws_feed._road_relevant("Air Quality Alert")
    assert nws_feed.driving_hazard({"forecast": "Tropical Storm Conditions"}) \
        == "tropical storm"


# ── Ambiguous names ──────────────────────────────────────────────────────────

SPRINGFIELDS = [
    {"name": "Springfield, MA", "lat": 42.1015, "lon": -72.5898},
    {"name": "Springfield, IL", "lat": 39.7817, "lon": -89.6501},
    {"name": "Springfield, MO", "lat": 37.2090, "lon": -93.2923},
]
PORTLANDS = [
    {"name": "Portland, OR", "lat": 45.5152, "lon": -122.6784},
    {"name": "Portland, ME", "lat": 43.6591, "lon": -70.2568},
]


def _fake_places(monkeypatch, rows):
    def nearest(lat, lon):
        if lat is None:
            return list(rows)
        return sorted(rows, key=lambda r: (r["lat"] - lat) ** 2
                      + (r["lon"] - lon) ** 2)

    async def suggest(client, q, lat, lon, limit=6, scope="us"):
        return nearest(lat, lon)

    async def search(client, q, limit=5, near=None, scope="us"):
        return []

    monkeypatch.setattr(planning, "stadia_suggest", suggest)
    monkeypatch.setattr(planning, "geocode_candidates", search)


@pytest.mark.parametrize("rows", [SPRINGFIELDS, PORTLANDS])
async def test_a_shared_name_with_no_context_is_asked(monkeypatch, rows):
    _fake_places(monkeypatch, rows)
    out = await planning.resolve(None, rows[0]["name"].split(",")[0], None,
                                 None, "place")
    assert out["needs_clarification"] is True
    assert len(out["options"]) == len(rows)


@pytest.mark.parametrize(("rows", "origin"), [
    (SPRINGFIELDS, (39.0997, -94.5786)),   # Kansas City: MO and IL both near
    (PORTLANDS, (39.7392, -104.9903)),     # Denver: both Portlands far
])
async def test_a_shared_name_the_origin_does_not_settle_is_asked(
        monkeypatch, rows, origin):
    _fake_places(monkeypatch, rows)
    out = await planning.resolve(None, rows[0]["name"].split(",")[0], None,
                                 origin, "destination")
    assert out.get("needs_clarification") is True, out


@pytest.mark.parametrize(("rows", "origin", "picked"), [
    (SPRINGFIELDS, (42.3601, -71.0589), "Springfield, MA"),   # from Boston
    (PORTLANDS, (47.6062, -122.3321), "Portland, OR"),        # from Seattle
    (PORTLANDS, (42.3601, -71.0589), "Portland, ME"),         # from Boston
])
async def test_the_obvious_namesake_is_picked_with_a_note(
        monkeypatch, rows, origin, picked):
    _fake_places(monkeypatch, rows)
    out = await planning.resolve(None, picked.split(",")[0], None, origin,
                                 "destination")
    assert out["name"].startswith(picked)
    assert out["other_matches"]
    note = planning.match_notes(("destination", out))[0]
    assert note.startswith(f"destination taken as {picked}")
    assert "other places share the name" in note


async def test_offline_california_fallback_is_flagged(monkeypatch):
    async def suggest(client, q, lat, lon, limit=6, scope="us"):
        return []

    async def search(client, q, limit=5, near=None, scope="us"):
        return [(37.9358, -122.3477, "Richmond, California")]

    monkeypatch.setattr(planning, "stadia_suggest", suggest)
    monkeypatch.setattr(planning, "geocode_candidates", search)
    out = await planning.resolve(None, "Richmond", None, None, "place")
    assert "another state" in out["note"]
    named = await planning.resolve(None, "Richmond, CA", None, None, "place")
    assert "note" not in named


# ── Sources ──────────────────────────────────────────────────────────────────

def test_sources_are_never_borrowed_from_california():
    ohio = {"kind": "incident", "lat": 39.96, "lon": -83.0}
    assert planning.marker_source(ohio) is None
    assert planning.marker_source({**ohio, "src": "OHGO"}) == "OHGO"
    assert planning.marker_source(
        {"kind": "incident", "lat": 38.58, "lon": -121.49}) == "CHP"
    assert planning.marker_source(
        {"kind": "lane_closure", "lat": 34.05, "lon": -118.24}) == "Caltrans LCS"
    assert "source" not in planning.event_view(ohio, 1.0)


async def test_nearby_events_outside_california_name_no_california_agency(
        monkeypatch):
    async def markers(client, box, kinds):
        return [
            {"kind": "incident", "lat": 39.97, "lon": -83.0, "type": "Crash",
             "src": "OHGO"},
            {"kind": "lane_closure", "lat": 39.95, "lon": -83.01,
             "label": "Roadwork"},
        ], "2026-11-20T00:00:00+00:00"

    monkeypatch.setattr(snapshots, "markers", markers)
    out = await server.get_nearby_events(center="39.9612,-82.9988")
    assert {e["source"] for e in out["events"]} == {"OHGO", None}

    async def empty(client, box, kinds):
        return [], "2026-11-20T00:00:00+00:00"

    monkeypatch.setattr(snapshots, "markers", empty)
    out = await server.get_nearby_events(center="39.9612,-82.9988")
    assert "California" not in out["message"]
    assert "docs/" not in out["message"]


# ── California-only tools ────────────────────────────────────────────────────

CA_ONLY = ("check_route", "check_region", "rank_routes", "get_incidents",
           "get_lane_closures", "get_chain_controls", "get_wildfires",
           "get_cameras", "get_road_signs")
GENERIC = ("plan_trip", "best_time_to_go", "find_place", "get_nearby_events",
           "get_weather", "get_traffic", "get_area_history", "get_coverage",
           "get_my_places")


def _tools():
    return {t.name: t for t in server.mcp._tool_manager.list_tools()}


def test_california_only_tools_say_so_first():
    tools = _tools()
    for name in CA_ONLY:
        assert tools[name].description.lstrip().startswith("CALIFORNIA ONLY"), name
        assert "California" in tools[name].annotations.title, name


def test_generic_tools_carry_no_california_framing():
    tools = _tools()
    assert set(tools) == set(CA_ONLY) | set(GENERIC)
    for name in GENERIC:
        text = tools[name].description + str(tools[name].parameters)
        for word in ("Caltrans", "CHP", "Pacific", "docs/"):
            assert word not in text, (name, word)
    assert "California-only" in server.INSTRUCTIONS
    assert "38.58,-121.49" not in server.CENTER_FORMAT_ERROR


def _no_feeds(monkeypatch):
    def boom():
        raise AssertionError("a California feed was fetched for another state")
    monkeypatch.setattr(server, "get_road", boom)


@pytest.mark.parametrize(("tool", "kind"), [
    ("get_incidents", "incident"), ("get_lane_closures", "closure"),
    ("get_chain_controls", "chain"), ("get_wildfires", "fire"),
    ("get_cameras", "camera"), ("get_road_signs", "sign")])
async def test_california_tools_redirect_other_states(monkeypatch, tool, kind):
    _no_feeds(monkeypatch)
    out = await getattr(server, tool)(center="39.9612,-82.9988", radius_km=30)
    assert out["california_only"] is True
    assert "get_nearby_events" in out["error"] and f"kinds='{kind}'" in out["error"]


async def test_check_route_hands_other_states_to_plan_trip(monkeypatch):
    _no_feeds(monkeypatch)
    out = await server.check_route("Columbus, OH", "Cleveland, Ohio")
    assert out["california_only"] is True and "plan_trip" in out["error"]
    out = await server.check_route("a", "b", from_coords="39.96,-83.0",
                                   to_coords="41.50,-81.69")
    assert out["california_only"] is True


def test_reno_still_counts_as_reachable_from_california():
    assert server.touches_california(39.53, -119.81)
    assert not server.touches_california(39.96, -83.0, 160)
    assert not server.names_other_state("Reno, NV")
    assert server.names_other_state("Portland, Oregon")
    assert not server.names_other_state("Truckee, CA")


# ── Coverage ─────────────────────────────────────────────────────────────────

async def test_coverage_follows_the_maps_sources(monkeypatch):
    entries = [
        {"state": "Washington", "agency": "WSDOT", "name": "All feeds"},
        {"state": "Texas", "agency": "NTTA", "name": "Toll pricing"},
        {"state": "Texas (Austin)", "agency": "City of Austin",
         "name": "Roadwork (WZDx)"},
        {"state": "California", "agency": "CHP", "name": "Incidents"},
        {"state": "Ohio", "agency": "OHGO", "name": "All feeds",
         "status": "stale"},
        {"state": "Nationwide", "agency": "NWS", "name": "Weather alerts"},
        {"state": "Vermont", "agency": "VTrans", "name": "All", "status": "off"},
    ]

    async def map_sources(client):
        return entries

    monkeypatch.setattr(planning, "_map_sources", map_sources)
    out = await planning.get_coverage(object())
    assert out["states_covered"] == 4
    assert sorted(out["by_state"]) == ["California", "Ohio", "Texas", "Washington"]
    assert "City of Austin: Roadwork (WZDx) (Austin)" in out["by_state"]["Texas"]
    assert out["by_state"]["Ohio"] == ["OHGO: All feeds (stale)"]
    assert "notes" not in out
    assert "nationwide layers" in out["other_states"]


async def test_coverage_without_the_map_lists_own_feeds_and_says_so():
    out = await planning.get_coverage(None)
    assert any(s.startswith("CHP:") for s in out["by_state"]["California"])
    assert out["notes"]


async def test_state_feed_notes_explain_quiet_states(monkeypatch):
    monkeypatch.setenv("MCP_SNAPSHOT_BASE", "https://example.invalid")

    async def map_sources(client):
        return [{"state": "Ohio", "agency": "OHGO", "name": "All feeds"},
                {"state": "Iowa", "agency": "Iowa DOT",
                 "name": "Roadwork (WZDx)"}]

    monkeypatch.setattr(planning, "_map_sources", map_sources)
    ohio = await planning.state_feeds(object(), {"place": "Columbus, OH"})
    assert ohio == {"state": "Ohio", "feeds": ["OHGO: All feeds"]}
    iowa = await planning.state_feeds(object(), {"place": "Ames, IA"})
    assert "roadwork only" in iowa["note"]
    georgia = await planning.state_feeds(object(), {"place": "Macon, GA"})
    assert georgia["feeds"] == [] and "no live road-event feed" in georgia["note"]
    assert await planning.state_feeds(object(), {"place": "Nowhere"}) is None


async def test_state_feed_notes_stay_off_without_the_maps_list():
    assert await planning.state_feeds(object(), {"place": "Macon, GA"}) is None


async def test_a_hotel_named_after_a_landmark_sinks_below_it(monkeypatch):
    _fake_places(monkeypatch, [
        {"name": "InterContinental New York Times Square, New York, NY",
         "lat": 40.7579, "lon": -73.9903},
        {"name": "Times Square, New York, NY", "lat": 40.7580, "lon": -73.9855},
    ])
    cands = await planning.place_candidates(None, "Times Square", None)
    assert cands[0][2].startswith("Times Square")


@pytest.mark.parametrize("rows,local,start,want", [
    (SPRINGFIELDS, {"name": "Harrison Ave opp. East Springfield St, Boston, MA",
                    "lat": 42.3375, "lon": -71.0745},
     (42.3601, -71.0589), "Springfield, MA"),
    (PORTLANDS, {"name": "Portland #2, Seattle, WA",
                 "lat": 47.6800, "lon": -122.3300},
     (47.6062, -122.3321), "Portland, OR"),
])
async def test_a_bare_town_from_a_trip_start_is_the_town_not_a_local_stop(
        monkeypatch, rows, local, start, want):
    # Live on prod: "Springfield" from Boston routed 2.6 mi to a bus stop
    # on East Springfield St, and "Portland" from Seattle to a shop there.
    def nearest(lat, lon, pool):
        return sorted(pool, key=lambda r: (r["lat"] - lat) ** 2
                      + (r["lon"] - lon) ** 2)

    async def suggest(client, q, lat, lon, limit=6, scope="us"):
        if lat is None:
            return list(rows) + [local]
        return nearest(lat, lon, [local])  # the bias floods the list

    async def search(client, q, limit=5, near=None, scope="us"):
        return []

    monkeypatch.setattr(planning, "stadia_suggest", suggest)
    monkeypatch.setattr(planning, "geocode_candidates", search)
    out = await planning.resolve(None, want.split(",")[0], None, start,
                                 "destination")
    assert out["name"].startswith(want), out
