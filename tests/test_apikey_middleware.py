"""ApiKeyMiddleware: keyless passes through to the address limiter, a
valid key is limited by its tier with RateLimit headers, a bad key is a
401 envelope, a spent day is a 429 with Retry-After."""

import json
import logging

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from ca_roads import apikeys
from ca_roads_mcp.ratelimit import ApiKeyMiddleware, RateLimitMiddleware


async def ok(request):
    keyed = (request.scope.get("state") or {}).get("api_key")
    return JSONResponse({"ok": True, "key": keyed["id"] if keyed else None})


@pytest.fixture
def stack():
    store = apikeys.MemoryKeyStore()
    inner = RateLimitMiddleware(Starlette(routes=[Route("/v1/tools/x", ok)]), daily_limit=2)
    mw = ApiKeyMiddleware(inner, resolver=apikeys.KeyResolver(store))
    return store, mw, TestClient(mw)


def test_keyless_requests_still_use_the_address_limits(stack):
    _, _, c = stack
    assert c.get("/v1/tools/x").json() == {"ok": True, "key": None}
    assert c.get("/v1/tools/x").status_code == 200
    assert c.get("/v1/tools/x").status_code == 429  # the inner daily_limit=2


@pytest.mark.asyncio
async def test_keyed_requests_are_limited_by_tier_not_address(stack):
    store, mw, c = stack
    full, view = await apikeys.create_key(store, "sam", "sam@example.com", "t")
    h = {"Authorization": f"Bearer {full}"}
    r = c.get("/v1/tools/x", headers=h)
    assert r.status_code == 200 and r.json()["key"] == view["id"]
    assert r.headers["ratelimit-limit"] == "2000"
    assert r.headers["ratelimit-remaining"] == "1999"
    # Far past the address limit that keyless clients hit.
    for _ in range(5):
        assert c.get("/v1/tools/x", headers={"X-API-Key": full}).status_code == 200
    assert c.get("/v1/tools/x", headers=h).headers["ratelimit-remaining"] == "1993"


@pytest.mark.asyncio
async def test_bad_or_revoked_keys_are_401_never_keyless(stack):
    store, mw, c = stack
    r = c.get("/v1/tools/x", headers={"X-API-Key": "cs_live_deadbeef_nope"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_key"
    assert "Settings" in r.json()["error"]["hint"]
    full, view = await apikeys.create_key(store, "sam", "sam@example.com", "t")
    await store.put(view["id"], {"revoked": True})
    r = c.get("/v1/tools/x", headers={"X-API-Key": full})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_spent_day_and_burst_answer_429(stack, monkeypatch):
    store, mw, c = stack
    full, view = await apikeys.create_key(store, "sam", "sam@example.com", "t")
    monkeypatch.setitem(apikeys.TIERS, "free", {"daily": 2, "burst": 2, "per_second": 0})
    h = {"X-API-Key": full}
    assert c.get("/v1/tools/x", headers=h).status_code == 200
    assert c.get("/v1/tools/x", headers=h).status_code == 200
    r = c.get("/v1/tools/x", headers=h)
    assert r.status_code == 429
    assert r.json()["error"]["code"] in ("daily_limit", "rate_limited")
    assert r.headers["retry-after"] in ("2", "3600")


@pytest.mark.asyncio
async def test_every_keyed_request_logs_one_metering_line(stack, caplog):
    store, mw, c = stack
    full, view = await apikeys.create_key(store, "sam", "sam@example.com", "t")
    with caplog.at_level(logging.INFO, logger="ca_roads.apikeys"):
        c.get("/v1/tools/x", headers={"X-API-Key": full})
    lines = [json.loads(r.message) for r in caplog.records if r.name == "ca_roads.apikeys"]
    assert lines and lines[-1]["log_type"] == "api_use"
    assert lines[-1]["key"] == view["id"] and lines[-1]["status"] == 200


def test_store_outage_is_a_503_not_a_free_pass():
    class Broken:
        async def get(self, key_id):
            raise RuntimeError("firestore down")

    mw = ApiKeyMiddleware(Starlette(routes=[Route("/v1/tools/x", ok)]),
                          resolver=apikeys.KeyResolver(Broken()))
    r = TestClient(mw).get("/v1/tools/x", headers={"X-API-Key": "cs_live_deadbeef_x"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "keys_unavailable"
