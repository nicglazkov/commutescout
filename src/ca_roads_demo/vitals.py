"""Process vitals on a timer.

The demo runs at 80-95% of its memory limit and gets killed about once
a day, and nothing in the logs says what holds the memory. One INFO
line every ten minutes with the resident set size and the sizes of the
in-process caches turns that into a time series in Cloud Logging, so
the next memory decision is measured instead of guessed.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import tracemalloc

log = logging.getLogger("vitals")

INTERVAL = 600
# Set VITALS_TRACEMALLOC=1 to add the top allocation sites to each line.
# tracemalloc costs memory and CPU, so it is a switch for a day of
# diagnosis, not a default: RSS was measured climbing ~120 MB an hour
# between restarts with every counted cache flat.
#
# Tracing starts TRACE_AFTER_S into the run, not at import. tracemalloc
# only tracks allocations made while it is on, and its overhead is
# proportional to what it tracks. Started at boot it tracked the whole
# working set, and the instance went over its memory limit three
# minutes after starting, three times in ten minutes (2026-09-25).
# Started after boot has settled it tracks only the growth, which is
# the only part anyone wants to see.
TRACE = os.environ.get("VITALS_TRACEMALLOC", "").strip() == "1"
TRACE_AFTER_S = float(os.environ.get("VITALS_TRACE_AFTER_S", "1800"))
# Injectable so tests can drive the loop without wall-clock waits.
_sleep = asyncio.sleep
_started = time.monotonic()


def rss_mb() -> float | None:
    """Current resident set size in MB, or None where /proc is absent."""
    try:
        with open("/proc/self/statm", encoding="ascii") as fh:
            pages = int(fh.read().split()[1])
        return round(pages * os.sysconf("SC_PAGE_SIZE") / 1e6, 1)
    except (OSError, ValueError, IndexError, AttributeError):
        return None


def snapshot() -> dict:
    """Sizes of every cache that lives for the life of the process."""
    # Local imports: app imports this module at load time.
    from ca_roads_demo import app, roadsnap, states

    out = {
        "log_type": "vitals",
        "uptime_min": round((time.monotonic() - _started) / 60, 1),
        "rss_mb": rss_mb(),
        "snaps_mem": len(roadsnap._mem),
        "snap_queue": len(roadsnap._queue),
        "mapdata_cache": len(app._MAPDATA_CACHE),
        "mapdata_cache_mb": round(app._mapdata_cache_bytes() / 1_048_576, 1),
        "staticmap_cache": len(app._STATICMAP_CACHE),
        "tile_cache": len(app._TILE_CACHE),
        "flow_cache": len(app._FLOW_CACHE),
        "perim_cache": len(app._PERIM_CACHE),
        "states_cache": len(states._cache._entries),
    }
    if TRACE and tracemalloc.is_tracing():
        current, peak = tracemalloc.get_traced_memory()
        stats = tracemalloc.take_snapshot().statistics("filename")[:8]
        out["traced_mb"] = round(current / 1e6, 1)
        out["traced_peak_mb"] = round(peak / 1e6, 1)
        out["top_alloc"] = [
            {"file": os.sep.join(s.traceback[0].filename.split(os.sep)[-3:]),
             "mb": round(s.size / 1e6, 1), "n": s.count}
            for s in stats]
    return out


async def run() -> None:
    """Log vitals forever; started from the app lifespan."""
    while True:
        await _sleep(INTERVAL)
        if (TRACE and not tracemalloc.is_tracing()
                and time.monotonic() - _started >= TRACE_AFTER_S):
            tracemalloc.start(1)
            log.info("vitals: tracing allocations from here on")
        try:
            log.info("vitals %s", json.dumps(snapshot(), sort_keys=True))
        except Exception as exc:  # noqa: BLE001 - never let vitals kill the loop
            log.warning("vitals failed: %s", type(exc).__name__)
