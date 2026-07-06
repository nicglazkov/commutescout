import pytest

from ca_roads.cache import TTLCache


async def test_fresh_hit_skips_fetch():
    cache = TTLCache()
    calls = 0

    async def fetch():
        nonlocal calls
        calls += 1
        return calls

    first = await cache.get("k", ttl_seconds=60, max_serve_seconds=300, fetch=fetch)
    second = await cache.get("k", ttl_seconds=60, max_serve_seconds=300, fetch=fetch)
    assert first.value == 1
    assert second.value == 1
    assert calls == 1
    assert not second.stale


async def test_stale_serve_on_failure():
    cache = TTLCache()

    async def ok():
        return "good"

    async def boom():
        raise RuntimeError("down")

    await cache.get("k", ttl_seconds=0, max_serve_seconds=300, fetch=ok)
    outcome = await cache.get("k", ttl_seconds=0, max_serve_seconds=300, fetch=boom)
    assert outcome.served
    assert outcome.stale
    assert outcome.value == "good"
    assert "down" in outcome.error


async def test_failure_without_cache():
    cache = TTLCache()

    async def boom():
        raise RuntimeError("down")

    outcome = await cache.get("k", ttl_seconds=60, max_serve_seconds=300, fetch=boom)
    assert not outcome.served
    assert outcome.value is None
    assert "down" in outcome.error


async def test_stale_beyond_max_serve_is_failure():
    cache = TTLCache()

    async def ok():
        return "good"

    async def boom():
        raise RuntimeError("down")

    await cache.get("k", ttl_seconds=0, max_serve_seconds=0, fetch=ok)
    outcome = await cache.get("k", ttl_seconds=0, max_serve_seconds=-1, fetch=boom)
    assert not outcome.served


@pytest.mark.parametrize("keys", [("a", "b")])
async def test_keys_are_independent(keys):
    cache = TTLCache()

    async def make(v):
        async def fetch():
            return v

        return fetch

    a = await cache.get(keys[0], 60, 300, await make("A"))
    b = await cache.get(keys[1], 60, 300, await make("B"))
    assert a.value == "A"
    assert b.value == "B"
