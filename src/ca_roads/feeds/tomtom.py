"""TomTom traffic flow: actual current speeds versus free-flow.

Activated by the TOMTOM_API_KEY environment variable; without it every
call returns None and route reports simply omit the traffic section. The
flow-segment endpoint answers for a single point, so callers sample a few
points along a corridor; results cache for a minute per rounded point.
Free tier: 2,500 requests/day, plenty at this project's scale.
"""

from __future__ import annotations

import os
import time

import httpx

FLOW_URL = (
    "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
)
TIMEOUT_SECONDS = 8.0
TTL_SECONDS = 60.0

_cache: dict[tuple[float, float], tuple[float, dict | None]] = {}


def api_key() -> str | None:
    return os.environ.get("TOMTOM_API_KEY") or None


async def flow_at_point(
    client: httpx.AsyncClient, lat: float, lon: float
) -> dict | None:
    key = api_key()
    if not key:
        return None
    cache_key = (round(lat, 2), round(lon, 2))
    now = time.monotonic()
    cached = _cache.get(cache_key)
    if cached and now - cached[0] < TTL_SECONDS:
        return cached[1]
    try:
        resp = await client.get(
            FLOW_URL,
            params={"point": f"{lat},{lon}", "unit": "MPH", "key": key},
            timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        seg = resp.json().get("flowSegmentData") or {}
        value = {
            "current_mph": seg.get("currentSpeed"),
            "freeflow_mph": seg.get("freeFlowSpeed"),
            "confidence": seg.get("confidence"),
            "closed": bool(seg.get("roadClosure")),
        }
    except Exception:  # noqa: BLE001 - context source, never fatal
        value = None
    _cache[cache_key] = (now, value)
    return value


def summarize(samples: list[dict]) -> dict | None:
    """Aggregate point samples into one traffic verdict."""
    usable = [
        s for s in samples
        if s and s.get("current_mph") and s.get("freeflow_mph")
    ]
    if not usable:
        return None
    ratios = [s["current_mph"] / s["freeflow_mph"] for s in usable]
    worst_i = min(range(len(usable)), key=lambda i: ratios[i])
    return {
        "sampled_points": len(usable),
        "avg_current_mph": round(
            sum(s["current_mph"] for s in usable) / len(usable)
        ),
        "avg_freeflow_mph": round(
            sum(s["freeflow_mph"] for s in usable) / len(usable)
        ),
        "worst_point": {
            "current_mph": usable[worst_i]["current_mph"],
            "freeflow_mph": usable[worst_i]["freeflow_mph"],
        },
        "flowing_freely": min(ratios) > 0.75,
    }
