"""The API host answers with the same hardening headers as the site."""

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from ca_roads_mcp.headers import DATA_CSP, HTML_CSP, SecurityHeaders


def _app():
    async def data(_):
        return JSONResponse({"ok": True})

    async def page(_):
        return HTMLResponse("<html><body>docs</body></html>")

    return SecurityHeaders(Starlette(routes=[Route("/data", data), Route("/docs", page)]))


def test_json_gets_a_policy_that_allows_nothing():
    r = TestClient(_app()).get("/data")
    assert r.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["content-security-policy"] == DATA_CSP.decode()


def test_the_reference_page_gets_the_policy_redoc_needs():
    r = TestClient(_app()).get("/docs")
    csp = r.headers["content-security-policy"]
    assert csp == HTML_CSP.decode()
    assert "https://cdn.jsdelivr.net" in csp and "worker-src blob:" in csp
    assert r.headers["strict-transport-security"].startswith("max-age=31536000")
