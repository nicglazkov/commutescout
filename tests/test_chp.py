from datetime import datetime

import httpx
import pytest
import respx

from ca_roads.feeds import chp


def test_parse_full_feed(fixture_bytes):
    incidents, truncated = chp.parse_chp_xml(fixture_bytes("chp_sample.xml"))
    assert not truncated
    # 4 Log records in the fixture; the 0:0 and missing-LATLON ones are dropped.
    assert [i.id for i in incidents] == ["260705SA1309", "260705SA1293"]
    first = incidents[0]
    assert first.log_type == "1125-Traffic Hazard"  # quotes stripped
    assert first.location == "Jackson Rd / Mayhew Rd"
    assert first.area == "East Sac"
    assert first.lat == pytest.approx(38.531446)
    assert first.lon == pytest.approx(-121.344046)  # western lon negated
    assert first.reported_at is not None
    assert first.reported_at.tzinfo is not None


def test_parse_truncated_feed_salvages_complete_records(fixture_bytes):
    incidents, truncated = chp.parse_chp_xml(fixture_bytes("chp_truncated.xml"))
    assert truncated
    assert [i.id for i in incidents] == ["260705SA1309", "260705SA1293"]


@pytest.mark.parametrize(
    "raw",
    [
        '"Jul  5 2026  9:53PM"',
        '"Jul 5 2026 9:53 PM"',
        '"07/05/2026 09:53 PM"',
        '"07/05/2026 21:53"',
    ],
)
def test_parse_log_time_formats(raw):
    parsed = chp.parse_log_time(raw)
    assert parsed == datetime(2026, 7, 5, 21, 53, tzinfo=chp.TZ_PACIFIC)


def test_parse_log_time_garbage():
    assert chp.parse_log_time('"not a time"') is None
    assert chp.parse_log_time("") is None


def test_parse_latlon():
    assert chp.parse_latlon('"38531446:121344046"') == pytest.approx((38.531446, -121.344046))
    # Explicit minus must not flip the longitude eastward.
    assert chp.parse_latlon("38531446:-121344046") == pytest.approx((38.531446, -121.344046))
    assert chp.parse_latlon("0:0") is None
    assert chp.parse_latlon("garbage") is None


@respx.mock
async def test_source_fetch_and_304(fixture_bytes):
    route = respx.get(chp.CHP_URL).mock(
        return_value=httpx.Response(
            200, content=fixture_bytes("chp_sample.xml"), headers={"ETag": '"abc"'}
        )
    )
    async with httpx.AsyncClient() as client:
        source = chp.ChpSource(client)
        result = await source.get()
        assert result.ok and not result.stale
        assert len(result.records) == 2
        first_as_of = result.data_as_of

        # Second request sends the validator and serves the last parse on 304.
        route.mock(return_value=httpx.Response(304))
        result2 = await source.get()
        assert route.calls.last.request.headers.get("If-None-Match") == '"abc"'
        assert result2.ok
        assert len(result2.records) == 2
        assert result2.data_as_of >= first_as_of


@respx.mock
async def test_source_serves_stale_on_failure(fixture_bytes):
    route = respx.get(chp.CHP_URL).mock(
        return_value=httpx.Response(200, content=fixture_bytes("chp_sample.xml"))
    )
    async with httpx.AsyncClient() as client:
        source = chp.ChpSource(client)
        await source.get()
        route.mock(side_effect=httpx.ConnectError("boom"))
        result = await source.get()
        assert result.ok
        assert result.stale
        assert result.error and "ConnectError" in result.error
        assert len(result.records) == 2


@respx.mock
async def test_source_fails_without_cache():
    respx.get(chp.CHP_URL).mock(side_effect=httpx.ConnectError("boom"))
    async with httpx.AsyncClient() as client:
        source = chp.ChpSource(client)
        result = await source.get()
        assert not result.ok
        assert result.records == []
        assert result.error


def test_to_event_families():
    def make(log_type):
        return chp.ChpIncident(
            id="X", log_type=log_type, location="L", area="A",
            lat=38.0, lon=-121.0, reported_at=None,
        )

    assert chp.to_event(make("1183-Trfc Collision-Unkn Inj")).family == "accident"
    assert chp.to_event(make("CLOSURE of a Road")).family == "closure"
    assert chp.to_event(make("1125-Traffic Hazard")).family == "incident"


async def test_truncated_feed_carries_recent_records(respx_mock=None):
    import httpx
    import respx

    from ca_roads.feeds.chp import ChpSource

    full = b"""<?xml version="1.0" encoding="UTF-8"?>
<State>
<Center ID="MY">
<Dispatch ID="A">
<Log ID="1"><LogType>"1182-Trfc Collision-No Inj"</LogType>
<LogTime>"Jul 11 2026 11:37PM"</LogTime>
<Location>"Sr9 / Shingle Mill Rd"</Location><Area>"Santa Cruz"</Area>
<LATLON>"37248342:122154090"</LATLON></Log>
<Log ID="2"><LogType>"1125-Traffic Hazard"</LogType>
<LogTime>"Jul 11 2026 11:38PM"</LogTime>
<Location>"US-101 N"</Location><Area>"San Jose"</Area>
<LATLON>"37338200:121886300"</LATLON></Log>
</Dispatch>
</Center>
</State>"""
    # Truncated mid-record: only Log 2 is gone.
    truncated = full.split(b"<Log ID=\"2\">")[0]

    async with httpx.AsyncClient() as client:
        source = ChpSource(client)
        with respx.mock:
            respx.get("https://media.chp.ca.gov/sa_xml/sa.xml").mock(
                return_value=httpx.Response(200, content=full))
            first = await source.get()
            assert {i.id for i in first.records} == {"1", "2"}

        with respx.mock:
            # Both the fetch and the cache-busted retry return the cut file.
            respx.get("https://media.chp.ca.gov/sa_xml/sa.xml").mock(
                return_value=httpx.Response(200, content=truncated))
            second = await source.get()
            # Log 2 sits behind the cut but was seen recently: carried.
            assert {i.id for i in second.records} == {"1", "2"}
            assert any("carried forward" in n for n in second.notes)
