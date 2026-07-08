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
import csv
import re
import time
from collections import OrderedDict
from importlib.resources import files

import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
PHOTON_URL = "https://photon.komoot.io/api/"
try:
    from importlib.metadata import version as _pkg_version
    _VERSION = _pkg_version("ca-roads-mcp")
except Exception:  # noqa: BLE001 - not installed (e.g. source checkout)
    _VERSION = "dev"
USER_AGENT = f"ca-roads-mcp/{_VERSION} (github.com/nicglazkov/ca-roads-mcp)"
# lon_min, lat_max, lon_max, lat_min (Nominatim viewbox order)
CALIFORNIA_VIEWBOX = "-124.6,42.1,-114.0,32.4"
TIMEOUT_SECONDS = 6.0
THROTTLE_SECONDS = 1.1  # tests set this to 0

_CACHE_MAX = 4096
_cache: OrderedDict[str, tuple[float, float, str] | None] = OrderedDict()


def _cache_put(key: str, value) -> None:
    _cache[key] = value
    _cache.move_to_end(key)
    while len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)


# ── Offline gazetteer ────────────────────────────────────────────────────────
# ~1,600 California cities/towns/CDPs from the Census 2024 place gazetteer
# (plus the Nevada border towns the corridors end at). Known places resolve
# with zero network calls; the external geocoders only see the misses.

_gazetteer: dict[str, tuple[float, float, str]] | None = None
_NOISE_RE = re.compile(r"[^a-z0-9 ]")


def _norm(text: str) -> str:
    return " ".join(_NOISE_RE.sub(" ", text.lower()).split())


def _load_gazetteer() -> dict[str, tuple[float, float, str]]:
    global _gazetteer
    if _gazetteer is None:
        table = {}
        data = files("ca_roads_mcp").joinpath("data/ca_places.csv").read_text(
            encoding="utf-8"
        )
        nevada = {"reno", "sparks", "carson city", "stateline", "minden",
                  "gardnerville", "las vegas", "primm"}
        for row in csv.DictReader(data.splitlines()):
            state = "Nevada" if _norm(row["name"]) in nevada else "California"
            table[_norm(row["name"])] = (
                float(row["lat"]), float(row["lon"]), f"{row['name']}, {state}"
            )
        _gazetteer = table
    return _gazetteer


# Suffix words the gazetteer may absorb when trimming. Anything else
# ("airport", "station", "boardwalk") is a point of interest whose real
# location differs from the city center - those go to the network geocoders.
_ABSORBABLE = {"downtown", "area", "city"}


def gazetteer_lookup(place: str) -> tuple[float, float, str] | None:
    """Offline place resolution: exact name, or a name plus generic suffix
    words ("Truckee downtown" -> Truckee). POI-style queries miss on purpose."""
    table = _load_gazetteer()
    normalized = _norm(place)
    for suffix in (" california", " ca"):
        normalized = normalized.removesuffix(suffix)
    words = normalized.split()
    dropped: list[str] = []
    while words:
        hit = table.get(" ".join(words))
        if hit and all(w in _ABSORBABLE for w in dropped):
            return hit
        dropped.insert(0, words[-1])
        words = words[:-1]
    return None

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


async def _search(
    client: httpx.AsyncClient, q: str, bounded: int, limit: int = 1
) -> list | None:
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
                    "limit": limit,
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
    """Second provider, best single hit. See _photon_hits."""
    hits = await _photon_hits(client, q)
    return hits[0] if hits else None


async def _photon_hits(
    client: httpx.AsyncClient,
    q: str,
    near: tuple[float, float] | None = None,
    limit: int = 3,
) -> list[tuple[float, float, str]]:
    """Photon (Komoot's OSM geocoder). Different infra and a fuzzier
    matcher than Nominatim, so it survives Nominatim outages, catches
    phrasings Nominatim misses, and its lat/lon bias surfaces the match
    NEAR the user that Nominatim's importance ranking buries."""
    global _last_request
    bias_lat, bias_lon = near or (37.5, -120.5)
    try:
        async with _throttle:
            wait = THROTTLE_SECONDS - (time.monotonic() - _last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            _last_request = time.monotonic()
            resp = await client.get(
                PHOTON_URL,
                params={"q": q, "limit": limit,
                        "lat": bias_lat, "lon": bias_lon},
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT_SECONDS,
            )
        resp.raise_for_status()
        features = resp.json().get("features", [])
        # Photon fuzzy-matches aggressively: a house-number query once
        # returned an entirely unrelated street, and a locality qualifier
        # can match by itself ("Riverside Drive, San Jose" matched "San
        # Jose Drive, San Jacinto"). Require the FIRST significant token -
        # the street or place name itself - to appear in the hit.
        significant = [
            t for t in _norm(q).split() if len(t) >= 4 and not t.isdigit()
        ]
        tokens = set(significant[:1])
        # Two passes: an explicit California match beats a merely-plausible
        # one ("Grapevine" exists in several states and canyons).
        out: list[tuple[float, float, str]] = []
        for require_ca in (True, False):
            for feature in features:
                lon, lat = feature["geometry"]["coordinates"][:2]
                if not _plausible({"lat": lat, "lon": lon}):
                    continue
                props = feature.get("properties", {})
                if require_ca and props.get("state") not in ("California", "CA"):
                    continue
                hit_text = _norm(" ".join(
                    str(props.get(k) or "")
                    for k in ("name", "street", "city", "district")
                ))
                if tokens and not any(t in hit_text for t in tokens):
                    continue
                name = ", ".join(
                    str(props[k])
                    for k in ("name", "street", "city", "state")
                    if props.get(k)
                )
                out.append((float(lat), float(lon), name))
            if out:
                return out
        return out
    except Exception:  # noqa: BLE001
        return []


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
        _cache.move_to_end(key)
        return _cache[key]

    offline = gazetteer_lookup(query)
    if offline:
        _cache_put(key, offline)
        return offline

    # Network ladder for non-place-name queries (addresses, landmarks),
    # trimmed to two Nominatim candidates; Photon is the cross-provider
    # fallback. The gazetteer already handled locality-style fallbacks.
    is_border = any(t in key for t in _BORDER_TOWNS)
    ca_ok = "california" not in key and not key.endswith(" ca") and not is_border
    candidates: list[tuple[str, int]] = []
    if ca_ok:
        candidates.append((f"{query}, California", 1))
    candidates.append((query, 0))
    words = query.split()

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
        _cache_put(key, resolved)
        return resolved

    # Nominatim came up empty or is unavailable; try Photon.
    photon = await _search_photon(client, query)
    if photon is None and len(words) > 1:
        photon = await _search_photon(client, " ".join(words[:-1]))
    if photon:
        _cache_put(key, photon)
        return photon
    if not saw_network_failure:
        _cache_put(key, None)  # definitive miss; network trouble retries later
    return None


async def geocode_candidates(
    client: httpx.AsyncClient,
    place: str,
    limit: int = 4,
    near: tuple[float, float] | None = None,
) -> list[tuple[float, float, str]]:
    """Like geocode(), but returns the distinct plausible matches so the
    caller can detect ambiguity ("Main St" exists in half the state).

    Gazetteer hits are single-answer by construction. Nominatim supplies
    the importance-ranked matches; Photon, biased toward `near` (the trip
    origin), supplies the match by the user that importance ranking buries
    under a big city's street. Results dedupe within 2 km, nearest first.
    """
    query = place.strip()
    if not query:
        return []
    offline = gazetteer_lookup(query)
    if offline:
        return [offline]

    key = query.lower()
    is_border = any(t in key for t in _BORDER_TOWNS)
    ca_ok = "california" not in key and not key.endswith(" ca") and not is_border
    q = f"{query}, California" if ca_ok else query
    raw: list[tuple[float, float, str]] = []
    got = await _search(client, q, bounded=0, limit=limit)
    for hit in got or []:
        if _plausible(hit):
            raw.append((
                float(hit["lat"]), float(hit["lon"]),
                hit.get("display_name", ""),
            ))
    raw.extend(await _photon_hits(client, query, near=near))

    distinct: list[tuple[float, float, str]] = []
    for cand in raw:
        if all(
            _rough_km(cand[0], cand[1], d[0], d[1]) > 2 for d in distinct
        ):
            distinct.append(cand)
    if near:
        distinct.sort(key=lambda c: _rough_km(c[0], c[1], near[0], near[1]))
    return distinct[:limit]


def _rough_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Equirectangular approximation; fine at disambiguation scales."""
    import math

    x = (lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    return 111.32 * math.hypot(lat2 - lat1, x)
