"""The REST bridge: every MCP tool as GET /v1/tools/{name}, an OpenAPI
document generated from the same schemas, one error envelope, CORS."""

import pytest
from starlette.testclient import TestClient
from tests.test_mcp_live_fixes import INC, FakeRoad

from ca_roads_mcp import server
from ca_roads_mcp.rest import PREFIX, openapi, tool_specs


@pytest.fixture(scope="module")
def client():
    # One client for the module: the context manager runs the app
    # lifespan, which the MCP session manager needs before it answers
    # on /mcp, and that manager can only be started once per instance.
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(server, "get_road", lambda: FakeRoad(incidents=[INC]))
        server.mcp.settings.stateless_http = True
        with TestClient(server.mcp.streamable_http_app()) as c:
            yield c


def test_every_tool_has_a_route_and_the_index_lists_them(client):
    names = [s["name"] for s in tool_specs(server.mcp)]
    assert len(names) == 10 and "check_route" in names and "get_nearby_events" in names
    r = client.get(PREFIX)
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "*"
    assert [t["name"] for t in r.json()["tools"]] == names
    assert r.json()["mcp"].endswith("/mcp")


def test_a_tool_answers_with_its_json(client):
    r = client.get(f"{PREFIX}/tools/get_incidents", params={"area": "Redwood City"})
    assert r.status_code == 200, r.text
    assert r.headers["access-control-allow-origin"] == "*"
    assert r.headers["cache-control"] == "no-store"
    body = r.json()
    assert body["count"] == 1 and body["incidents"][0]["id"] == INC.id


def test_query_strings_coerce_like_json(client):
    r = client.get(f"{PREFIX}/tools/get_incidents",
                   params={"center": "37.48,-122.14", "radius_km": "5"})
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 1


def test_error_envelope_for_missing_unknown_and_invalid(client):
    r = client.get(f"{PREFIX}/tools/check_route", params={"from_place": "Sacramento"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "missing_parameter"
    assert "to_place" in r.json()["error"]["message"]

    r = client.get(f"{PREFIX}/tools/get_incidents", params={"zone": "x"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "unknown_parameter"
    assert "area" in r.json()["error"]["hint"]

    r = client.get(f"{PREFIX}/tools/get_incidents", params={"radius_km": "wide"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_parameter"
    assert r.json()["error"]["message"].startswith("radius_km")

    r = client.get(f"{PREFIX}/tools/no_such_tool")
    assert r.status_code == 404 and r.json()["error"]["code"] == "unknown_tool"


def test_semantic_errors_are_400_in_the_one_envelope(client):
    # A malformed center or a bad radius is the caller's mistake: a 400
    # in the documented envelope, never a 200 that reads as "nothing near".
    r = client.get(f"{PREFIX}/tools/get_incidents", params={"center": "nowhere"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_parameter"
    assert "center" in r.json()["error"]["message"]
    r = client.get(f"{PREFIX}/tools/get_incidents",
                   params={"center": "37.3,-121.9", "radius_km": "-5"})
    assert r.status_code == 400 and "radius_km" in r.json()["error"]["message"]
    r = client.get(f"{PREFIX}/tools/get_incidents", params={"center": "200,999"})
    assert r.status_code == 400


def test_openapi_is_generated_from_the_tool_schemas(client):
    doc = openapi(server.mcp)
    assert doc["openapi"].startswith("3.1")
    assert len(doc["paths"]) == 10
    op = doc["paths"][f"{PREFIX}/tools/check_route"]["get"]
    params = {p["name"]: p for p in op["parameters"]}
    assert params["from_place"]["required"] is True
    assert params["from_coords"]["required"] is False
    assert params["from_coords"]["schema"] == {"type": "string", "default": None}
    assert op["responses"]["429"]["$ref"].endswith("RateLimited")
    r = client.get(f"{PREFIX}/openapi.json")
    assert r.status_code == 200 and r.json()["paths"] == doc["paths"]
    assert client.get(f"{PREFIX}/docs").status_code == 200
    assert "openapi.json" in client.get(f"{PREFIX}/docs").text


def test_preflight_is_answered(client):
    r = client.options(f"{PREFIX}/tools/get_incidents")
    assert r.status_code == 204
    assert "GET" in r.headers["access-control-allow-methods"]


def test_mcp_transport_still_mounted(client):
    # The bridge is additive: the MCP endpoint keeps answering.
    r = client.get("/mcp", headers={"Accept": "application/json"})
    # 421 is the SDK's host check under the test client; main() turns it off.
    assert r.status_code in (400, 405, 406, 421)
