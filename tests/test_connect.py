"""Setup instructions an agent can follow: /llms.txt and the server card
on both hosts, rendered from ca_roads_mcp/connect.py, and the site's
/mcp page fed by the same data."""

import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from ca_roads_demo import app as demo_app
from ca_roads_mcp import connect, server

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def mcp_client():
    with TestClient(server.mcp.streamable_http_app(stateless_http=True)) as c:
        yield c


def test_guide_names_every_client_and_the_endpoint():
    text = connect.guide()
    assert text.startswith("# CommuteScout\n\n> ")
    assert connect.ENDPOINT in text
    for client in connect.CLIENTS:
        assert f"### {client['name']}" in text
    # Every tool the server registers is listed by name.
    for tool in server.mcp._tool_manager.list_tools():
        assert f"`{tool.name}`" in text, tool.name


def test_every_client_has_runnable_steps():
    ids = [c["id"] for c in connect.CLIENTS]
    assert len(ids) == len(set(ids))
    for client in connect.CLIENTS:
        assert client["steps"], client["id"]
        assert any(connect.ENDPOINT in (s.get("code") or s.get("text") or "")
                   for s in client["steps"]), client["id"]


def test_site_json_matches_the_source():
    committed = json.loads((REPO / "site" / "lib" / "mcp-clients.json").read_text("utf-8"))
    assert committed == json.loads(json.dumps(connect.clients_json())), (
        "run scripts/gen_api_reference.py")
    page = (REPO / "site" / "app" / "mcp" / "page.tsx").read_text("utf-8")
    assert "@/lib/mcp-clients.json" in page and 'id="connect"' in page


def test_server_card_matches_server_json():
    reg = json.loads((REPO / "server.json").read_text("utf-8"))
    card = connect.server_card(reg["version"])
    assert card["name"] == reg["name"]
    assert card["remotes"][0]["url"] == reg["remotes"][0]["url"] == connect.ENDPOINT
    assert card["remotes"][0]["authentication"]["required"] is False


@pytest.mark.parametrize("path", ["/", "/llms.txt"])
def test_mcp_host_serves_the_guide(mcp_client, path):
    r = mcp_client.get(path)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert connect.ENDPOINT in r.text and "### Claude Code" in r.text


@pytest.mark.parametrize("path", ["/.well-known/mcp/server-card.json", "/.well-known/mcp.json"])
def test_mcp_host_serves_the_card(mcp_client, path):
    r = mcp_client.get(path)
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "*"
    assert r.json()["remotes"][0]["url"] == connect.ENDPOINT


def test_mcp_host_openapi_alias(mcp_client):
    assert mcp_client.get("/openapi.json").json() == mcp_client.get("/v1/openapi.json").json()


def test_site_serves_the_guide_and_card():
    c = TestClient(demo_app.app)
    r = c.get("/llms.txt")
    assert r.status_code == 200 and connect.ENDPOINT in r.text
    card = c.get("/.well-known/mcp.json")
    assert card.status_code == 200 and card.json()["name"] == "io.github.nicglazkov/commutescout"
    assert "llms.txt" in c.get("/robots.txt").text
