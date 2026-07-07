"""Place-name geocoding via Nominatim (OpenStreetMap).

check_route used to trust the coordinates the calling model recalled for a
place. For cities that works; for landmarks it can be miles off (a request
for Alice's Restaurant once pinned a spot deep in the Saratoga hills). Names
now resolve through a real geocoder, and model-recalled coordinates are the
fallback.

Nominatim usage policy: identify the app, stay near 1 request/second. The
in-process cache absorbs repeats, every result is bounded to California, and
failures degrade to the fallback coordinates.
"""

from __future__ import annotations

import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "ca-roads-mcp/1.1 (github.com/nicglazkov/ca-roads-mcp)"
# lon_min, lat_max, lon_max, lat_min (Nominatim viewbox order)
CALIFORNIA_VIEWBOX = "-124.6,42.1,-114.0,32.4"
TIMEOUT_SECONDS = 6.0

_cache: dict[str, tuple[float, float, str] | None] = {}


async def geocode(
    client: httpx.AsyncClient, place: str
) -> tuple[float, float, str] | None:
    """Resolve a place name to (lat, lon, display_name), or None.

    Bounded to California. Cached for the process lifetime (place names
    don't move).
    """
    query = place.strip()
    if not query:
        return None
    key = query.lower()
    if key in _cache:
        return _cache[key]
    if "california" not in key and not key.endswith(" ca"):
        query += ", California"
    try:
        resp = await client.get(
            NOMINATIM_URL,
            params={
                "q": query,
                "format": "json",
                "limit": 1,
                "countrycodes": "us",
                "viewbox": CALIFORNIA_VIEWBOX,
                "bounded": 1,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        results = resp.json()
    except Exception:  # noqa: BLE001 - any failure means "use the fallback"
        return None
    if not results:
        _cache[key] = None
        return None
    hit = results[0]
    resolved = (float(hit["lat"]), float(hit["lon"]), hit.get("display_name", ""))
    _cache[key] = resolved
    return resolved
