import httpx
import pytest
import respx

from ca_roads_mcp import geocode as geo


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    monkeypatch.setenv("STADIA_API_KEY", "test-key")
    geo._cache.clear()


def pelias(features):
    return httpx.Response(200, json={"features": features})


def feature(lat, lon, label, name=None, layer="address", **props):
    return {"geometry": {"coordinates": [lon, lat]},
            "properties": {"label": label,
                           "name": name or label.split(",")[0],
                           "layer": layer, **props}}


@respx.mock
async def test_geocode_resolves_and_caches():
    route = respx.get(geo.STADIA_SEARCH_URL).mock(
        return_value=pelias([feature(
            37.3866867, -122.2653984,
            "Alice's Restaurant, Skyline Boulevard, Woodside, CA, USA",
        )]))
    async with httpx.AsyncClient() as client:
        result = await geo.geocode(client, "Alice's Restaurant, Woodside")
        assert result[0] == 37.3866867
        assert "Alice's Restaurant" in result[2]
        # Second call served from cache.
        await geo.geocode(client, "alice's restaurant, woodside")
        assert route.call_count == 1
        # Search stays inside the California rectangle, key as param.
        url = str(route.calls[0].request.url)
        assert "boundary.rect.min_lon" in url
        assert "api_key=test-key" in url


@respx.mock
async def test_geocode_failure_returns_none_and_retries_later():
    route = respx.get(geo.STADIA_SEARCH_URL).mock(
        side_effect=httpx.ConnectTimeout("slow"))
    async with httpx.AsyncClient() as client:
        assert await geo.geocode(client, "Nowhereville") is None
        first = route.call_count
        # Network trouble is not a definitive miss: the next call tries
        # the network again instead of serving a cached None.
        assert await geo.geocode(client, "Nowhereville") is None
        assert route.call_count > first


@respx.mock
async def test_geocode_empty_results_cached_as_none():
    route = respx.get(geo.STADIA_SEARCH_URL).mock(
        return_value=pelias([]))
    async with httpx.AsyncClient() as client:
        assert await geo.geocode(client, "zzz nonexistent") is None
        first_count = route.call_count
        assert first_count >= 2  # CA-qualified, raw, then the trim ladder
        assert await geo.geocode(client, "zzz nonexistent") is None
        assert route.call_count == first_count  # the miss is cached


@respx.mock
async def test_geocode_without_key_is_gazetteer_only(monkeypatch):
    monkeypatch.delenv("STADIA_API_KEY", raising=False)
    route = respx.get(geo.STADIA_SEARCH_URL).mock(
        return_value=pelias([feature(37.0, -121.0, "Anything, CA, USA")]))
    async with httpx.AsyncClient() as client:
        # Known place still resolves offline.
        sj = await geo.geocode(client, "San Jose")
        assert abs(sj[0] - 37.296) < 0.01
        # Unknown query returns None with zero network calls and is not
        # cached as a definitive miss.
        assert await geo.geocode(client, "Some Unknown Diner") is None
        assert route.call_count == 0
        assert "some unknown diner" not in geo._cache


async def test_gazetteer_resolves_known_places_offline():
    # No respx mocks active: any network attempt would blow up the test.
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda req: (_ for _ in ()).throw(AssertionError("network hit"))
    )) as client:
        sj = await geo.geocode(client, "San Jose")
        assert abs(sj[0] - 37.296) < 0.01
        reno = await geo.geocode(client, "Reno")
        assert "Nevada" in reno[2]
        assert await geo.geocode(client, "truckee, CA") is not None
        assert await geo.geocode(client, "Truckee downtown") is not None


def test_gazetteer_refuses_poi_queries():
    # "San Jose Airport" is not the San Jose city center; the gazetteer must
    # miss so the network geocoder resolves the actual POI.
    assert geo.gazetteer_lookup("San Jose Airport") is None
    assert geo.gazetteer_lookup("Santa Cruz Beach Boardwalk") is None
    assert geo.gazetteer_lookup("Sacramento Capitol") is None


def test_cache_is_bounded():
    geo._cache.clear()
    for i in range(geo._CACHE_MAX + 50):
        geo._cache_put(f"k{i}", None)
    assert len(geo._cache) == geo._CACHE_MAX


@respx.mock
async def test_search_rejects_token_mismatched_fuzzy_hits():
    # A house-number query must not accept an entirely unrelated street.
    respx.get(geo.STADIA_SEARCH_URL).mock(
        return_value=pelias([feature(
            37.3437, -121.8663,
            "South 23rd Street, San Jose, CA, USA", layer="street")]))
    async with httpx.AsyncClient() as client:
        assert await geo.geocode(client, "175 Kestrel Rd") is None


@respx.mock
async def test_search_guard_ignores_locality_qualifier_matches():
    # "Riverside Drive, San Jose" must not accept "San Jose Drive, San
    # Jacinto" just because the locality word matches.
    respx.get(geo.STADIA_SEARCH_URL).mock(
        return_value=pelias([feature(
            33.7839, -116.9586,
            "San Jose Drive, San Jacinto, CA, USA", layer="street")]))
    async with httpx.AsyncClient() as client:
        hits = await geo._search_stadia(client, "Riverside Drive, San Jose")
    assert hits == []


@respx.mock
async def test_candidates_surface_ambiguity():
    respx.get(geo.STADIA_SEARCH_URL).mock(
        return_value=pelias([
            feature(37.3720944, -122.1103216,
                    "175 Kestrel Road, Los Altos, CA, USA"),
            feature(37.1259, -122.1222,
                    "Kestrel Road, Boulder Creek, CA, USA", layer="street"),
        ]))
    async with httpx.AsyncClient() as client:
        cands = await geo.geocode_candidates(client, "175 Kestrel Rd")
    assert len(cands) == 2
    assert "Los Altos" in cands[0][2]


@respx.mock
async def test_suggest_maps_autocomplete_features():
    route = respx.get(geo.STADIA_AUTOCOMPLETE_URL).mock(
        return_value=pelias([feature(
            37.3866, -122.2654,
            "Skyline Boulevard, Woodside, CA, USA",
            name="Skyline Boulevard", layer="street",
            locality="Woodside", region_a="CA")]))
    async with httpx.AsyncClient() as client:
        got = await geo.stadia_suggest(client, "skyline blvd", 37.4, -122.2)
    assert got[0]["name"] == "Skyline Boulevard, Woodside, CA"
    assert got[0]["kind"] == "street"
    url = str(route.calls[0].request.url)
    assert "focus.point.lat" in url and "api_key=test-key" in url
    # The abbreviation expands before it reaches the API.
    assert "boulevard" in url


@respx.mock
async def test_suggest_without_key_returns_empty(monkeypatch):
    monkeypatch.delenv("STADIA_API_KEY", raising=False)
    route = respx.get(geo.STADIA_AUTOCOMPLETE_URL).mock(
        return_value=pelias([]))
    async with httpx.AsyncClient() as client:
        assert await geo.stadia_suggest(client, "skyline", 37.4, -122.2) == []
    assert route.call_count == 0


def test_san_francisco_is_not_in_the_ocean():
    # The Census centroid for San Francisco includes the Farallon Islands,
    # which drags it ~30 miles offshore; the gazetteer overrides it to
    # downtown. Guard against a regenerated CSV reintroducing the ocean.
    lat, lon, _ = geo.gazetteer_lookup("San Francisco")
    assert abs(lat - 37.779) < 0.05
    assert abs(lon - -122.419) < 0.05


def test_suggest_prefers_the_shorter_famous_place():
    from ca_roads_mcp.geocode import gazetteer_suggest

    names = [s["name"] for s in gazetteer_suggest("san jo")]
    assert names[0].startswith("San Jose")
