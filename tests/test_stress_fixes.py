"""Defects the MCP stress run (scripts/stress_mcp.py) turned up on
2026-11-05: unrecognized routes dropped silently (route='🚗' answered
with every closure in the state), NaN and infinite radii accepted,
unknown event kinds answering "nothing nearby", hints naming a
place_coords parameter no tool has, a 108 KB place sent to the geocoder
and echoed back whole, and pydantic's raw dump for a bad argument."""

import asyncio

import pytest
from tests.test_mcp_live_fixes import BASE_CLOSURE, INC, FakeRoad

from ca_roads_mcp import planning, server


@pytest.fixture
def road(monkeypatch):
    fake = FakeRoad(incidents=[INC], closures=[BASE_CLOSURE])
    monkeypatch.setattr(server, "get_road", lambda: fake)
    return fake


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("call", [
    lambda: server.get_incidents(highway="🚗🔥"),
    lambda: server.get_lane_closures(route="None"),
    lambda: server.get_chain_controls(route="'; DROP TABLE x; --"),
    lambda: server.get_wildfires(near_route="undefined"),
    lambda: server.get_cameras(route="<script>"),
    lambda: server.get_road_signs(route="nowhere"),
])
def test_unrecognized_route_is_refused(road, call):
    out = run(call())
    assert "must be a highway" in out["error"]


def test_blank_route_means_no_filter(road):
    out = run(server.get_lane_closures(route="  \n"))
    assert out["count"] == 1


def test_blank_area_means_no_filter(road):
    assert run(server.get_incidents(area="\n\t"))["count"] == 1


@pytest.mark.parametrize("radius", [float("nan"), float("inf"), -1.0, 0.0, 501.0])
@pytest.mark.parametrize("tool", ["get_incidents", "get_lane_closures", "get_chain_controls",
                                  "get_wildfires", "get_cameras", "get_road_signs"])
def test_radius_is_finite_and_bounded(road, tool, radius):
    out = run(getattr(server, tool)(center="37.48,-122.14", radius_km=radius))
    assert "radius_km must be" in out["error"]


def test_nearby_rejects_nan_radius(road):
    out = run(server.get_nearby_events(center="37.48,-122.14", radius_km=float("nan")))
    assert "radius_km" in out["error"]


@pytest.mark.parametrize("kinds", ["crashes", "incident,teleport", "🚗"])
def test_nearby_rejects_unknown_kinds(road, kinds):
    out = run(server.get_nearby_events(center="37.48,-122.14", kinds=kinds))
    assert "unknown kinds" in out["error"]
    assert "incident" in out["error"]


def test_coords_hint_names_a_real_parameter(monkeypatch):
    async def no_places():
        return [], "none"

    async def no_candidates(*_a, **_kw):
        return []

    monkeypatch.setattr(planning.account, "places", no_places)
    monkeypatch.setattr(planning, "place_candidates", no_candidates)
    miss = run(planning.resolve(None, "Nowhereville", None, None, "place"))
    assert "pass center" in miss["error"] and "place_coords" not in miss["error"]
    blank = run(planning.resolve(None, "", None, None, "place"))
    assert "or center" in blank["error"]
    trip = run(planning.resolve(None, "Nowhereville", None, None, "origin"))
    assert "origin_coords" in trip["error"]


def test_long_place_never_reaches_the_geocoder(monkeypatch):
    async def no_places():
        return [], "none"

    async def boom(*_a, **_kw):
        raise AssertionError("geocoder called")

    monkeypatch.setattr(planning.account, "places", no_places)
    monkeypatch.setattr(planning, "place_candidates", boom)
    out = run(planning.resolve(None, "Los Angeles " * 9000, None, None, "destination"))
    assert "under 300" in out["error"]
    assert len(out["error"]) < 300


def test_miss_echo_is_bounded(monkeypatch):
    async def no_places():
        return [], "none"

    async def no_candidates(*_a, **_kw):
        return []

    monkeypatch.setattr(planning.account, "places", no_places)
    monkeypatch.setattr(planning, "place_candidates", no_candidates)
    out = run(planning.resolve(None, "x" * 290, None, None, "origin"))
    assert len(out["error"]) < 250


def test_bad_argument_reads_as_one_line():
    async def call():
        return await server.mcp.call_tool("get_weather", {"place": "Reno", "hours": 999})

    with pytest.raises(server.ToolError) as exc:
        run(call())
    text = str(exc.value)
    assert text.startswith("Invalid arguments for get_weather: hours:")
    assert "errors.pydantic.dev" not in text and "input_value" not in text


def test_named_city_beats_namesakes_near_the_origin(monkeypatch):
    # Austin to "Houston, TX" once routed 8 miles to Houston Elementary.
    async def suggest(_c, q, lat, lon, limit=6):
        if lat is not None:
            return [{"name": "Houston Elementary School, Austin, TX", "lat": 30.2, "lon": -97.7}]
        return [{"name": "Houston, TX", "lat": 29.76, "lon": -95.37}]

    async def nothing(*_a, **_kw):
        return []

    monkeypatch.setattr(planning, "stadia_suggest", suggest)
    monkeypatch.setattr(planning, "geocode_candidates", nothing)
    out = run(planning.place_candidates(None, "Houston, TX", (30.27, -97.74)))
    assert out[0][2] == "Houston, TX, USA"


def test_explicit_foreign_places_are_refused():
    for place in ("Vancouver, BC", "Tijuana, Mexico", "Toronto, Ontario"):
        assert planning.names_abroad(place)
    for place in ("Ontario, CA", "Vancouver, WA", "Mexico, MO", "New Mexico"):
        assert not planning.names_abroad(place)


def test_city_state_parsing():
    assert planning.city_state("Fairbanks, AK") == ("fairbanks", "AK")
    assert planning.city_state("Portland, Maine") == ("portland", "ME")
    assert planning.city_state("1600 Main St, Reno") is None
    assert planning.city_state("Pike Place Market") is None


@pytest.mark.parametrize("coords", ["48.85,2.35", "0,0", "-33.86,151.21"])
def test_points_outside_the_us_are_refused(coords):
    out = run(planning.point_from(None, None, coords))
    assert "outside the United States" in out["error"]
    trip = run(planning.resolve(None, None, coords, None, "origin"))
    assert "origin_coords is outside" in trip["error"]


def test_traffic_points_are_deduped_and_capped(monkeypatch):
    calls = []

    async def flow(_c, lat, lon):
        calls.append((lat, lon))
        return {"current_mph": 30, "freeflow_mph": 60}

    monkeypatch.setattr(planning.tomtom_feed, "api_key", lambda: "k")
    monkeypatch.setattr(planning.tomtom_feed, "flow_at_point", flow)
    same = run(planning.get_traffic(None, points="|".join(["37.79,-122.39"] * 50)))
    assert len(same["readings"]) == 1 and len(calls) == 1
    many = "|".join(f"37.{i:02d},-122.39" for i in range(12))
    out = run(planning.get_traffic(None, points=many))
    assert len(out["readings"]) == 10 and "first 10" in out["notes"][0]
    assert "points must be" in run(planning.get_traffic(None, points="||"))["error"]


def test_stadia_get_retries_once(monkeypatch):
    import httpx

    from ca_roads_mcp import geocode

    statuses = iter([429, 200])

    class Client:
        n = 0

        async def get(self, *_a, **_kw):
            Client.n += 1
            return httpx.Response(next(statuses), json={"features": []})

    async def fast(_s):
        return None

    monkeypatch.setattr(geocode.asyncio, "sleep", fast)
    resp = run(geocode._stadia_get(Client(), "https://x", {}, "k", timeout=1))
    assert resp.status_code == 200 and Client.n == 2


def test_a_street_named_after_the_town_is_not_the_town():
    city = ("vail", "CO")
    assert planning._is_city((39.6, -106.4, "Vail, CO, USA"), city)
    assert not planning._is_city((39.7, -105.0, "Vail, Colorado, Denver, CO, USA"), city)
