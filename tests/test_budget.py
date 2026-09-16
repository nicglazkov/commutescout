"""Daily budgets: per-client caps on paid endpoints, global upstream
budgets, the per-client daily cap in the rate limiter, and signed
static map URLs."""

import logging

import pytest
import respx
from httpx import Response as HttpxResponse
from starlette.testclient import TestClient

from ca_roads import budget
from ca_roads.budget import DailyCounter
from ca_roads.feeds import tomtom as tomtom_feed
from ca_roads_demo import app as demo_app
from ca_roads_demo import staticmap_sig
from ca_roads_mcp import geocode as geo
from ca_roads_mcp.ratelimit import RateLimiter, RateLimitMiddleware

log = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def _fresh_counters(monkeypatch):
    monkeypatch.setattr(budget, "UPSTREAM", DailyCounter())
    monkeypatch.setattr(geo, "UPSTREAM", budget.UPSTREAM)
    monkeypatch.setattr(tomtom_feed, "UPSTREAM", budget.UPSTREAM)
    monkeypatch.setattr(demo_app, "UPSTREAM", budget.UPSTREAM)
    monkeypatch.setattr(demo_app, "paid_use", DailyCounter())
    monkeypatch.delenv("TELEMETRY_SALT", raising=False)
    monkeypatch.delenv("STATICMAP_SIGNING_KEY", raising=False)


def test_daily_counter_caps_and_rolls(monkeypatch):
    c = DailyCounter()
    c.day = "2026-01-01"
    assert c.allow("k", 2) and c.allow("k", 2) and not c.allow("k", 2)
    assert c.used("k") == 2
    assert c.allow("other", 2)
    # A new UTC day clears everything.
    c.day = "1999-01-01"
    assert c.used("k") == 0
    assert c.allow("k", 2)


def test_daily_counter_bounds_its_keys():
    c = DailyCounter(max_keys=4)
    for i in range(4):
        assert c.allow(f"k{i}", 10)
    assert c.allow("fresh", 10)
    assert len(c.counts) <= 4


async def test_middleware_daily_limit_returns_429():
    seen = []

    async def inner(scope, receive, send):
        seen.append(scope["path"])
        await send({"type": "http.response.start", "status": 200,
                    "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    app = RateLimitMiddleware(inner, RateLimiter(capacity=100,
                                                 refill_per_second=100),
                              daily_limit=2)
    statuses = []

    async def send(msg):
        if msg["type"] == "http.response.start":
            statuses.append(msg["status"])

    async def receive():
        return {"type": "http.request"}

    scope = {"type": "http", "path": "/mcp", "headers": [],
             "client": ("203.0.113.9", 1234)}
    for _ in range(3):
        await app(scope, receive, send)
    assert statuses == [200, 200, 429]
    assert len(seen) == 2


def test_suggest_per_client_daily_cap(monkeypatch):
    monkeypatch.setitem(demo_app.PAID_PER_CLIENT_DAILY, "suggest", 2)
    client = TestClient(demo_app.app)
    r1 = client.get("/api/suggest?q=pasadena")
    r2 = client.get("/api/suggest?q=pasadena")
    r3 = client.get("/api/suggest?q=pasadena")
    assert r1.status_code == 200 and r2.status_code == 200
    assert r3.status_code == 429
    assert r3.headers["Retry-After"] == "3600"
    assert "daily limit" in r3.json()["error"]


@respx.mock
async def test_stadia_geocode_global_budget_skips_the_network(monkeypatch):
    import httpx
    monkeypatch.setenv("STADIA_API_KEY", "test-key")
    monkeypatch.setattr(geo, "STADIA_GEOCODE_DAILY", 1)
    route = respx.get(url__regex=r"https://api\.stadiamaps\.com/geocoding/.*").mock(
        return_value=HttpxResponse(200, json={"features": []}))
    async with httpx.AsyncClient() as client:
        assert await geo._search_stadia(client, "somewhere") == []
        # Budget spent: the next call never leaves the process.
        assert await geo._search_stadia(client, "elsewhere") is None
        assert await geo.stadia_suggest(client, "any", 37.0, -122.0) == []
    assert route.call_count == 1


@respx.mock
async def test_tomtom_flow_global_budget(monkeypatch):
    import httpx
    monkeypatch.setenv("TOMTOM_API_KEY", "tt")
    monkeypatch.setattr(tomtom_feed, "TOMTOM_FLOW_DAILY", 1)
    tomtom_feed._cache.clear()
    route = respx.get(url__regex=r"https://api\.tomtom\.com/.*").mock(
        return_value=HttpxResponse(200, json={"flowSegmentData": {
            "currentSpeed": 50, "freeFlowSpeed": 65}}))
    async with httpx.AsyncClient() as client:
        assert (await tomtom_feed.flow_at_point(client, 37.0, -122.0))["current_mph"] == 50
        assert await tomtom_feed.flow_at_point(client, 38.0, -121.0) is None
    assert route.call_count == 1


def test_staticmap_signature_round_trip(monkeypatch):
    monkeypatch.setenv("STATICMAP_SIGNING_KEY", "k" * 32)
    q = staticmap_sig.query(37.33821, -121.88631, 11, "closure")
    params = dict(p.split("=") for p in q.split("&"))
    assert params["lat"] == "37.3382" and params["s"]
    assert staticmap_sig.verify(params)
    params["lat"] = "37.3383"
    assert not staticmap_sig.verify(params)
    # HTML attribute form uses &amp; and the same signature.
    assert staticmap_sig.query(37.33821, -121.88631, 11, "closure",
                               sep="&amp;").endswith("s=" + params_sig(q))


def params_sig(q: str) -> str:
    return dict(p.split("=") for p in q.split("&"))["s"]


def test_staticmap_endpoint_requires_signature_when_keyed(monkeypatch):
    monkeypatch.setenv("STATICMAP_SIGNING_KEY", "k" * 32)
    monkeypatch.delenv("STADIA_API_KEY", raising=False)
    demo_app._STATICMAP_CACHE.clear()
    client = TestClient(demo_app.app)
    unsigned = client.get("/api/staticmap?lat=37.3382&lon=-121.8863&z=11&k=incident")
    assert unsigned.status_code == 403
    signed = client.get("/api/staticmap?" + staticmap_sig.query(
        37.3382, -121.8863, 11, "incident"))
    assert signed.status_code == 200


def test_staticmap_endpoint_open_without_key():
    demo_app._STATICMAP_CACHE.clear()
    client = TestClient(demo_app.app)
    r = client.get("/api/staticmap?lat=37.3382&lon=-121.8863&z=11&k=incident")
    assert r.status_code == 200
