import json

import httpx
import pytest
import respx

from ca_roads.feeds import wildfire


def load(fixture_bytes):
    return json.loads(fixture_bytes("wfigs_sample.json"))


def test_parse(fixture_bytes):
    fires, notes = wildfire.parse_wfigs_json(load(fixture_bytes))
    assert notes == []
    # RX burn and missing-geometry features are skipped.
    assert [f.id for f in fires] == ["2026-CAKRN-025007", "2026-CAENF-001234"]
    lost = fires[0]
    assert lost.name == "LOST"
    assert lost.size_acres == 7834
    assert lost.percent_contained == 100
    assert lost.discovered_at is not None
    ridge = fires[1]
    assert ridge.size_acres is None
    assert ridge.percent_contained is None
    assert ridge.discovered_at is None


def test_error_body_raises():
    with pytest.raises(wildfire.WfigsQueryError):
        wildfire.parse_wfigs_json({"error": {"code": 400, "message": "Invalid field"}})


def test_transfer_limit_note(fixture_bytes):
    payload = load(fixture_bytes)
    payload["exceededTransferLimit"] = True
    _, notes = wildfire.parse_wfigs_json(payload)
    assert any("record cap" in n for n in notes)


def test_describe(fixture_bytes):
    fires, _ = wildfire.parse_wfigs_json(load(fixture_bytes))
    assert wildfire.describe(fires[0]) == "Wildfire: LOST, 7,834 acres, 100% contained"
    assert wildfire.describe(fires[1]) == "Wildfire: RIDGE"


@respx.mock
async def test_source_error_body_is_failure(fixture_bytes):
    route = respx.get(wildfire.QUERY_URL).mock(
        return_value=httpx.Response(200, json={"error": {"code": 400, "message": "bad"}})
    )
    async with httpx.AsyncClient() as client:
        source = wildfire.WildfireSource(client)
        result = await source.get()
        assert not result.ok
        assert "WFIGS query error" in (result.error or "")

    assert route.call_count == 1


@respx.mock
async def test_source_ok_and_cached(fixture_bytes):
    route = respx.get(wildfire.QUERY_URL).mock(
        return_value=httpx.Response(200, json=load(fixture_bytes))
    )
    async with httpx.AsyncClient() as client:
        source = wildfire.WildfireSource(client)
        result = await source.get()
        assert result.ok
        assert len(result.records) == 2
        await source.get()
        assert route.call_count == 1
