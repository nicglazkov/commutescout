"""The hosted stack (server.hosted_app) requires a key on the data
surfaces, /mcp and /v1/tools/*, and leaves discovery open: the setup
guide, server card, OpenAPI (the uptime check), the tool index and
CORS preflights. First-party products never call this service (the map,
watch pages and apps go through commutescout.com, which runs the tools
in process), so nothing of ours needs a key here."""

import pytest
from starlette.testclient import TestClient

from ca_roads import apikeys
from ca_roads_mcp import server

MCP_HEADERS = {"Accept": "application/json, text/event-stream",
               "Content-Type": "application/json",
               "MCP-Protocol-Version": "2025-06-18"}
INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
    "protocolVersion": "2025-06-18", "capabilities": {},
    "clientInfo": {"name": "test", "version": "0"}}}


@pytest.fixture
def store(monkeypatch):
    store = apikeys.MemoryKeyStore()
    monkeypatch.setattr(apikeys, "_store", store)
    return store


@pytest.fixture
def client(store, monkeypatch):
    monkeypatch.delenv("MCP_REQUIRE_KEY", raising=False)
    with TestClient(server.hosted_app()) as c:
        yield c


def test_keyless_mcp_is_401(client):
    r = client.post("/mcp", json=INIT, headers=MCP_HEADERS)
    assert r.status_code == 401
    assert r.json()["error"]["data"]["code"] == "missing_key"
    assert "https://commutescout.com/map" in r.json()["error"]["message"]


def test_keyless_rest_tool_is_401(client):
    r = client.get("/v1/tools/get_coverage")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "missing_key"
    assert r.headers["access-control-allow-origin"] == "*"


@pytest.mark.parametrize("path", ["/", "/llms.txt", "/robots.txt", "/openapi.json",
                                  "/v1/openapi.json", "/v1", "/v1/tools", "/v1/docs",
                                  "/.well-known/mcp.json",
                                  "/.well-known/mcp/server-card.json"])
def test_discovery_is_open(client, path):
    assert client.get(path).status_code == 200


def test_preflight_is_open(client):
    r = client.options("/v1/tools/get_coverage", headers={
        "Origin": "https://example.com", "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "x-api-key"})
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_keyed_calls_work(client, store):
    full, _ = await apikeys.create_key(store, "sam", "sam@example.com", "t")
    r = client.get("/v1/tools/get_coverage", headers={"X-API-Key": full})
    assert r.status_code == 200, r.text
    assert r.headers["ratelimit-limit"] == "2000"
    r = client.post("/mcp", json=INIT,
                    headers={**MCP_HEADERS, "Authorization": f"Bearer {full}"})
    assert r.status_code == 200, r.text


def test_self_hosting_can_turn_the_requirement_off(store, monkeypatch):
    monkeypatch.setenv("MCP_REQUIRE_KEY", "0")
    with TestClient(server.hosted_app()) as c:
        r = c.post("/mcp", json=INIT, headers=MCP_HEADERS)
    assert r.status_code == 200, r.text
