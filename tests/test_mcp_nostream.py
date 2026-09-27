"""The MCP endpoint refuses the idle GET stream a stateless server can
never use, and leaves every other request alone."""

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from ca_roads_mcp.nostream import NoIdleStream


def _app():
    reached = []

    async def endpoint(request):
        reached.append((request.method, request.url.path))
        return JSONResponse({"ok": True})

    inner = Starlette(routes=[Route("/mcp", endpoint, methods=["GET", "POST", "DELETE"]),
                              Route("/v1/tools/{name}", endpoint)])
    return NoIdleStream(inner), reached


def test_a_get_on_the_endpoint_is_405_and_never_reaches_the_server():
    app, reached = _app()
    c = TestClient(app)
    for path in ("/mcp", "/mcp/"):
        r = c.get(path, headers={"accept": "text/event-stream"})
        assert r.status_code == 405
        assert r.headers["allow"] == "POST"
    assert reached == []


def test_posts_and_the_rest_bridge_pass_through():
    app, reached = _app()
    c = TestClient(app)
    assert c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"}).status_code == 200
    assert c.get("/v1/tools/road_conditions").status_code == 200
    assert reached == [("POST", "/mcp"), ("GET", "/v1/tools/road_conditions")]


def test_the_real_server_app_refuses_the_stream():
    from ca_roads_mcp.server import mcp

    r = TestClient(NoIdleStream(mcp.streamable_http_app())).get(
        "/mcp", headers={"accept": "text/event-stream"})
    assert r.status_code == 405
