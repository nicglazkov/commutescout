"""Process vitals: one INFO line every ten minutes with the resident
set size and the in-process cache sizes, so the daily memory-limit
kill has a time series behind it."""

import asyncio
import json
import logging
import sys

import pytest

from ca_roads_demo import roadsnap, vitals


def test_snapshot_reports_caches_and_rss():
    roadsnap._mem["k"] = None
    got = vitals.snapshot()
    for key in ("rss_mb", "snaps_mem", "snap_queue", "mapdata_cache",
                "staticmap_cache", "tile_cache", "states_cache"):
        assert key in got, key
    assert got["snaps_mem"] >= 1
    if sys.platform.startswith("linux"):
        assert got["rss_mb"] and got["rss_mb"] > 10
    else:
        assert got["rss_mb"] is None or got["rss_mb"] > 0


async def test_run_logs_one_json_line_per_tick(monkeypatch, caplog):
    ticks: list[float] = []

    async def fake_sleep(seconds):
        ticks.append(seconds)
        if len(ticks) == 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(vitals, "_sleep", fake_sleep)
    with caplog.at_level(logging.INFO, logger="vitals"):
        with pytest.raises(asyncio.CancelledError):
            await vitals.run()
    lines = [r.getMessage() for r in caplog.records if r.name == "vitals"]
    assert len(lines) == 2
    parsed = json.loads(lines[0].split(" ", 1)[1])
    assert parsed["log_type"] == "vitals" and "snaps_mem" in parsed
    assert ticks == [vitals.INTERVAL, vitals.INTERVAL]
