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
            "properties": {"name": "Alice's Restaurant", "state": "CA"},
        }]})
    )
    async with httpx.AsyncClient() as client:
        result = await geo.geocode(client, "17288 Skyline Blvd, Woodside")
    assert result[0] == 37.3866867
    assert "Alice's Restaurant" in result[2]
