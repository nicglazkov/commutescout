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
async def test_keys_on_one_account_share_the_day(stack, monkeypatch):
    store, mw, c = stack
    monkeypatch.setitem(apikeys.TIERS, "free", {"daily": 3, "burst": 10, "per_second": 1})
    first, _ = await apikeys.create_key(store, "sam", "sam@example.com", "a")
    second, _ = await apikeys.create_key(store, "sam", "sam@example.com", "b")
    other, _ = await apikeys.create_key(store, "pat", "pat@example.com", "c")
    for full in (first, first, second):
        assert c.get("/v1/tools/x", headers={"X-API-Key": full}).status_code == 200
    r = c.get("/v1/tools/x", headers={"X-API-Key": second})
    assert r.status_code == 429 and r.json()["error"]["code"] == "daily_limit"
    assert c.get("/v1/tools/x", headers={"X-API-Key": other}).status_code == 200


@pytest.mark.asyncio
async def test_every_keyed_request_logs_one_metering_line(stack, caplog):
    store, mw, c = stack
    full, view = await apikeys.create_key(store, "sam", "sam@example.com", "t")
    with caplog.at_level(logging.INFO, logger="ca_roads.apikeys"):
        c.get("/v1/tools/x", headers={"X-API-Key": full})
    lines = [json.loads(r.message) for r in caplog.records if r.name == "ca_roads.apikeys"]
    assert lines and lines[-1]["log_type"] == "api_use"
    assert lines[-1]["key"] == view["id"] and lines[-1]["status"] == 200


def test_guessing_keys_is_capped_per_address_before_any_lookup():
    """A bad key skips the address limiter (it is answered here), so a
    fresh random key per request used to cost one store read each with
    no ceiling. Past a small budget the address gets a 429 unlooked-up."""
    lookups = []

    class Counting(apikeys.MemoryKeyStore):
        async def get(self, key_id):
            lookups.append(key_id)
            return await super().get(key_id)

    mw = ApiKeyMiddleware(Starlette(routes=[Route("/v1/tools/x", ok)]),
                          resolver=apikeys.KeyResolver(Counting()))
    c = TestClient(mw)
    codes = [c.get("/v1/tools/x",
                   headers={"X-API-Key": f"cs_live_{i:08x}_nope"}).status_code
             for i in range(40)]
    assert codes[0] == 401
    assert codes[-1] == 429
    assert len(lookups) <= 15
    # Keyless calls from that address are not this limiter's business.
    assert c.get("/v1/tools/x").status_code == 200


def test_store_outage_is_a_503_not_a_free_pass():
    class Broken:
        async def get(self, key_id):
            raise RuntimeError("firestore down")

    mw = ApiKeyMiddleware(Starlette(routes=[Route("/v1/tools/x", ok)]),
                          resolver=apikeys.KeyResolver(Broken()))
    r = TestClient(mw).get("/v1/tools/x", headers={"X-API-Key": "cs_live_deadbeef_x"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "keys_unavailable"


@pytest.mark.asyncio
async def test_usage_is_mirrored_for_the_account_page(stack, monkeypatch):
    import asyncio
    store, mw, c = stack
    full, _ = await apikeys.create_key(store, "sam", "sam@example.com", "t")
    mw.usage.flush_s = 0
    for _ in range(3):
        assert c.get("/v1/tools/x", headers={"X-API-Key": full}).status_code == 200
    for _ in range(20):
        if (store.usage.get("sam") or {}).get("requests") == 3:
            break
        await asyncio.sleep(0.01)
    rec = await store.get_usage("sam")
    assert rec["limit"] == 2000 and rec["tier"] == "free" and rec["updated_at"]
    assert rec["requests"] >= 1


@pytest.mark.asyncio
async def test_usage_mirror_throttles_and_keeps_the_latest():
    import asyncio
    store = apikeys.MemoryKeyStore()
    mirror = apikeys.UsageMirror(lambda: store, flush_s=0.05)
    mirror.note("sam", "2026-10-29", 1, 2000, "free")
    await asyncio.sleep(0.01)
    assert store.usage["sam"]["requests"] == 1
    mirror.note("sam", "2026-10-29", 2, 2000, "free")
    mirror.note("sam", "2026-10-29", 3, 2000, "free")
    assert store.usage["sam"]["requests"] == 1      # inside the window
    await asyncio.sleep(0.1)
    assert store.usage["sam"]["requests"] == 3      # one write, the latest
