"""Connection-pool self-healing: detection, reset, worker survival."""

import asyncio

import httpx
import pytest

from ca_roads.roaddata import RoadData
from ca_roads_demo import states


async def test_reset_client_swaps_every_source():
    rd = RoadData()
    old = rd.client
    new = rd.reset_client()
    assert new is not old
    for src in (rd.chp, rd.lcs, rd.chains, rd.wildfires_source,
                rd.calfire_source, rd.cms, rd.cctv, rd.rwis):
        assert src._client is new
    await asyncio.sleep(0)  # let the background close task run
    await rd.aclose()


async def test_pooltimeout_burst_triggers_reset(monkeypatch):
    calls = []

    class FakeRoad:
        def reset_client(self):
            calls.append(1)

    from ca_roads_mcp import server as tools
    monkeypatch.setattr(tools, "get_road", lambda: FakeRoad())
    monkeypatch.setattr(states, "_POOL_ERRORS", [])

    async def starved():
        raise httpx.PoolTimeout("pool exhausted")

    capped = states._capped(starved, 5.0)
    for _ in range(states._POOL_ERROR_LIMIT - 1):
        with pytest.raises(httpx.PoolTimeout):
            await capped()
    assert not calls  # below the burst threshold: no reset yet
    with pytest.raises(httpx.PoolTimeout):
        await capped()
    assert calls == [1]  # threshold hit: pool swapped once
    # Counter cleared: the next single timeout does not re-trigger.
    with pytest.raises(httpx.PoolTimeout):
        await capped()
    assert calls == [1]


async def test_other_errors_do_not_touch_the_pool(monkeypatch):
    calls = []

    class FakeRoad:
        def reset_client(self):
            calls.append(1)

    from ca_roads_mcp import server as tools
    monkeypatch.setattr(tools, "get_road", lambda: FakeRoad())
    monkeypatch.setattr(states, "_POOL_ERRORS", [])

    async def down():
        raise httpx.ConnectError("upstream down")

    capped = states._capped(down, 5.0)
    for _ in range(states._POOL_ERROR_LIMIT + 2):
        with pytest.raises(httpx.ConnectError):
            await capped()
    assert not calls
