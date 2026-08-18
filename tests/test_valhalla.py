"""Stadia Valhalla routing client: polyline6 codec and request shape."""

import httpx
import pytest
import respx
from httpx import Response as HttpxResponse

from ca_roads_demo import valhalla


def encode_polyline6(points: list[list[float]]) -> str:
    """Reference encoder (Valhalla's format) for round-trip tests."""
    out = []
    prev_lat = prev_lon = 0
    for lat, lon in points:
        for value, prev in ((lat, prev_lat), (lon, prev_lon)):
            delta = round(value * 1e6) - prev
            delta = ~(delta << 1) if delta < 0 else delta << 1
            while delta >= 0x20:
                out.append(chr((0x20 | (delta & 0x1F)) + 63))
                delta >>= 5
            out.append(chr(delta + 63))
        prev_lat = round(lat * 1e6)
        prev_lon = round(lon * 1e6)
    return "".join(out)


SJ_SF = [[37.3382, -121.8863], [37.4848, -122.2281], [37.7749, -122.4194]]


def test_polyline6_round_trip():
    assert valhalla.decode_polyline6(encode_polyline6(SJ_SF)) == SJ_SF


def test_polyline6_negative_deltas():
    pts = [[40.0, -120.0], [39.5, -120.5], [39.5001, -120.4999]]
    got = valhalla.decode_polyline6(encode_polyline6(pts))
    assert got == pts


def trip_body(points: list[list[float]], length_km: float) -> dict:
    return {"trip": {
        "legs": [{"shape": encode_polyline6(points)}],
        "summary": {"length": length_km, "time": 1200},
    }}


@respx.mock
@pytest.mark.asyncio
async def test_route_posts_key_and_returns_trip():
    route = respx.post("https://api.stadiamaps.com/route/v1").mock(
        return_value=HttpxResponse(200, json=trip_body(SJ_SF, 77.2)))
    async with httpx.AsyncClient() as client:
        trip = await valhalla.route(
            client,
            [{"lat": 37.3382, "lon": -121.8863},
             {"lat": 37.7749, "lon": -122.4194}],
            api_key="test-key")
    req = route.calls[0].request
    assert req.url.params["api_key"] == "test-key"
    sent = respx.calls[0].request.read()
    assert b'"costing": "auto"' in sent or b'"costing":"auto"' in sent
    assert trip["summary"]["length"] == 77.2
    assert valhalla.trip_points(trip) == SJ_SF
    assert valhalla.trip_meters(trip) == pytest.approx(77_200.0)


@respx.mock
@pytest.mark.asyncio
async def test_route_400_raises_no_candidate():
    respx.post("https://api.stadiamaps.com/route/v1").mock(
        return_value=HttpxResponse(400, json={"error": "No suitable edges"}))
    async with httpx.AsyncClient() as client:
        with pytest.raises(valhalla.NoCandidateError):
            await valhalla.route(
                client, [{"lat": 0, "lon": 0}, {"lat": 1, "lon": 1}],
                api_key="k")


@respx.mock
@pytest.mark.asyncio
async def test_route_empty_trip_returns_none():
    respx.post("https://api.stadiamaps.com/route/v1").mock(
        return_value=HttpxResponse(200, json={"trip": {"legs": []}}))
    async with httpx.AsyncClient() as client:
        assert await valhalla.route(
            client, [{"lat": 0, "lon": 0}, {"lat": 1, "lon": 1}],
            api_key="k") is None


@respx.mock
@pytest.mark.asyncio
async def test_route_server_error_raises():
    respx.post("https://api.stadiamaps.com/route/v1").mock(
        return_value=HttpxResponse(503))
    async with httpx.AsyncClient() as client:
        with pytest.raises(httpx.HTTPStatusError):
            await valhalla.route(
                client, [{"lat": 0, "lon": 0}, {"lat": 1, "lon": 1}],
                api_key="k")
