"""Place-name geocoding via Stadia Maps (Pelias).

check_route used to trust the coordinates the calling model recalled for a
place. For cities that works; for landmarks it can be miles off (a request
for Alice's Restaurant once pinned a spot deep in the Saratoga hills). Names
now resolve through a real geocoder, and model-recalled coordinates are the
fallback.

The offline gazetteer stays the primary resolver; only its misses reach
the network. Stadia is keyed by env STADIA_API_KEY; without one (dev, CI,
self-hosters) the module is gazetteer-only and misses fall through to the
caller's fallback coordinates without being cached as definitive.
"""

from __future__ import annotations

import asyncio
import csv
import os
import re
from collections import OrderedDict
from importlib.resources import files

import httpx

STADIA_SEARCH_URL = "https://api.stadiamaps.com/geocoding/v1/search"
STADIA_AUTOCOMPLETE_URL = "https://api.stadiamaps.com/geocoding/v1/autocomplete"
try:
    from importlib.metadata import version as _pkg_version
    _VERSION = _pkg_version("ca-roads-mcp")
except Exception:  # noqa: BLE001 - not installed (e.g. source checkout)
    _VERSION = "dev"
USER_AGENT = f"ca-roads-mcp/{_VERSION} (github.com/nicglazkov/ca-roads-mcp)"
# California and its border towns: lon_min, lat_min, lon_max, lat_max.
_RECT = (-124.6, 32.4, -114.0, 42.1)
TIMEOUT_SECONDS = 6.0


def _api_key() -> str:
    return os.environ.get("STADIA_API_KEY", "").strip()


def _rect_params() -> dict:
    return {
        "boundary.country": "US",
        "boundary.rect.min_lon": _RECT[0],
        "boundary.rect.min_lat": _RECT[1],
        "boundary.rect.max_lon": _RECT[2],
        "boundary.rect.max_lat": _RECT[3],
    }

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

# Corridor endpoints just over the state line; appending ", California" to
# these sends the geocoder hunting for the wrong place.
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


async def _search_stadia(
    client: httpx.AsyncClient,
    q: str,
    near: tuple[float, float] | None = None,
    limit: int = 1,
) -> list[tuple[float, float, str]] | None:
    """Stadia (Pelias) search inside the California rectangle.

    Returns (lat, lon, label) hits, [] for a clean miss, or None for
    network trouble or a missing key (callers must not cache None-shaped
    results as definitive misses)."""
    key = _api_key()
    if not key:
        return None
    params = {"text": q, "size": limit, "api_key": key, **_rect_params()}
    if near:
        params["focus.point.lat"], params["focus.point.lon"] = near
    try:
        resp = await client.get(
            STADIA_SEARCH_URL, params=params,
            headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
        features = resp.json().get("features", [])
    except Exception:  # noqa: BLE001 - failure means "use the fallback"
        return None
    # Fuzzy-match guard, kept from the Photon era: a house-number query
    # once returned an entirely unrelated street, and a locality
    # qualifier can match by itself ("Riverside Drive, San Jose"
    # matching "San Jose Drive, San Jacinto"). Require the FIRST
    # significant token - the street or place name itself - in the hit.
    significant = [
        t for t in _norm(q).split() if len(t) >= 4 and not t.isdigit()
    ]
    tokens = set(significant[:1])
    out: list[tuple[float, float, str]] = []
    for f in features:
        coords = (f.get("geometry") or {}).get("coordinates") or []
        if len(coords) < 2:
            continue
        lon, lat = coords[:2]
        if not _plausible({"lat": lat, "lon": lon}):
            continue
        props = f.get("properties", {})
        label = props.get("label") or props.get("name") or ""
        if tokens and not any(t in _norm(label) for t in tokens):
            continue
        out.append((float(lat), float(lon), label))
    return out


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

    # Network ladder for non-place-name queries (addresses, landmarks).
    # The gazetteer already handled locality-style fallbacks.
    is_border = any(t in key for t in _BORDER_TOWNS)
    ca_ok = "california" not in key and not key.endswith(" ca") and not is_border
    candidates: list[str] = []
    if ca_ok:
        candidates.append(f"{query}, California")
    candidates.append(query)
    words = query.split()
    # Trailing-word trim for phrasings the geocoder names differently
    # ("X Caltrain station" resolves as "X").
    if len(words) > 1:
        candidates.append(" ".join(words[:-1]))

    saw_network_failure = False
    for q in candidates:
        got = await _search_stadia(client, q)
        if got is None:
            saw_network_failure = True
            continue
        if got:
            _cache_put(key, got[0])
            return got[0]
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

    Gazetteer hits are single-answer by construction. The search runs
    biased toward `near` (the trip origin) so the match by the user
    beats the one importance ranking would bury under a big city's
    street. Results dedupe within 2 km, nearest first.
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
    raw = list(await _search_stadia(client, q, near=near, limit=limit) or [])
    # The ", California" suffix can mislead Pelias into matching the
    # state itself (the token guard filters those hits away). The raw
    # query catches the venue or street the suffix hid.
    if ca_ok:
        raw.extend(
            await _search_stadia(client, query, near=near, limit=limit) or [])

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


# ── Autocomplete (search-as-you-type) ───────────────────────────────────────
# Per-keystroke lookups go gazetteer first (instant, offline), then
# Stadia's autocomplete endpoint (prefix search with location bias),
# with a small concurrency cap so a burst of keystrokes cannot pile up.
# The precise search ladder still validates whatever the user finally
# picks or types.

_suggest_sem = asyncio.Semaphore(4)


def gazetteer_suggest(q: str, limit: int = 3) -> list[dict]:
    """Instant offline prefix matches against the CA place table."""
    table = _load_gazetteer()
    nq = _norm(q)
    if not nq:
        return []
    starts, contains = [], []
    for key, (lat, lon, display) in table.items():
        entry = {"name": display, "lat": lat, "lon": lon, "kind": "city"}
        if key.startswith(nq):
            starts.append((len(key), key, entry))
        elif any(w.startswith(nq) for w in key.split()):
            contains.append((len(key), key, entry))
    # Shorter names first: "san jo" should suggest San Jose before San
    # Joaquin. Population data would be better; length is a decent proxy
    # for the famous place and costs nothing.
    starts.sort(key=lambda t: (t[0], t[1]))
    contains.sort(key=lambda t: (t[0], t[1]))
    return [e for _, _, e in (starts + contains)[:limit]]


# The geocoder prefix-matches literally, so "kestrel rd" can miss
# "Kestrel Road"; expand common abbreviations before the request.
_ABBREV = {
    "rd": "road", "st": "street", "ave": "avenue", "av": "avenue",
    "blvd": "boulevard", "dr": "drive", "hwy": "highway", "ln": "lane",
    "ct": "court", "pkwy": "parkway", "expy": "expressway",
}


def _expand_abbrev(q: str) -> str:
    words = q.split()
    return " ".join(_ABBREV.get(w.lower().rstrip("."), w) for w in words)


async def stadia_suggest(
    client: httpx.AsyncClient,
    q: str,
    bias_lat: float,
    bias_lon: float,
    limit: int = 6,
) -> list[dict]:
    key = _api_key()
    if not key:
        return []
    q = _expand_abbrev(q)
    try:
        async with _suggest_sem:
            resp = await client.get(
                STADIA_AUTOCOMPLETE_URL,
                params={
                    "text": q, "size": limit, "api_key": key,
                    "focus.point.lat": bias_lat,
                    "focus.point.lon": bias_lon,
                    **_rect_params(),
                },
                headers={"User-Agent": USER_AGENT},
                timeout=4.0,
            )
        resp.raise_for_status()
        out = []
        number_match = re.match(r"^(\d+[a-zA-Z]?)\s+(.+)", q)
        for feature in resp.json().get("features", []):
            lon, lat = feature["geometry"]["coordinates"][:2]
            if not _plausible({"lat": lat, "lon": lon}):
                continue
            props = feature.get("properties", {})
            primary = props.get("name") or " ".join(
                str(x) for x in (props.get("housenumber"), props.get("street"))
                if x
            )
            if not primary:
                continue
            approx = False
            # When the exact house number is not in the data, the
            # geocoder answers with the street itself and the typed
            # number silently disappears. Keep it: label the row
            # "<number> <Street>" and mark it approximate so selection
            # can interpolate a precise position.
            if (
                number_match
                and not props.get("housenumber")
                and props.get("layer") == "street"
                and _norm(number_match.group(2)).split()[0] in _norm(primary)
            ):
                primary = number_match.group(1) + " " + primary
                approx = True
            secondary = ", ".join(
                str(props[k]) for k in ("locality", "region_a")
                if props.get(k)
            )
            entry = {
                "name": primary + (", " + secondary if secondary else ""),
                "lat": float(lat), "lon": float(lon),
                "kind": props.get("layer") or "place",
            }
            if approx:
                entry["approx"] = True
            out.append(entry)
        # Rank rows that actually contain the typed street/place word
        # above fuzzy fallbacks; the fallbacks stay visible but sink to
        # the bottom of the list.
        tokens = [t for t in _norm(q).split() if len(t) >= 4 and not t.isdigit()]
        if tokens:
            out.sort(key=lambda s: 0 if tokens[0] in _norm(s["name"]) else 1)
        return out
    except Exception:  # noqa: BLE001 - suggestions degrade to gazetteer only
        return []
