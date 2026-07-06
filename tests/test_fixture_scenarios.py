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
async def test_quiet_single_closure_and_shoulder_excluded(scenario):
    result = await tool_server.get_lane_closures()
    assert [c["location"] for c in result["closures"]] == ["Trimble Rd"]


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
