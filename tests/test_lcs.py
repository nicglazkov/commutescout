import httpx
import pytest
import respx

from ca_roads.feeds import lcs

NOW = 1783320000  # 2026-07-05 ~23:40 UTC, within the fixture's active window


def parse_fixture(fixture_bytes):
    closures, truncated = lcs.parse_lcs_xml(fixture_bytes("lcs_sample.xml"), district=3)
    assert not truncated
    return closures


def test_parse_fields(fixture_bytes):
    closures = parse_fixture(fixture_bytes)
    assert len(closures) == 4
    c = closures[0]
    assert c.index == "C5AB-0001-2026-07-06-19:01:00"
    assert c.route == "I-5"
    assert c.county == "San Joaquin"
    assert c.direction == "North"
    assert c.location_name == "Sacramento County Line"
    assert c.nearby_place == "Thornton"
    assert c.type_of_closure == "Lane"
    assert c.type_of_work == "Pavement Repair"
    assert c.lanes_closed == "2, RShoulder"
    assert c.begin_lat == pytest.approx(38.254878)
    assert c.begin_lon == pytest.approx(-121.447722)
    assert c.end_lat == pytest.approx(38.320371)
    assert c.begin_milepost == pytest.approx(495.096)
    assert c.end_milepost == pytest.approx(499.723)
    assert c.is_1097 and not c.is_1098 and not c.is_1022
    assert c.epoch_1097 == 1783305000
    assert c.district == 3


def test_is_active_established_only(fixture_bytes):
    closures = parse_fixture(fixture_bytes)
    active = [c for c in closures if lcs.is_active(c, NOW)]
    # Only the first record: established (1097) lane closure.
    # Skipped: not-yet-established, shoulder-only, and the ghost record
    # whose scheduled end passed weeks ago.
    assert [c.index.split("-")[0] for c in active] == ["C5AB"]


def test_is_active_respects_1098_and_1022(fixture_bytes):
    c = parse_fixture(fixture_bytes)[0]
    import dataclasses

    picked_up = dataclasses.replace(c, is_1098=True)
    canceled = dataclasses.replace(c, is_1022=True)
    assert not lcs.is_active(picked_up, NOW)
    assert not lcs.is_active(canceled, NOW)


def test_ghost_grace_period(fixture_bytes):
    c = parse_fixture(fixture_bytes)[0]
    just_over = c.end_epoch + lcs.END_OVERRUN_GRACE_SECONDS + 1
    just_under = c.end_epoch + lcs.END_OVERRUN_GRACE_SECONDS - 1
    assert lcs.is_active(c, just_under)
    assert not lcs.is_active(c, just_over)
    import dataclasses

    indefinite = dataclasses.replace(c, indefinite_end=True)
    assert lcs.is_active(indefinite, just_over)


@pytest.mark.parametrize(
    ("lanes", "expected"),
    [
        ("RShoulder", True),
        ("Median, LShoulder", True),
        ("3, RShoulder", False),
        ("All", False),
        ("Left HOV", False),
        ("Median, LShoulder, Auxiliary", False),
        ("Right Turn", False),
        ("", False),
    ],
)
def test_is_shoulder_only(lanes, expected):
    assert lcs.is_shoulder_only(lanes) is expected


def test_describe(fixture_bytes):
    closures = parse_fixture(fixture_bytes)
    assert (
        lcs.describe(closures[0])
        == ("I-5 lane closure @ Sacramento County Line (Thornton), "
           "1 of 2 lanes closed, est. delay 10 min")
    )
    ghost = closures[3]
    assert lcs.describe(ghost).startswith("I-80 FULL CLOSURE")
    assert "lanes:" not in lcs.describe(ghost)


@respx.mock
async def test_source_missing_district_is_note_not_failure(fixture_bytes):
    respx.get(lcs.feed_url(3)).mock(
        return_value=httpx.Response(200, content=fixture_bytes("lcs_sample.xml"))
    )
    respx.get(lcs.feed_url(10)).mock(side_effect=httpx.ConnectTimeout("timeout"))
    async with httpx.AsyncClient() as client:
        source = lcs.LcsSource(client)
        result = await source.get(districts=[3, 10])
        assert result.ok  # one district served
        assert len(result.records) == 4
        assert result.error and "D10" in result.error
        assert any("district 10" in n for n in result.notes)


@respx.mock
async def test_source_uses_cache_within_ttl(fixture_bytes):
    route = respx.get(lcs.feed_url(3)).mock(
        return_value=httpx.Response(200, content=fixture_bytes("lcs_sample.xml"))
    )
    async with httpx.AsyncClient() as client:
        source = lcs.LcsSource(client)
        await source.get(districts=[3])
        await source.get(districts=[3])
        assert route.call_count == 1


def make_closure(**overrides):
    import dataclasses

    from ca_roads.models import LaneClosure

    base = LaneClosure(
        index="X", district=4, route="US-101", county="", direction="North",
        location_name="loc", nearby_place="", type_of_closure="Lane",
        facility="Mainline", type_of_work="", lanes_closed="1",
        total_lanes=4, estimated_delay_minutes=None, duration="Standard",
        begin_lat=37.0, begin_lon=-121.9, end_lat=0.0, end_lon=0.0,
        begin_milepost=None, end_milepost=None, start_epoch=1, end_epoch=0,
        indefinite_end=True, is_1097=True, is_1098=False, is_1022=False,
        epoch_1097=1,
    )
    return dataclasses.replace(base, **overrides)


def test_closure_class_taxonomy():
    assert lcs.closure_class(make_closure()) == "lane"
    assert lcs.closure_class(make_closure(type_of_closure="Full")) == "full-roadway"
    # A Full closure of a ramp or connector is a ramp closure, full stop.
    assert lcs.closure_class(
        make_closure(type_of_closure="Full", facility="On Ramp")
    ) == "ramp"
    assert lcs.closure_class(
        make_closure(type_of_closure="Lane", facility="Connector")
    ) == "ramp"
    assert lcs.closure_class(
        make_closure(type_of_closure="One-Way Traffic", facility="Conventional Hwy")
    ) == "one-way-traffic"
    assert lcs.closure_class(
        make_closure(type_of_closure="Alternating Lanes")
    ) == "alternating-lanes"
    assert lcs.closure_class(make_closure(type_of_closure="Moving")) == "moving"
    assert lcs.closure_class(
        make_closure(type_of_closure="Traffic Break")
    ) == "traffic-break"
    assert lcs.closure_class(make_closure(facility="Surface Street")) == "other"


def test_is_full_roadway_only_for_roadways():
    assert lcs.is_full_roadway_closure(make_closure(type_of_closure="Full"))
    assert lcs.is_full_roadway_closure(
        make_closure(type_of_closure="Full", facility="Toll Bridge")
    )
    assert not lcs.is_full_roadway_closure(
        make_closure(type_of_closure="Full", facility="Off Ramp")
    )
    assert not lcs.is_full_roadway_closure(make_closure())


def test_lanes_summary():
    assert lcs.lanes_summary(make_closure(lanes_closed="1, 2")) == "2 of 4 lanes closed"
    assert lcs.lanes_summary(make_closure(lanes_closed="All")) == "all lanes closed"
    assert lcs.lanes_summary(
        make_closure(lanes_closed="Left HOV", total_lanes=None)
    ) == "lanes: Left HOV"
    assert lcs.lanes_summary(make_closure(lanes_closed="")) is None
