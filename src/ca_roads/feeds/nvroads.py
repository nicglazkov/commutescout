"""Nevada DOT events for corridor continuations past the state line
(Reno, Tahoe's east shore, Las Vegas). Activated by NVROADS_API_KEY;
without it, reports omit the Nevada section.

NV Roads runs the common CARS REST API. The parser is defensive: this
integration is marked experimental until verified against a real key,
and any surprise in the shape degrades to an empty list.
"""

from __future__ import annotations

import os
import time

import httpx

EVENTS_URL = "https://goto.nvroads.com/api/v2/get/event"
TIMEOUT_SECONDS = 12.0
TTL_SECONDS = 180.0

_cache: tuple[float, list[dict]] | None = None


def api_key() -> str | None:
    return os.environ.get("NVROADS_API_KEY") or None


async def events(client: httpx.AsyncClient) -> list[dict]:
    global _cache
    key = api_key()
    if not key:
        return []
    now = time.monotonic()
    if _cache and now - _cache[0] < TTL_SECONDS:
        return _cache[1]
    try:
        resp = await client.get(
            EVENTS_URL,
            params={"key": key, "format": "json"},
            timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        out = []
        for event in resp.json():
            if not isinstance(event, dict):
                continue
            out.append({
                "road": event.get("RoadwayName") or event.get("Roadway"),
                "direction": event.get("DirectionOfTravel"),
                "description": (event.get("Description") or "")[:200],
                "type": event.get("EventType"),
                "full_closure": bool(event.get("IsFullClosure")),
                "lat": event.get("Latitude"),
                "lon": event.get("Longitude"),
            })
    except Exception:  # noqa: BLE001 - context source, never fatal
        return _cache[1] if _cache else []
    _cache = (now, out)
    return out
