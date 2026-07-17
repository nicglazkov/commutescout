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


async def test_expired_serves_stale_then_refreshes():
    """Stale-while-revalidate: an expired-but-servable key returns the cached
    value immediately (never awaiting the refresh) and updates in the
    background."""
    cache = TTLCache()
    calls = 0

    async def fetch():
        nonlocal calls
        calls += 1
        return f"v{calls}"

    first = await cache.get("k", ttl_seconds=0, max_serve_seconds=300, fetch=fetch)
    assert first.value == "v1" and calls == 1 and not first.stale

    # ttl=0 -> already expired, but within max_serve: serve v1 now, refresh async.
    second = await cache.get("k", ttl_seconds=0, max_serve_seconds=300, fetch=fetch)
    assert second.served and second.value == "v1" and not second.stale

    await cache._drain()
    assert calls == 2  # the refresh ran off the caller's path

    third = await cache.get("k", ttl_seconds=0, max_serve_seconds=300, fetch=fetch)
    assert third.value == "v2"  # now serving the refreshed value
    await cache._drain()


async def test_failed_refresh_keeps_serving_and_flags_stale():
    """When the background refresh fails, the last good value keeps being served
    and is flagged stale with the error."""
    cache = TTLCache()
    state = {"fail": False}

    async def fetch():
        if state["fail"]:
            raise RuntimeError("down")
        return "good"

    await cache.get("k", ttl_seconds=0, max_serve_seconds=300, fetch=fetch)  # cold -> good

    state["fail"] = True
    # First expired serve returns cached "good" immediately; failure not known yet.
    first = await cache.get("k", ttl_seconds=0, max_serve_seconds=300, fetch=fetch)
    assert first.served and first.value == "good" and not first.stale

    await cache._drain()  # background refresh fails and records the error

    second = await cache.get("k", ttl_seconds=0, max_serve_seconds=300, fetch=fetch)
    assert second.served and second.value == "good"
    assert second.stale and "down" in second.error
    await cache._drain()


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
