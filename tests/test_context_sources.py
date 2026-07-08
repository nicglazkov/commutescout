import httpx
import pytest
import respx

from ca_roads.feeds import nws, quakes, wildfire


@pytest.fixture(autouse=True)
def _clear_caches():
    nws._cache.clear()
    quakes._cache = None


@respx.mock
async def test_nws_filters_to_road_relevant_and_dedupes():
    respx.get(nws.ALERTS_URL).mock(return_value=httpx.Response(200, json={
        "features": [
            {"id": "a1", "properties": {"event": "Winter Storm Warning",
                                        "severity": "Severe",
                                        "headline": "Snow tonight",
                                        "areaDesc": "Donner Pass"}},
            {"id": "a2", "properties": {"event": "Beach Hazards Statement",
                                        "severity": "Minor",
                                        "areaDesc": "Coast"}},
        ]
    }))
    async with httpx.AsyncClient() as client:
        # two nearby points that round to different cache keys
        alerts = await nws.alerts_at_points(
            client, [(39.32, -120.33), (39.1, -120.9)])
    assert len(alerts) == 1
    assert alerts[0]["event"] == "Winter Storm Warning"


@respx.mock
async def test_nws_failure_is_empty_not_fatal():
    respx.get(nws.ALERTS_URL).mock(side_effect=httpx.ConnectTimeout("down"))
    async with httpx.AsyncClient() as client:
        assert await nws.alerts_at_points(client, [(38.5, -121.5)]) == []


@respx.mock
async def test_quakes_parse_and_cache():
    route = respx.get(quakes.QUERY_URL).mock(return_value=httpx.Response(200, json={
        "features": [{"properties": {"mag": 5.1, "place": "near Ridgecrest",
                                     "time": 1783500000000},
                      "geometry": {"coordinates": [-117.6, 35.7, 8.0]}}]
    }))
    async with httpx.AsyncClient() as client:
        q1 = await quakes.recent_significant(client)
        q2 = await quakes.recent_significant(client)
    assert q1[0]["magnitude"] == 5.1
    assert q1[0]["lat"] == 35.7
    assert q2 == q1
    assert route.call_count == 1


@respx.mock
async def test_perimeter_failure_is_empty():
    respx.get(wildfire.PERIMETER_URL).mock(return_value=httpx.Response(500))
    async with httpx.AsyncClient() as client:
        out = await wildfire.perimeters_in_bbox(client, 37, -122, 38, -121)
    assert out == []


@respx.mock
async def test_perimeter_rings_flatten_to_points():
    respx.get(wildfire.PERIMETER_URL).mock(return_value=httpx.Response(200, json={
        "features": [{
            "attributes": {"poly_IncidentName": "lost ", "poly_GISAcres": 7834.0},
            "geometry": {"rings": [[[-120.1, 39.1], [-120.2, 39.2]]]},
        }]
    }))
    async with httpx.AsyncClient() as client:
        out = await wildfire.perimeters_in_bbox(client, 39, -121, 40, -119)
    assert out[0]["name"] == "LOST"
    assert out[0]["points"] == [(39.1, -120.1), (39.2, -120.2)]
