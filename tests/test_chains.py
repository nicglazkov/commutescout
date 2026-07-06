import httpx
import respx

from ca_roads.feeds import chains


def test_parse_fields(fixture_bytes):
    controls, truncated = chains.parse_cc_xml(fixture_bytes("cc_sample.xml"), district=3)
    assert not truncated
    assert len(controls) == 3
    c = controls[1]
    assert c.index == "3-ED-50-33.2-E-101"
    assert c.route == "US-50"
    assert c.county == "El Dorado"
    assert c.location_name == "Twin Bridges"
    assert c.status == "R-2"
    assert c.in_service
    assert c.status_updated_at is not None
    assert c.status_updated_at.year == 2026


def test_is_active(fixture_bytes):
    controls, _ = chains.parse_cc_xml(fixture_bytes("cc_sample.xml"), district=3)
    active = [c for c in controls if chains.is_active(c)]
    # R-0 excluded, out-of-service R-2 excluded; only the live R-2 remains.
    assert [c.index for c in active] == ["3-ED-50-33.2-E-101"]


def test_describe(fixture_bytes):
    controls, _ = chains.parse_cc_xml(fixture_bytes("cc_sample.xml"), district=3)
    assert chains.describe(controls[1]) == "Chains R-2 on US-50 @ Twin Bridges (Twin Bridges)"


@respx.mock
async def test_missing_district_feed_is_empty_not_error(fixture_bytes):
    # Flatland districts answer 404 or 500 permanently; both mean
    # "no chain-control checkpoints here", cached as a normal empty result.
    respx.get(chains.feed_url(3)).mock(
        return_value=httpx.Response(200, content=fixture_bytes("cc_sample.xml"))
    )
    d4 = respx.get(chains.feed_url(4)).mock(return_value=httpx.Response(500))
    d12 = respx.get(chains.feed_url(12)).mock(return_value=httpx.Response(404))
    async with httpx.AsyncClient() as client:
        source = chains.ChainSource(client)
        result = await source.get(districts=[3, 4, 12])
        assert result.ok
        assert result.error is None
        assert len(result.records) == 3  # only D3 contributes

        # The no-feed answer is cached: no re-request on the next call.
        await source.get(districts=[3, 4, 12])
        assert d4.call_count == 1
        assert d12.call_count == 1


@respx.mock
async def test_all_districts_down_is_failure():
    respx.get(chains.feed_url(3)).mock(side_effect=httpx.ConnectError("boom"))
    async with httpx.AsyncClient() as client:
        source = chains.ChainSource(client)
        result = await source.get(districts=[3])
        assert not result.ok
        assert result.error
