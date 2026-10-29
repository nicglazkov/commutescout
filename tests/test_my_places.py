"""The caller's own places in the trip tools: "home", "work", saved
names, a default origin, "my location", and the key's account reaching
the tool through the real HTTP stack."""

import json

import pytest
from starlette.testclient import TestClient

from ca_roads import apikeys
from ca_roads_mcp import account, planning

PLACES = [
    {"kind": "home", "name": "Home", "lat": 37.44, "lon": -122.16},
    {"kind": "work", "name": "Office on Market", "lat": 37.79, "lon": -122.40},
    {"kind": "saved", "name": "Gold's Gym", "lat": 37.40, "lon": -122.10},
    {"kind": "recent", "name": "Ferry Building", "lat": 37.7955, "lon": -122.3937},
]


@pytest.fixture
def signed_in(monkeypatch):
    account._cache.clear()

    async def fake(uid):
        assert uid == "u1"
        return PLACES

    monkeypatch.setattr(account, "_account_places", fake)
    token = account.CURRENT.set({"id": "k1", "uid": "u1", "tier": "free"})
    yield
    account.CURRENT.reset(token)


@pytest.fixture(autouse=True)
def _no_env_places(monkeypatch):
    monkeypatch.delenv("MCP_HOME", raising=False)
    monkeypatch.delenv("MCP_WORK", raising=False)


def test_match_reads_home_work_and_saved_names():
    assert account.match("home", PLACES)["kind"] == "home"
    assert account.match("my office", PLACES)["kind"] == "work"
    assert account.match("the gym", PLACES)["name"] == "Gold's Gym"
    assert account.match("Ferry Building", PLACES)["kind"] == "recent"
    assert account.match("Pike Place Market", PLACES) is None
    assert account.wants_here("My location") and not account.wants_here("Here St")


async def test_saved_places_resolve_without_geocoding(signed_in, monkeypatch):
    async def no_geocoding(*a, **k):
        raise AssertionError("saved places must not hit the geocoder")
    monkeypatch.setattr(planning, "place_candidates", no_geocoding)
    home = await planning.resolve(None, "home", None, None, "origin")
    assert (home["lat"], home["lon"], home["saved_place"]) == (37.44, -122.16, "home")
    work = await planning.resolve(None, "work", None, None, "destination")
    assert work["name"] == "Work (Office on Market)"
    gym = await planning.resolve(None, "the gym", None, None, "destination")
    assert gym["name"] == "Gold's Gym"


async def test_no_origin_starts_from_home(signed_in):
    out = await planning.resolve(None, None, None, None, "origin")
    assert out["defaulted_to_home"] is True and out["lat"] == 37.44
    # A destination never defaults.
    dest = await planning.resolve(None, None, None, None, "destination")
    assert "error" in dest


async def test_my_location_asks_for_coordinates(signed_in):
    out = await planning.resolve(None, "my location", None, None, "origin")
    assert out["needs_location"] is True
    assert "cannot see the user's device" in out["error"]
    # Coordinates the model already has always win.
    here = await planning.resolve(None, "my location", "40.7,-74.0", None, "origin")
    assert here["lat"] == 40.7


async def test_home_without_a_key_says_how_to_connect():
    out = await planning.resolve(None, "home", None, None, "origin")
    assert out["needs_saved_place"] == "home"
    assert "API key" in out["error"]
    listed = await planning.my_places()
    assert listed["connected"] is False and "cs_live_" in listed["message"]


async def test_server_places_from_env(monkeypatch):
    monkeypatch.setenv("MCP_HOME", "39.74,-104.99")
    out = await planning.resolve(None, None, None, None, "origin")
    assert (out["lat"], out["lon"], out["saved_place"]) == (39.74, -104.99, "home")
    listed = await planning.my_places()
    assert listed["source"] == "server" and listed["places"][0]["address"] == "39.74,-104.99"


async def test_account_without_home_says_so(monkeypatch):
    account._cache.clear()

    async def empty(uid):
        return []
    monkeypatch.setattr(account, "_account_places", empty)
    token = account.CURRENT.set({"id": "k1", "uid": "u2", "tier": "free"})
    try:
        out = await planning.resolve(None, "home", None, None, "origin")
    finally:
        account.CURRENT.reset(token)
    assert "No Home is saved" in out["error"]


async def test_my_places_lists_the_account(signed_in):
    out = await planning.my_places()
    assert out["connected"] is True
    assert [p["kind"] for p in out["places"]] == ["home", "work", "saved", "recent"]
    assert out["places"][0]["coords"] == "37.44000,-122.16000"


def _sse_json(text: str) -> dict:
    for line in text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:])
    return json.loads(text)


async def test_the_key_reaches_the_tool_over_streamable_http(monkeypatch):
    """The middleware's context must survive the SDK's task hand-off:
    a keyed POST to /mcp sees that account's places, a keyless one
    does not."""
    from mcp.server.transport_security import TransportSecuritySettings

    from ca_roads_mcp import server
    from ca_roads_mcp.ratelimit import ApiKeyMiddleware

    account._cache.clear()

    async def fake(uid):
        return PLACES if uid == "u1" else []
    monkeypatch.setattr(account, "_account_places", fake)

    store = apikeys.MemoryKeyStore()
    full, _ = await apikeys.create_key(store, "u1", "someone@example.com", "test")
    app = ApiKeyMiddleware(
        server.mcp.streamable_http_app(
            streamable_http_path="/mcp", stateless_http=True,
            transport_security=TransportSecuritySettings(
                enable_dns_rebinding_protection=False)),
        resolver=apikeys.KeyResolver(store))
    call = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "get_my_places", "arguments": {}}}
    base = {"Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": "2025-06-18"}
    with TestClient(app) as c:
        keyed = c.post("/mcp", json=call,
                       headers={**base, "Authorization": f"Bearer {full}"})
        keyless = c.post("/mcp", json=call, headers=base)
    assert keyed.status_code == 200, keyed.text
    result = _sse_json(keyed.text)["result"]
    payload = result.get("structuredContent") or json.loads(result["content"][0]["text"])
    payload = payload.get("result", payload)
    assert payload["connected"] is True
    assert payload["places"][0]["kind"] == "home"
    result = _sse_json(keyless.text)["result"]
    payload = result.get("structuredContent") or json.loads(result["content"][0]["text"])
    assert payload.get("result", payload)["connected"] is False
