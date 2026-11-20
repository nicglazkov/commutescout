"""Personal connector links: /mcp/<key> and /mcp?key= become an ordinary
keyed /mcp request, the key never reaches the path the logs see, and
anything else passes through untouched."""

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from ca_roads import apikeys
from ca_roads_mcp.keyurl import KeyInUrl, key_from_scope
from ca_roads_mcp.ratelimit import ApiKeyMiddleware

KEY = "cs_live_0123abcd_" + "A" * 32


async def echo(request):
    keyed = (request.scope.get("state") or {}).get("api_key")
    return JSONResponse({"path": request.url.path, "query": request.url.query,
                         "auth": request.headers.get("authorization"),
                         "key": keyed["id"] if keyed else None})


def test_key_from_path_and_query():
    assert key_from_scope({"path": f"/mcp/{KEY}"}) == (KEY, "/mcp", b"")
    assert key_from_scope({"path": f"/mcp/{KEY}/"})[0] == KEY
    k, path, q = key_from_scope({"path": "/mcp", "query_string": f"a=1&key={KEY}".encode()})
    assert (k, path, q) == (KEY, "/mcp", b"a=1")
    # Not a key, or not the MCP path: untouched.
    assert key_from_scope({"path": "/mcp/other"})[0] is None
    assert key_from_scope({"path": f"/v1/tools/x/{KEY}"})[0] is None
    assert key_from_scope({"path": "/mcp", "query_string": b"key=nope"})[0] is None


@pytest.mark.asyncio
async def test_personal_link_is_a_keyed_request():
    store = apikeys.MemoryKeyStore()
    full, view = await apikeys.create_key(store, "sam", "sam@example.com", "t")
    inner = Starlette(routes=[Route("/mcp", echo, methods=["GET", "POST"])])
    app = KeyInUrl(ApiKeyMiddleware(inner, resolver=apikeys.KeyResolver(store),
                                    require_key=True))
    c = TestClient(app)
    r = c.post(f"/mcp/{full}")
    assert r.status_code == 200
    body = r.json()
    assert body["path"] == "/mcp" and body["key"] == view["id"]
    assert full not in body["query"]
    r = c.post(f"/mcp?key={full}")
    assert r.status_code == 200 and r.json()["key"] == view["id"]
    # A header the client sent wins over the link.
    other, _ = await apikeys.create_key(store, "kim", "kim@example.com", "t")
    r = c.post(f"/mcp/{full}", headers={"Authorization": f"Bearer {other}"})
    assert r.json()["auth"] == f"Bearer {other}"
    # A revoked or made-up key in the link is a 401, never keyless.
    assert c.post(f"/mcp/{KEY}").status_code == 401
    assert c.post("/mcp").status_code == 401
