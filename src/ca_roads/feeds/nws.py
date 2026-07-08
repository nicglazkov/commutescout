"""National Weather Service alerts, queried by point.

Zone-based alerts cover huge areas; resolving zone polygons costs a request
per zone. Querying api.weather.gov/alerts/active?point= per sampled corridor
point is bounded (a route needs 3 points) and returns exactly the alerts a
driver there is under. Points are rounded before caching so nearby queries
share entries. Failures return empty: weather context must never break a
road report.
"""

from __future__ import annotations

import time

import httpx

USER_AGENT = "ca-roads-mcp (github.com/nicglazkov/ca-roads-mcp)"
ALERTS_URL = "https://api.weather.gov/alerts/active"
TIMEOUT_SECONDS = 10.0
TTL_SECONDS = 300.0

# Alert types that matter to a driver; everything else (beach hazards,
# air quality) is noise in a road report.
ROAD_EVENTS = (
    "winter", "snow", "blizzard", "ice", "freez", "wind", "dust", "flood",
    "fire weather", "red flag", "fog", "storm", "heat", "avalanche",
)

_cache: dict[tuple[float, float], tuple[float, list[dict]]] = {}


def _road_relevant(event: str) -> bool:
    lowered = event.lower()
    return any(k in lowered for k in ROAD_EVENTS)


async def alerts_at_points(
    client: httpx.AsyncClient, points: list[tuple[float, float]]
) -> list[dict]:
    """Active road-relevant alerts covering any of the given points,
    deduplicated by alert id."""
    seen: dict[str, dict] = {}
    now = time.monotonic()
    rounded = {(round(lat, 1), round(lon, 1)) for lat, lon in points}
    for point in sorted(rounded):
        cached = _cache.get(point)
        if cached and now - cached[0] < TTL_SECONDS:
            features = cached[1]
        else:
            try:
                resp = await client.get(
                    ALERTS_URL,
                    params={"point": f"{point[0]},{point[1]}"},
                    headers={"User-Agent": USER_AGENT},
                    timeout=TIMEOUT_SECONDS,
                )
                resp.raise_for_status()
                features = resp.json().get("features", [])
                _cache[point] = (now, features)
            except Exception:  # noqa: BLE001 - context source, never fatal
                continue
        for feature in features:
            props = feature.get("properties") or {}
            if not _road_relevant(props.get("event", "")):
                continue
            alert_id = feature.get("id") or props.get("id", "")
            if alert_id in seen:
                continue
            seen[alert_id] = {
                "event": props.get("event"),
                "severity": props.get("severity"),
                "headline": props.get("headline"),
                "areas": (props.get("areaDesc") or "")[:160],
                "ends": props.get("ends") or props.get("expires"),
            }
    return list(seen.values())
