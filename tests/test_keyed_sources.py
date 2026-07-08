import httpx
import pytest
import respx

from ca_roads.feeds import bay511, nvroads, tomtom


@pytest.fixture(autouse=True)
def _clear(monkeypatch):
    tomtom._cache.clear()
    bay511._cache = None
    nvroads._cache = None


async def test_no_key_means_none_and_no_network():
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda req: (_ for _ in ()).throw(AssertionError("network hit"))
    )) as client:
        assert await tomtom.flow_at_point(client, 39.3, -120.3) is None
        assert await bay511.events(client) == []
        assert await nvroads.events(client) == []


@respx.mock
async def test_tomtom_flow_and_summary(monkeypatch):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key")
    respx.get(tomtom.FLOW_URL).mock(return_value=httpx.Response(200, json={
        "flowSegmentData": {"currentSpeed": 22, "freeFlowSpeed": 65,
                            "confidence": 0.95, "roadClosure": False}
    }))
    async with httpx.AsyncClient() as client:
        sample = await tomtom.flow_at_point(client, 37.5, -122.2)
    assert sample["current_mph"] == 22
    summary = tomtom.summarize([sample, {"current_mph": 60, "freeflow_mph": 65}])
    assert summary["flowing_freely"] is False
    assert summary["worst_point"]["current_mph"] == 22
    assert tomtom.summarize([None, {}]) is None


@respx.mock
async def test_bay511_parses_bom_json(monkeypatch):
    monkeypatch.setenv("BAY511_API_KEY", "test-key")
    body = (
        '﻿{"events": [{"headline": "Crash on US-101 NB", '
        '"event_type": "INCIDENT", "severity": "Moderate", '
        '"roads": [{"name": "US-101"}], '
        '"updated": "2026-07-08T18:00:00Z"}]}'
    )
    respx.get(bay511.EVENTS_URL).mock(
        return_value=httpx.Response(200, content=body.encode("utf-8")))
    async with httpx.AsyncClient() as client:
        out = await bay511.events(client)
    assert out[0]["headline"] == "Crash on US-101 NB"
    assert out[0]["roads"] == ["US-101"]


@respx.mock
async def test_nvroads_defensive_parse(monkeypatch):
    monkeypatch.setenv("NVROADS_API_KEY", "test-key")
    respx.get(nvroads.EVENTS_URL).mock(return_value=httpx.Response(200, json=[
        {"RoadwayName": "I-80", "DirectionOfTravel": "Westbound",
         "Description": "Crash near Verdi", "EventType": "accidentsAndIncidents",
         "IsFullClosure": False, "Latitude": 39.52, "Longitude": -119.99},
        "garbage-entry",
    ]))
    async with httpx.AsyncClient() as client:
        out = await nvroads.events(client)
    assert len(out) == 1
    assert out[0]["road"] == "I-80"
    assert out[0]["full_closure"] is False
