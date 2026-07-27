"""Cold-instance warm-up: budgeted map responses and warm progress."""

import asyncio

import pytest

from ca_roads.cache import TTLCache
from ca_roads_demo import states

WORLD = (-85.0, -180.0, 85.0, 180.0)


@pytest.fixture
def registries(monkeypatch):
    """Two fake keyless states on a fresh cache: one instant, one slow."""
    monkeypatch.setattr(states, "_cache", TTLCache())
    monkeypatch.setattr(states, "NEC_STATES", {})
    monkeypatch.setattr(states, "WZDX_FEEDS", {})
    monkeypatch.setattr(states, "KEYED_STATES", {})
    monkeypatch.setattr(states, "TOLL_SOURCES", {})
    monkeypatch.setattr(states, "_PREWARM_DONE", False)

    async def fast(client):
        return {"markers": [{"kind": "incident", "lat": 40.0, "lon": -100.0,
                             "src": "FastDOT"}]}

    async def slow(client):
        await asyncio.sleep(0.6)
        return {"markers": [{"kind": "incident", "lat": 41.0, "lon": -101.0,
                             "src": "SlowDOT"}]}

    monkeypatch.setattr(states, "KEYLESS_STATES", {
        "fast": ("Faststate", (39.0, -101.0, 41.5, -99.0), fast),
        "slow": ("Slowstate", (40.0, -102.0, 42.0, -100.0), slow),
    })


async def test_budget_serves_ready_feeds_and_backfills(registries):
    want = {"incident"}
    # Budgeted call on a cold cache: the instant feed answers, the slow
    # one is dropped from this response but keeps fetching.
    out = await states.markers_for_bbox(None, WORLD, want,
                                        budget_seconds=0.15)
    assert [m["src"] for m in out] == ["FastDOT"]
    ready, total = states.warm_progress()
    assert (ready, total) == (1, 2)
    # Once the background lookup lands, the next poll has everything.
    await asyncio.gather(*list(states._PENDING_LOOKUPS),
                         return_exceptions=True)
    out = await states.markers_for_bbox(None, WORLD, want,
                                        budget_seconds=0.15)
    assert {m["src"] for m in out} == {"FastDOT", "SlowDOT"}
    assert states.warm_progress() == (2, 2)


async def test_unbudgeted_call_waits_for_everything(registries):
    out = await states.markers_for_bbox(None, WORLD, {"incident"})
    assert {m["src"] for m in out} == {"FastDOT", "SlowDOT"}


async def test_default_budget_bounds_the_request_path(registries,
                                                      monkeypatch):
    # Without an explicit budget the default still applies: a wedged
    # feed cannot hold the map payload hostage.
    monkeypatch.setattr(states, "DEFAULT_BUDGET_SECONDS", 0.15)
    out = await states.markers_for_bbox(None, WORLD, {"incident"})
    assert [m["src"] for m in out] == ["FastDOT"]


async def test_capped_fetch_times_out_dripping_upstream():
    async def drip():
        await asyncio.sleep(5)
        return {"markers": []}

    capped = states._capped(drip, 0.1)
    with pytest.raises(asyncio.TimeoutError):
        await capped()


async def test_prewarm_done_ends_warmup_despite_failures(registries,
                                                         monkeypatch):
    # A feed that never succeeds must not keep warm-up open forever:
    # after the boot prewarm finishes, progress reports complete.
    assert states.warm_progress() == (0, 2)
    monkeypatch.setattr(states, "_PREWARM_DONE", True)
    assert states.warm_progress() == (2, 2)


async def test_prewarm_sets_done_flag_even_on_failure(registries,
                                                      monkeypatch):
    async def boom(client):
        raise RuntimeError("upstream down")

    monkeypatch.setattr(states, "_prewarm_all", boom)
    await states.prewarm(None)
    assert states._PREWARM_DONE is True
