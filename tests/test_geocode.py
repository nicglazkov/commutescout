import httpx
import respx

from ca_roads_mcp import geocode as geo


@respx.mock
async def test_geocode_resolves_and_caches():
    geo._cache.clear()
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
        # California is appended to unqualified queries.
        assert "California" in str(route.calls[0].request.url)


@respx.mock
async def test_geocode_failure_returns_none():
    geo._cache.clear()
    respx.get(geo.NOMINATIM_URL).mock(side_effect=httpx.ConnectTimeout("slow"))
    async with httpx.AsyncClient() as client:
        assert await geo.geocode(client, "Nowhereville") is None


@respx.mock
async def test_geocode_empty_results_cached_as_none():
    geo._cache.clear()
    route = respx.get(geo.NOMINATIM_URL).mock(
        return_value=httpx.Response(200, json=[])
    )
    async with httpx.AsyncClient() as client:
        assert await geo.geocode(client, "zzz nonexistent") is None
        assert await geo.geocode(client, "zzz nonexistent") is None
        assert route.call_count == 1
