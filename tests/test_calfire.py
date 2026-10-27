"""CAL FIRE feed parsing and the WFIGS merge/dedupe rules."""

from datetime import UTC, datetime

from ca_roads.feeds.calfire import (
    merge_with_wfigs,
    normalize_fire_name,
    parse_calfire_json,
)
from ca_roads.models import FeedResult, Wildfire

ITEM = {
    "Name": "3-1 Pit Fire",
    "Started": "2026-07-07T13:35:02Z",
    "AcresBurned": 1055.0,
    "PercentContained": 45.0,
    "Longitude": -121.26181,
    "Latitude": 40.94913,
    "Type": "Wildfire",
    "UniqueId": "05803e87",
    "IsActive": True,
}


def wf(name, lat, lon, fid="w1"):
    return Wildfire(id=fid, name=name, lat=lat, lon=lon,
                    size_acres=100.0, percent_contained=10.0,
                    discovered_at=None)


def result(records, source="wfigs", ok=True, error=None):
    return FeedResult(source=source, records=records,
                      data_as_of=datetime.now(UTC), ok=ok, error=error)


def test_parse_keeps_active_wildfires_only():
    items = [
        ITEM,
        {**ITEM, "UniqueId": "gone", "IsActive": False},
        {**ITEM, "UniqueId": "flood", "Type": "Flood"},
        {**ITEM, "UniqueId": "nowhere", "Latitude": None},
    ]
    fires = parse_calfire_json(items)
    assert [f.id for f in fires] == ["calfire-05803e87"]
    assert fires[0].name == "3-1 Pit Fire"
    assert fires[0].size_acres == 1055.0
    assert fires[0].discovered_at.year == 2026


def test_name_normalization_bridges_the_two_feeds():
    assert normalize_fire_name("3-1 Pit Fire") == "31PIT"
    assert normalize_fire_name("31 PIT") == "31PIT"
    assert normalize_fire_name("RIDGE") == "RIDGE"
    assert normalize_fire_name("Ridge Fire") == "RIDGE"
    # "Fire" only strips as a suffix word, not from within a name.
    assert normalize_fire_name("Fireweed") == "FIREWEED"


def test_merge_drops_same_fire_and_keeps_new_ones():
    wfigs = result([wf("RIDGE", 40.0, -121.0)])
    calfire = result([
        # Same name 3 km away: duplicate, WFIGS record wins.
        parse_calfire_json([{**ITEM, "Name": "Ridge Fire",
                             "Latitude": 40.02, "Longitude": -121.02}])[0],
        # Different name far away: genuinely new.
        parse_calfire_json([{**ITEM, "UniqueId": "new1",
                             "Name": "Cedar Fire",
                             "Latitude": 37.2, "Longitude": -119.5}])[0],
    ], source="calfire")
    merged = merge_with_wfigs(wfigs, calfire)
    names = [f.name for f in merged.records]
    assert names == ["RIDGE", "Cedar Fire"]
    assert any("1 additional fire" in n for n in merged.notes)


def test_merge_dedupes_by_proximity_even_when_names_differ():
    wfigs = result([wf("COW CREEK", 40.0, -121.0)])
    calfire = result(parse_calfire_json([
        {**ITEM, "Name": "Cow Fire", "Latitude": 40.001,
         "Longitude": -121.001}]), source="calfire")
    merged = merge_with_wfigs(wfigs, calfire)
    assert len(merged.records) == 1  # ~140 m apart: same fire


def test_merge_survives_either_feed_failing():
    wfigs = result([wf("RIDGE", 40.0, -121.0)])
    dead = FeedResult(source="calfire", records=[], data_as_of=None,
                      ok=False, error="boom")
    merged = merge_with_wfigs(wfigs, dead)
    assert [f.name for f in merged.records] == ["RIDGE"]
    assert "CAL FIRE feed unavailable" in merged.notes

    dead_wfigs = FeedResult(source="wfigs", records=[], data_as_of=None,
                            ok=False, error="down")
    calfire = result(parse_calfire_json([ITEM]), source="calfire")
    merged = merge_with_wfigs(dead_wfigs, calfire)
    assert merged.ok is True
    assert len(merged.records) == 1
    assert "WFIGS unavailable; CAL FIRE records only" in merged.notes


def test_wfigs_internal_duplicates_collapse():
    # Seen live: the same fire listed twice under two unit codes at the
    # same coordinates.
    wfigs = result([wf("HILLTOP", 33.46, -117.44, "2026-CAORCC-095194"),
                    wf("HILLTOP", 33.46, -117.44, "2026-CAORC-000004")])
    merged = merge_with_wfigs(wfigs, result([], source="calfire"))
    assert len(merged.records) == 1
