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
        == "I-5 Lane closure @ Sacramento County Line (Thornton), lanes: 2, RShoulder"
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
