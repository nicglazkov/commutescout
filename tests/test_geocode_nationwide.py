"""Search outside California: the site and app search boxes and the
address check used to be fenced to a California rectangle, so "Pike
Place Market, Seattle" found nothing and "1600 Pennsylvania Ave" found
only California streets."""

import httpx
import pytest
import respx
from starlette.testclient import TestClient

from ca_roads_mcp import geocode as geo


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    monkeypatch.setenv("STADIA_API_KEY", "test-key")
    geo._cache.clear()


def pelias(features):
    return httpx.Response(200, json={"features": features})


def feature(lat, lon, label, layer="venue", **props):
    return {"geometry": {"coordinates": [lon, lat]},
            "properties": {"label": label, "name": label.split(",")[0],
                           "layer": layer, **props}}


PIKE = feature(47.6097, -122.3422, "Pike Place Market, Seattle, WA, USA",
               locality="Seattle", region_a="WA")


@respx.mock
async def test_us_scope_searches_the_whole_country():
    route = respx.get(geo.STADIA_SEARCH_URL).mock(return_value=pelias([PIKE]))
    async with httpx.AsyncClient() as client:
        cands = await geo.geocode_candidates(
            client, "Pike Place Market, Seattle", scope="us")
    assert cands and "Seattle" in cands[0][2]
    url = str(route.calls[0].request.url)
    assert "boundary.rect" not in url
    # No ", California" ladder for nationwide queries.
    assert "California" not in url


@respx.mock
async def test_ca_scope_still_rejects_out_of_state_hits():
    respx.get(geo.STADIA_SEARCH_URL).mock(return_value=pelias([PIKE]))
    async with httpx.AsyncClient() as client:
        assert await geo.geocode_candidates(
            client, "Pike Place Market, Seattle") == []


@respx.mock
async def test_us_scope_skips_the_california_gazetteer_for_bare_names():
    # "Columbia" is a California town in the gazetteer and a city in
    # several other states; nationwide, the network answers.
    respx.get(geo.STADIA_SEARCH_URL).mock(return_value=pelias([
        feature(38.9517, -92.3341, "Columbia, MO, USA", layer="locality")]))
    async with httpx.AsyncClient() as client:
        cands = await geo.geocode_candidates(client, "Columbia", scope="us")
    assert "MO" in cands[0][2]


@respx.mock
async def test_us_scope_falls_back_to_gazetteer_when_network_is_down():
    respx.get(geo.STADIA_SEARCH_URL).mock(return_value=httpx.Response(503))
    async with httpx.AsyncClient() as client:
        cands = await geo.geocode_candidates(client, "Sacramento", scope="us")
    assert cands and "Sacramento" in cands[0][2]


@respx.mock
async def test_us_scope_trusts_gazetteer_when_the_query_names_california():
    route = respx.get(geo.STADIA_SEARCH_URL).mock(return_value=pelias([]))
    async with httpx.AsyncClient() as client:
        cands = await geo.geocode_candidates(client, "Truckee, CA", scope="us")
    assert cands and "Truckee" in cands[0][2]
    assert route.call_count == 0


@respx.mock
async def test_us_scope_rejects_hits_outside_the_country():
    respx.get(geo.STADIA_SEARCH_URL).mock(return_value=pelias([
        feature(51.5079, -0.0877, "Pike Place, London, UK")]))
    async with httpx.AsyncClient() as client:
        assert await geo.geocode_candidates(
            client, "Pike Place", scope="us") == []


@respx.mock
async def test_us_geocode_passes_focus_point():
    route = respx.get(geo.STADIA_SEARCH_URL).mock(return_value=pelias([PIKE]))
    async with httpx.AsyncClient() as client:
        hit = await geo.geocode(client, "Pike Place Market", scope="us",
                                near=(47.6, -122.3))
    assert hit and "Seattle" in hit[2]
    assert "focus.point.lat=47.6" in str(route.calls[0].request.url)


@pytest.fixture
def client():
    from ca_roads_demo.app import app

    return TestClient(app)


def test_suggest_endpoint_finds_places_outside_california(client):
    with respx.mock:
        route = respx.get(geo.STADIA_AUTOCOMPLETE_URL).mock(
            return_value=pelias([PIKE]))
        r = client.get("/api/suggest?q=pike%20place&lat=47.6&lon=-122.3")
    names = [s["name"] for s in r.json()["suggestions"]]
    assert names[0].startswith("Pike Place Market, Seattle")
    url = str(route.calls[0].request.url)
    assert "boundary.rect" not in url and "focus.point.lat=47.6" in url


def test_suggest_without_position_sends_no_california_bias(client):
    with respx.mock:
        route = respx.get(geo.STADIA_AUTOCOMPLETE_URL).mock(
            return_value=pelias([PIKE]))
        client.get("/api/suggest?q=pike%20place")
    assert "focus.point" not in str(route.calls[0].request.url)


def test_suggest_far_from_california_drops_gazetteer_rows(client):
    with respx.mock:
        respx.get(geo.STADIA_AUTOCOMPLETE_URL).mock(return_value=pelias([
            feature(39.9612, -82.9988, "Columbus, OH, USA", layer="locality",
                    locality="Columbus", region_a="OH")]))
        r = client.get("/api/suggest?q=colu&lat=39.96&lon=-83.0")
    names = [s["name"] for s in r.json()["suggestions"]]
    assert not any("California" in n for n in names)


def test_geocode_endpoint_resolves_out_of_state_addresses(client):
    with respx.mock:
        respx.get(geo.STADIA_SEARCH_URL).mock(return_value=pelias([
            feature(38.8977, -77.0365,
                    "1600 Pennsylvania Avenue NW, Washington, DC, USA",
                    layer="address")]))
        r = client.get("/api/geocode?q=1600%20Pennsylvania%20Ave")
    cands = r.json()["candidates"]
    assert cands and "Washington" in cands[0]["name"]
