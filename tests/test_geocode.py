import httpx
import pytest
import respx

from ca_roads_mcp import geocode as geo


@pytest.fixture(autouse=True)
def _fast_and_isolated(monkeypatch):
    monkeypatch.setattr(geo, "THROTTLE_SECONDS", 0)
    geo._cache.clear()


@respx.mock
async def test_geocode_resolves_and_caches():
    route = respx.get(geo.NOMINATIM_URL).mock(
        return_value=httpx.Response(200, json=[{
            "lat": "37.3866867", "lon": "-122.2653984",
            "display_name": "Alice's Restaurant, Skyline Boulevard, Woodside, "
                            "San Mateo County, California, 94062, United States",
        }])
    )
    async with httpx.AsyncClient() as client:
        result = await geo.geocode(client, "Alice's Restaurant, Woodside")
        assert result[0] == 37.3866867
        assert "Alice's Restaurant" in result[2]
        # Second call served from cache.
        await geo.geocode(client, "alice's restaurant, woodside")
        assert route.call_count == 1
        # The first candidate is the query as given, bounded to California.
        assert "bounded=1" in str(route.calls[0].request.url)


@respx.mock
async def test_geocode_failure_returns_none():
    respx.get(geo.NOMINATIM_URL).mock(side_effect=httpx.ConnectTimeout("slow"))
    respx.get(geo.PHOTON_URL).mock(side_effect=httpx.ConnectTimeout("slow"))
    async with httpx.AsyncClient() as client:
        assert await geo.geocode(client, "Nowhereville") is None


@respx.mock
async def test_geocode_empty_results_cached_as_none():
    route = respx.get(geo.NOMINATIM_URL).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(geo.PHOTON_URL).mock(
        return_value=httpx.Response(200, json={"features": []})
    )
    async with httpx.AsyncClient() as client:
        assert await geo.geocode(client, "zzz nonexistent") is None
        first_count = route.call_count
        assert first_count >= 2  # bounded, unbounded, then the trim ladder
        assert await geo.geocode(client, "zzz nonexistent") is None
        assert route.call_count == first_count  # the miss is cached


@respx.mock
async def test_photon_fallback_when_nominatim_blocked():
    respx.get(geo.NOMINATIM_URL).mock(return_value=httpx.Response(429))
    respx.get(geo.PHOTON_URL).mock(
        return_value=httpx.Response(200, json={"features": [{
            "geometry": {"coordinates": [-122.2653984, 37.3866867]},
            "properties": {"name": "Alice's Restaurant", "state": "CA",
                           "street": "Skyline Boulevard", "city": "Woodside"},
        }]})
    )
    async with httpx.AsyncClient() as client:
        result = await geo.geocode(client, "17288 Skyline Blvd, Woodside")
    assert result[0] == 37.3866867
    assert "Alice's Restaurant" in result[2]


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
    # miss so the network geocoders resolve the actual POI.
    assert geo.gazetteer_lookup("San Jose Airport") is None
    assert geo.gazetteer_lookup("Santa Cruz Beach Boardwalk") is None
    assert geo.gazetteer_lookup("Sacramento Capitol") is None


def test_cache_is_bounded():
    geo._cache.clear()
    for i in range(geo._CACHE_MAX + 50):
        geo._cache_put(f"k{i}", None)
    assert len(geo._cache) == geo._CACHE_MAX


@respx.mock
async def test_photon_rejects_token_mismatched_fuzzy_hits():
    # Photon fuzzy-matches: a house-number query once returned an
    # entirely unrelated street in another town.
    respx.get(geo.NOMINATIM_URL).mock(return_value=httpx.Response(200, json=[]))
    respx.get(geo.PHOTON_URL).mock(
        return_value=httpx.Response(200, json={"features": [{
            "geometry": {"coordinates": [-121.8663, 37.3437]},
            "properties": {"name": "South 23rd Street", "city": "San Jose",
                           "state": "California"},
        }]})
    )
    async with httpx.AsyncClient() as client:
        assert await geo.geocode(client, "175 Kestrel Rd") is None


@respx.mock
async def test_candidates_surface_ambiguity():
    respx.get(geo.NOMINATIM_URL).mock(return_value=httpx.Response(200, json=[
        {"lat": "37.3720944", "lon": "-122.1103216",
         "display_name": "175, Kestrel Road, Los Altos, Santa Clara County"},
        {"lat": "37.1259", "lon": "-122.1222",
         "display_name": "Kestrel Road, Boulder Creek, Santa Cruz County"},
    ]))
    async with httpx.AsyncClient() as client:
        cands = await geo.geocode_candidates(client, "175 Kestrel Rd")
    assert len(cands) == 2
    assert "Los Altos" in cands[0][2]


@respx.mock
async def test_photon_guard_ignores_locality_qualifier_matches():
    # "Riverside Drive, San Jose" must not accept "San Jose Drive, San
    # Jacinto" just because the locality word matches.
    respx.get(geo.PHOTON_URL).mock(
        return_value=httpx.Response(200, json={"features": [{
            "geometry": {"coordinates": [-116.9586, 33.7839]},
            "properties": {"name": "San Jose Drive", "city": "San Jacinto",
                           "state": "California"},
        }]})
    )
    hits = await geo._photon_hits(None or __import__("httpx").AsyncClient(),
                                  "Riverside Drive, San Jose")
    assert hits == []


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
