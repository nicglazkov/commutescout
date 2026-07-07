"""Place-name geocoding via Nominatim (OpenStreetMap).

check_route used to trust the coordinates the calling model recalled for a
place. For cities that works; for landmarks it can be miles off (a request
for Alice's Restaurant once pinned a spot deep in the Saratoga hills). Names
now resolve through a real geocoder, and model-recalled coordinates are the
fallback.

Nominatim usage policy: identify the app, one request per second. The
throttle enforces that, the in-process cache absorbs repeats, results are
sanity-checked against a California-and-borders box, and failures degrade
to the fallback coordinates.
"""

from __future__ import annotations

import asyncio
import time

import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
PHOTON_URL = "https://photon.komoot.io/api/"
USER_AGENT = "ca-roads-mcp/1.1 (github.com/nicglazkov/ca-roads-mcp)"
# lon_min, lat_max, lon_max, lat_min (Nominatim viewbox order)
CALIFORNIA_VIEWBOX = "-124.6,42.1,-114.0,32.4"
TIMEOUT_SECONDS = 6.0
THROTTLE_SECONDS = 1.1  # tests set this to 0

_cache: dict[str, tuple[float, float, str] | None] = {}

# Nominatim's policy is one request per second; the throttle keeps ladder
# retries polite and stops degraded answers under bursts.
_throttle = asyncio.Lock()
_last_request = 0.0

# Corridor endpoints just over the state line; appending ", California" to
# these sends Nominatim hunting for the wrong place.
_BORDER_TOWNS = ("reno", "sparks", "las vegas", "vegas", "carson city",
                 "primm", "stateline", "minden", "gardnerville")


def _plausible(hit: dict) -> bool:
    """Reject matches outside California and its border cities: a
    wrong-state hit is worse than no hit."""
    try:
        lat, lon = float(hit["lat"]), float(hit["lon"])
    except (KeyError, TypeError, ValueError):
        return False
    return 32.0 <= lat <= 42.5 and -125.0 <= lon <= -113.5


async def _search(client: httpx.AsyncClient, q: str, bounded: int) -> list | None:
    global _last_request
    try:
        async with _throttle:
            wait = THROTTLE_SECONDS - (time.monotonic() - _last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            _last_request = time.monotonic()
            resp = await client.get(
                NOMINATIM_URL,
                params={
                    "q": q,
                    "format": "json",
                    "limit": 1,
                    "countrycodes": "us",
                    "viewbox": CALIFORNIA_VIEWBOX,
                    "bounded": bounded,
                },
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT_SECONDS,
            )
        resp.raise_for_status()
        return resp.json()
    except Exception:  # noqa: BLE001 - failure means "use the fallback"
        return None


async def _search_photon(
    client: httpx.AsyncClient, q: str
) -> tuple[float, float, str] | None:
    """Second provider: Photon (Komoot's OSM geocoder). Different infra and
    a fuzzier matcher, so it both survives Nominatim outages and catches
    phrasings Nominatim misses."""
    global _last_request
    try:
        async with _throttle:
            wait = THROTTLE_SECONDS - (time.monotonic() - _last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            _last_request = time.monotonic()
            resp = await client.get(
                PHOTON_URL,
                params={"q": q, "limit": 3, "lat": 37.5, "lon": -120.5},
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT_SECONDS,
            )
        resp.raise_for_status()
        features = resp.json().get("features", [])
        # Two passes: an explicit California match beats a merely-plausible
        # one ("Grapevine" exists in several states and canyons).
        for require_ca in (True, False):
            for feature in features:
                lon, lat = feature["geometry"]["coordinates"][:2]
                if not _plausible({"lat": lat, "lon": lon}):
                    continue
                props = feature.get("properties", {})
                if require_ca and props.get("state") not in ("California", "CA"):
                    continue
                name = ", ".join(
                    str(props[k]) for k in ("name", "city", "state") if props.get(k)
                )
                return float(lat), float(lon), name
        return None
    except Exception:  # noqa: BLE001
        return None


async def geocode(
    client: httpx.AsyncClient, place: str
) -> tuple[float, float, str] | None:
    """Resolve a place name to (lat, lon, display_name), or None.

    Candidate ladder, most-specific first. Appending ", California" makes
    street addresses unambiguous (raw "17288 Skyline Blvd" matches Oakland's
    Skyline Blvd), so it leads, except for border towns like Reno. Then the
    raw query, then trailing-word trims for phrasings OSM names differently
    ("X Caltrain station" resolves as "X").
    """
    query = place.strip()
    if not query:
        return None
    key = query.lower()
    if key in _cache:
        return _cache[key]

    is_border = any(t in key for t in _BORDER_TOWNS)
    ca_ok = "california" not in key and not key.endswith(" ca") and not is_border
    candidates: list[tuple[str, int]] = []
    if ca_ok:
        candidates.append((f"{query}, California", 1))
    candidates.append((query, 1))
    candidates.append((query, 0))
    words = query.split()
    for trims in (1, 2):
        if len(words) - trims >= 1:
            trimmed = " ".join(words[: len(words) - trims])
            candidates.append((f"{trimmed}, California" if ca_ok else trimmed, 0))

    results: list = []
    saw_network_failure = False
    for q, bounded in candidates:
        got = await _search(client, q, bounded)
        if got is None:
            saw_network_failure = True
            continue
        if got and _plausible(got[0]):
            results = got
            break
    if results:
        hit = results[0]
        resolved = (
            float(hit["lat"]), float(hit["lon"]), hit.get("display_name", "")
        )
        _cache[key] = resolved
        return resolved

    # Nominatim came up empty or is unavailable; try Photon.
    photon = await _search_photon(client, query)
    if photon is None and len(words) > 1:
        photon = await _search_photon(client, " ".join(words[:-1]))
    if photon:
        _cache[key] = photon
        return photon
    if not saw_network_failure:
        _cache[key] = None  # definitive miss; network trouble retries later
    return None
