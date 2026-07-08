"""Ground-truth checks for the eval fixtures, through the real tool functions.

These don't involve any LLM: they pin down that each scenario's fixtures
produce exactly the conditions the golden questions assume.
"""

import pytest
from evals.fixture_mode import fixture_road_data

from ca_roads_mcp import server as tool_server


@pytest.fixture
def scenario(request):
    road = fixture_road_data(request.param)
    old = tool_server._road
    tool_server._road = road
    yield request.param
    tool_server._road = old


def for_scenario(name):
    return pytest.mark.parametrize("scenario", [name], indirect=True)


@for_scenario("storm-day")
async def test_storm_us50_chains(scenario):
    result = await tool_server.get_chain_controls(route="50")
    levels = {(c["location"], c["level"]) for c in result["chain_controls"]}
    assert ("Twin Bridges", "R-2") in levels
    assert ("Meyers", "R-2") in levels
    assert ("Pollock Pines", "R-1") in levels


@for_scenario("storm-day")
async def test_storm_route_sac_tahoe_has_controls_in_order(scenario):
    result = await tool_server.check_route("Sacramento", "South Lake Tahoe")
    kinds = [e["kind"] for e in result["events"]]
    assert "chain_control" in kinds
    chains = [e for e in result["events"] if e["kind"] == "chain_control"]
    names = [c["detail"]["location"] for c in chains]
    # Ordered going east: Pollock Pines before Twin Bridges before Meyers.
    assert names.index("Pollock Pines") < names.index("Twin Bridges")
    assert "R-2" in result["summary"]


@for_scenario("storm-day")
async def test_storm_sr89_full_closure(scenario):
    result = await tool_server.get_lane_closures(route="89")
    assert result["count"] == 1
    assert result["closures"][0]["is_full_closure"]
    assert result["closures"][0]["location"] == "Emerald Bay"


@for_scenario("storm-day")
async def test_storm_scheduled_work_not_reported(scenario):
    result = await tool_server.get_lane_closures(route="US-50")
    assert result["count"] == 0  # Placerville tree work has no 1097


@for_scenario("quiet-day")
async def test_quiet_no_chains_message(scenario):
    result = await tool_server.get_chain_controls()
    assert result["count"] == 0
    assert "No chain controls active" in result["message"]


@for_scenario("quiet-day")
async def test_quiet_closures_classified_and_shoulder_excluded(scenario):
    result = await tool_server.get_lane_closures()
    by_location = {c["location"]: c for c in result["closures"]}
    assert set(by_location) == {"Trimble Rd", "Story Rd", "La Honda"}
    assert by_location["Trimble Rd"]["closure_class"] == "lane"
    assert by_location["Trimble Rd"]["lanes"] == "1 of 4 lanes closed"
    # A "Full" closure of an on-ramp is a ramp closure, not a closed highway.
    assert by_location["Story Rd"]["closure_class"] == "ramp"
    assert not by_location["Story Rd"]["is_full_closure"]
    assert by_location["La Honda"]["closure_class"] == "one-way-traffic"
    assert by_location["La Honda"]["estimated_delay_minutes"] == 10


@for_scenario("quiet-day")
async def test_quiet_sr17_route_clear(scenario):
    result = await tool_server.check_route("San Jose", "Santa Cruz")
    assert result["events"] == []
    assert "no active" in result["summary"]


@for_scenario("fire-day")
async def test_fire_i5_closed_both_directions(scenario):
    result = await tool_server.get_lane_closures(route="5")
    fulls = [c for c in result["closures"] if c["is_full_closure"]]
    assert len(fulls) == 2
    assert {c["direction"] for c in fulls} == {"North", "South"}


@for_scenario("fire-day")
async def test_fire_vulcan_near_i5(scenario):
    result = await tool_server.get_wildfires(near_route="I-5")
    names = [f["name"] for f in result["wildfires"]]
    assert names == ["VULCAN"]
    assert result["wildfires"][0]["percent_contained"] == 15


@for_scenario("fire-day")
async def test_fire_route_la_sac_reports_closure_and_fire(scenario):
    result = await tool_server.check_route("Los Angeles", "Sacramento")
    kinds = {e["kind"] for e in result["events"]}
    assert "lane_closure" in kinds
    assert "wildfire" in kinds
    assert "FULL" in result["summary"]


@for_scenario("fire-day")
async def test_fire_remote_not_near_highways(scenario):
    result = await tool_server.get_wildfires()
    remote = next(f for f in result["wildfires"] if f["name"] == "REMOTE")
    assert remote["near_highways"] == []


@for_scenario("quiet-day")
async def test_area_miss_returns_warning_with_dispatch_areas(scenario):
    result = await tool_server.get_incidents(area="Coyote")
    assert result["count"] == 0
    assert "dispatch-area" in result["warning"]
    assert "East Sac" in result["warning"]  # recovery path lists real areas
    assert "center=" in result["warning"]


@for_scenario("quiet-day")
async def test_center_filter_catches_closures_on_any_road(scenario):
    result = await tool_server.get_lane_closures(center="37.39,-121.93", radius_km=15)
    assert {c["location"] for c in result["closures"]} == {"Trimble Rd", "Story Rd"}
    far = await tool_server.get_lane_closures(center="38.58,-121.49", radius_km=15)
    assert far["count"] == 0


@for_scenario("storm-day")
async def test_center_filter_chain_controls_around_truckee(scenario):
    result = await tool_server.get_chain_controls(center="39.33,-120.18", radius_km=25)
    names = {c["location"] for c in result["chain_controls"]}
    assert "Donner Lake Interchange" in names
    assert "Kingvale" in names
    assert "Carson Pass" not in names  # 70+ km away


@for_scenario("fire-day")
async def test_center_filter_wildfires_around_lebec(scenario):
    result = await tool_server.get_wildfires(center="34.84,-118.86", radius_km=50)
    assert [f["name"] for f in result["wildfires"]] == ["VULCAN"]


@for_scenario("quiet-day")
async def test_region_bay_area_report(scenario):
    result = await tool_server.check_region("the bay area")
    assert result["region"] == "San Francisco Bay Area"
    assert result["counts"]["lane_closures"] == 3
    assert result["counts"]["full_closures"] == 0  # the ramp Full doesn't count
    assert result["counts"]["ramp_closures"] == 1
    # SF and Berkeley incidents are in-region; Sacramento and Bakersfield not.
    locations = " ".join(i["location"] for i in result["incidents"])
    assert "Cesar Chavez" in locations and "University" in locations
    assert "Jackson" not in locations and "Ming" not in locations


@for_scenario("storm-day")
async def test_region_sierra_report(scenario):
    result = await tool_server.check_region("the sierra")
    assert result["counts"]["chain_controls"] == 9
    assert result["counts"]["full_closures"] == 1
    assert "strictest R-2" in result["summary"]


@for_scenario("fire-day")
async def test_region_socal_report(scenario):
    result = await tool_server.check_region("socal")
    assert result["counts"]["full_closures"] == 2
    assert [f["name"] for f in result["wildfires"]] == ["VULCAN"]
    # Full closures sort first, injury collision leads incidents.
    assert result["closures"][0]["is_full_closure"]


@for_scenario("quiet-day")
async def test_region_unknown_lists_options(scenario):
    result = await tool_server.check_region("the moon")
    assert "supported_regions" in result


@for_scenario("quiet-day")
async def test_route_clips_to_landmark_destination(scenario):
    result = await tool_server.check_route(
        "San Jose", "Alice's Restaurant", to_coords="37.417,-122.276"
    )
    assert result["corridor"].startswith("I-280")
    lats = [lat for lat, lon in result["route_geometry"]]
    # The drawn route stops near Woodside instead of running up to SF.
    assert max(lats) < 37.6
    assert result["trip_miles_approx"] < 45
    # The destination is the actual place, not the corridor snap point.
    assert result["destination"] == [37.417, -122.276]
    assert abs(result["origin"][0] - 37.33) < 0.1  # San Jose end


@for_scenario("quiet-day")
async def test_local_trip_gets_center_hint(scenario):
    result = await tool_server.check_route(
        "444 Castro St, Mountain View", "1 Infinite Loop, Cupertino",
        from_coords="37.3894,-122.0819", to_coords="37.3318,-122.0302",
    )
    assert result.get("local_trip") is True
    assert "suggested_center" in result


def test_synthetic_fixtures_have_not_rotted():
    """The synthetic closures use a fixed far-future end epoch so 'in place
    now' stays true. When that horizon nears, regenerate the fixtures."""
    import datetime

    from evals.build_fixtures import FAR_FUTURE_EPOCH

    horizon = datetime.datetime.fromtimestamp(FAR_FUTURE_EPOCH, datetime.UTC)
    remaining = horizon - datetime.datetime.now(datetime.UTC)
    assert remaining.days > 365, (
        "Synthetic fixture closures expire within a year (FAR_FUTURE_EPOCH). "
        "Bump it in evals/build_fixtures.py and rerun the builder."
    )


@for_scenario("real-2026-07-07")
async def test_real_recording_plays_back(scenario):
    """The first real (non-synthetic) recording: 2026-07-07, fire season.
    Pins the day's headline numbers so fixture serving (gzip + recorded
    status replay) stays honest end to end."""
    road = tool_server.get_road()
    chp = await road.incidents()
    lcs = await road.lane_closures()
    chains = await road.chain_controls()
    fires = await road.wildfires()
    assert len(chp.records) == 197
    assert len(lcs.records) == 293
    assert len(chains.records) == 0  # July; D12's 500 replays as recorded
    assert len(fires.records) == 232

    fires_i5 = await tool_server.get_wildfires(near_route="I-5")
    assert fires_i5["count"] > 40
    names = {f["name"] for f in fires_i5["wildfires"]}
    assert "BIG" in names


@for_scenario("quiet-day")
async def test_check_route_asks_when_destination_is_ambiguous(scenario, monkeypatch):
    from ca_roads_mcp import server as srv

    async def two_towns(client, place, limit=4, near=None):
        return [
            (37.3721, -122.1103, "175, Kestrel Road, Los Altos, Santa Clara County"),
            (37.1259, -122.1222, "Kestrel Road, Boulder Creek, Santa Cruz County"),
        ]

    monkeypatch.setattr(srv, "geocode_candidates", two_towns)
    out = await srv.check_route(
        "San Jose", "175 Kestrel Rd", from_coords="37.3382,-121.8863"
    )
    assert out.get("needs_clarification") is True
    assert any("Los Altos" in o for o in out["options"])
    assert any("Boulder Creek" in o for o in out["options"])
