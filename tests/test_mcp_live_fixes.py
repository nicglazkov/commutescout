"""Defects a live check of the MCP server turned up on 2026-09-16:
out-of-range coordinates accepted silently, Caltrans districts not
validated, an uncapped closures list (597 KB unfiltered), the
nationwide tool empty inside California, silent clamps, and the
advertised Los Angeles to Las Vegas corridor starting at Barstow."""

import dataclasses
from datetime import UTC, datetime

from ca_roads.models import ChpIncident, FeedResult, LaneClosure
from ca_roads_mcp import corridors as corr
from ca_roads_mcp import server

AS_OF = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)

INC = ChpIncident(
    id="260916GG0001", log_type="1182-Trfc Collision-No Inj",
    location="Sr84 E / University Ave Onr", area="Redwood City",
    lat=37.482, lon=-122.14, reported_at=AS_OF,
)

BASE_CLOSURE = LaneClosure(
    index="X", district=4, route="US-101", county="", direction="North",
    location_name="loc", nearby_place="", type_of_closure="Lane",
    facility="Mainline", type_of_work="", lanes_closed="1",
    total_lanes=4, estimated_delay_minutes=None, duration="Standard",
    begin_lat=37.0, begin_lon=-121.9, end_lat=0.0, end_lon=0.0,
    begin_milepost=None, end_milepost=None, start_epoch=1, end_epoch=0,
    indefinite_end=True, is_1097=True, is_1098=False, is_1022=False,
    epoch_1097=1,
)


class FakeRoad:
    client = None

    def __init__(self, incidents=(), closures=()):
        self._inc = list(incidents)
        self._clo = list(closures)

    async def incidents(self):
        return FeedResult(source="chp", records=self._inc, data_as_of=AS_OF)

    async def lane_closures(self, districts=None):
        return FeedResult(source="lcs", records=self._clo, data_as_of=AS_OF)

    async def chain_controls(self, **_kw):
        return FeedResult(source="chains", records=[], data_as_of=AS_OF)

    async def wildfires(self):
        return FeedResult(source="wfigs", records=[], data_as_of=AS_OF)


def test_parse_center_rejects_out_of_range_coordinates():
    assert server.parse_center("99,999") is None
    assert server.parse_center("37.7,-122.4") == (37.7, -122.4)
    assert server.parse_center("-90,180") == (-90.0, 180.0)
    assert server.parse_center("abc") is None


def test_los_angeles_to_las_vegas_resolves_to_i15():
    match = corr.resolve_corridor("Los Angeles", "Las Vegas")
    assert match is not None and match.corridor.routes == ("I-15",)
    assert not match.reversed
    back = corr.resolve_corridor("Las Vegas", "Ontario, CA")
    assert back is not None and back.corridor.id == match.corridor.id
    assert back.reversed
    # The polyline now begins in the basin, so LA-area coordinates snap.
    dist, _ = corr.distance_to_corridor(match.corridor, 34.07, -117.60)
    assert dist < corr.SNAP_MAX_METERS


async def test_district_out_of_range_is_an_error_before_any_fetch(monkeypatch):
    def no_feed():
        raise AssertionError("the feed must not be touched")

    monkeypatch.setattr(server, "get_road", no_feed)
    res = await server.get_lane_closures(district=13)
    assert "error" in res and "1 to 12" in res["error"]
    res = await server.get_lane_closures(district=0)
    assert "error" in res


async def test_closures_are_capped_with_a_truncation_note(monkeypatch):
    closures = [dataclasses.replace(BASE_CLOSURE, index=str(i))
                for i in range(server.CLOSURES_CAP + 50)]
    monkeypatch.setattr(server, "get_road", lambda: FakeRoad(closures=closures))
    res = await server.get_lane_closures()
    assert res["count"] == server.CLOSURES_CAP
    assert res["total"] == server.CLOSURES_CAP + 50
    assert res["truncated"] is True
    assert any(str(server.CLOSURES_CAP) in n for n in res["notes"])


async def test_small_closure_lists_are_not_marked_truncated(monkeypatch):
    monkeypatch.setattr(server, "get_road", lambda: FakeRoad(closures=[BASE_CLOSURE]))
    res = await server.get_lane_closures()
    assert res["count"] == res["total"] == 1 and res["truncated"] is False


async def test_nearby_events_include_california_feeds(monkeypatch):
    from ca_roads_demo import states

    async def no_expansion(_client, _box, _want, **_kw):
        return []

    monkeypatch.setattr(states, "markers_for_bbox", no_expansion)
    monkeypatch.setattr(server, "get_road", lambda: FakeRoad(
        incidents=[INC], closures=[BASE_CLOSURE]))
    res = await server.get_nearby_events("37.5,-122.1", radius_km=20)
    kinds = {(e["kind"], e["source"]) for e in res["events"]}
    assert ("incident", "CHP") in kinds
    assert res["count"] == 1  # the closure at 37.0,-121.9 is 60 km away
    ev = res["events"][0]
    assert ev["type"].startswith("1182") and "Sr84" in ev["summary"]
    wide = await server.get_nearby_events("37.5,-122.1", radius_km=100,
                                          kinds="closure")
    assert wide["count"] == 1 and wide["events"][0]["source"] == "Caltrans LCS"
    assert wide["events"][0]["closure_class"] == "lane"


async def test_nearby_events_note_the_radius_clamp(monkeypatch):
    from ca_roads_demo import states

    async def no_expansion(_client, _box, _want, **_kw):
        return []

    monkeypatch.setattr(states, "markers_for_bbox", no_expansion)
    monkeypatch.setattr(server, "get_road", lambda: FakeRoad())
    res = await server.get_nearby_events("39.7,-104.9", radius_km=500)
    assert res["filters"]["radius_km"] == 160.0
    assert any("160" in n for n in res["notes"])
