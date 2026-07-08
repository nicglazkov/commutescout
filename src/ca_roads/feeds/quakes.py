"""Recent significant earthquakes near California, from the USGS FDSN API.

Only quakes big enough to plausibly matter to a road report (M4.5+ in the
last 24 hours) are returned; most days that is an empty list. Failures
return empty: this is context, never a reason to fail a report.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import httpx

USER_AGENT = "ca-roads-mcp (github.com/nicglazkov/ca-roads-mcp)"
QUERY_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
TIMEOUT_SECONDS = 10.0
TTL_SECONDS = 300.0
MIN_MAGNITUDE = 4.5

_cache: tuple[float, list[dict]] | None = None


async def recent_significant(client: httpx.AsyncClient) -> list[dict]:
    global _cache
    now = time.monotonic()
    if _cache and now - _cache[0] < TTL_SECONDS:
        return _cache[1]
    start = (datetime.now(UTC) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
    try:
        resp = await client.get(
            QUERY_URL,
            params={
                "format": "geojson",
                "minmagnitude": MIN_MAGNITUDE,
                "starttime": start,
                "minlatitude": 32.0, "maxlatitude": 42.5,
                "minlongitude": -125.0, "maxlongitude": -114.0,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        quakes = []
        for feature in resp.json().get("features", []):
            props = feature.get("properties") or {}
            coords = (feature.get("geometry") or {}).get("coordinates") or []
            if len(coords) < 2:
                continue
            quakes.append({
                "magnitude": props.get("mag"),
                "place": props.get("place"),
                "lat": coords[1],
                "lon": coords[0],
                "time": props.get("time"),
            })
    except Exception:  # noqa: BLE001 - context source, never fatal
        return _cache[1] if _cache else []
    _cache = (now, quakes)
    return quakes
