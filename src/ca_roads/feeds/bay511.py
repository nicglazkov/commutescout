"""511 SF Bay traffic events. Activated by BAY511_API_KEY; without it,
Bay Area reports simply omit the section. Defensive parsing: the 511 API
shape is stable but this is a context source, so anything unexpected
degrades to an empty list.
"""

from __future__ import annotations

import os
import time

import httpx

EVENTS_URL = "https://api.511.org/traffic/events"
TIMEOUT_SECONDS = 12.0
TTL_SECONDS = 180.0

_cache: tuple[float, list[dict]] | None = None


def api_key() -> str | None:
    return os.environ.get("BAY511_API_KEY") or None


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
            params={"api_key": key, "format": "json"},
            timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        # 511 serves JSON with a UTF-8 BOM.
        payload = resp.content.decode("utf-8-sig")
        import json

        parsed = json.loads(payload)
        out = []
        for event in parsed.get("events", []):
            roads = [
                r.get("name", "")
                for r in event.get("roads", [])
                if isinstance(r, dict)
            ]
            out.append({
                "headline": (event.get("headline") or "")[:160],
                "type": event.get("event_type"),
                "severity": event.get("severity"),
                "roads": [r for r in roads if r][:3],
                "updated": event.get("updated"),
            })
    except Exception:  # noqa: BLE001 - context source, never fatal
        return _cache[1] if _cache else []
    _cache = (now, out)
    return out
