"""API keys: format, hashing, resolution with a cached store, the
per-account cap, and the tier table Nic set (free 2,000 a day, pro
10,000 a day)."""

import pytest

from ca_roads import apikeys


def test_key_format_and_parse():
    key_id, secret, full = apikeys.new_key()
    assert full == f"cs_live_{key_id}_{secret}" and len(key_id) == 8
    assert apikeys.parse(full) == (key_id, secret)
    assert apikeys.parse("sk_other_abc") is None
    assert apikeys.parse("cs_live_short_x") is None
    assert apikeys.parse("cs_live_0123abcd") is None  # no secret
    assert apikeys.parse(None) is None


def test_tiers_are_nics_numbers():
    assert apikeys.TIERS["free"]["daily"] == 2000
    assert apikeys.TIERS["pro"]["daily"] == 10000
    assert apikeys.tier_limits("bogus") == apikeys.TIERS["free"]


def test_headers_bearer_or_x_api_key():
    h = {"authorization": "Bearer cs_live_0123abcd_secret"}
    assert apikeys.from_headers(h.get) == "cs_live_0123abcd_secret"
    # A Firebase bearer token is not a key: leave it alone.
    assert apikeys.from_headers({"authorization": "Bearer eyJhbGci"}.get) is None
    assert apikeys.from_headers({"x-api-key": "cs_live_x"}.get) == "cs_live_x"
    assert apikeys.from_headers({}.get) is None


@pytest.mark.asyncio
async def test_create_resolve_revoke_and_cap():
    store = apikeys.MemoryKeyStore()
    full, view = await apikeys.create_key(store, "sam", "Sam@Example.com", "dashboard")
    assert view["tier"] == "free" and view["daily_limit"] == 2000
    assert view["prefix"] == full[: len(view["prefix"])]
    assert "hash" not in view
    rec = await store.get(view["id"])
    assert rec["email"] == "sam@example.com" and rec["hash"] != full

    r = apikeys.KeyResolver(store)
    info = await r.resolve(full)
    assert info == {"id": view["id"], "tier": "free", "uid": "sam"}
    assert (await store.get(view["id"]))["last_used_at"]  # touched once
    wrong = full[:-1] + ("x" if full[-1] != "x" else "y")  # never the real last char
    assert await r.resolve(wrong) is None  # wrong secret
    assert await r.resolve("cs_live_ffffffff_nope") is None  # unknown id

    await store.put(view["id"], {"revoked": True})
    r.forget(view["id"])
    assert await r.resolve(full) is None

    for i in range(apikeys.MAX_KEYS_PER_ACCOUNT):
        await apikeys.create_key(store, "pat", "pat@example.com", f"k{i}")
    with pytest.raises(ValueError):
        await apikeys.create_key(store, "pat", "pat@example.com", "one too many")
    assert len(await store.list_for("pat")) == apikeys.MAX_KEYS_PER_ACCOUNT


@pytest.mark.asyncio
async def test_resolver_caches_reads():
    store = apikeys.MemoryKeyStore()
    full, view = await apikeys.create_key(store, "sam", "sam@example.com", "x")
    reads = []
    orig = store.get

    async def counting_get(key_id):
        reads.append(key_id)
        return await orig(key_id)

    store.get = counting_get
    r = apikeys.KeyResolver(store)
    for _ in range(5):
        assert await r.resolve(full)
    assert len(reads) == 1
