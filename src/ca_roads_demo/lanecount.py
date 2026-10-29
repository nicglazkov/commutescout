"""How many lanes a road has at a point, from OpenStreetMap.

CHP logs say which lane ("#2 LN") but never how wide the road is, and
some closure feeds leave the count out. Without a count there is no
lane drawing, so this module asks OpenStreetMap's Overpass API for the
road ways near the point and reads their ``lanes`` and ``hov:lanes``
tags.

Lookups never run on a request: ``known()`` reads the cache only and
``want()`` queues a point for a background worker that drains the
queue at a polite pace under a daily cap. Results are cached by
rounded location and direction for a month (roads rarely change
width); misses for a day.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import time
from collections import OrderedDict

from ca_roads import lanes
from ca_roads.budget import UPSTREAM
from ca_roads_mcp.serialize import direction_hint

log = logging.getLogger("lanecount")

OVERPASS_URL = os.environ.get("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
USER_AGENT = "commutescout.com lane lookup (https://commutescout.com)"
# Overpass asks for no more than about 10,000 queries a day and a
# couple at a time; one at a time under this cap stays well inside it.
DAILY_CAP = int(os.environ.get("OVERPASS_LANES_DAILY", "1500"))
PACE_SECONDS = 1.5
HIT_TTL = 30 * 86400
MISS_TTL = 86400
CACHE_MAX = 20_000
QUEUE_MAX = 500
# CHP pins an incident at the nearest cross street or ramp, often a
# block off the freeway itself, so freeways are searched wider than
# surface streets (where a block over is another road).
RADIUS_M = 150
MAX_DIST_M = {"motorway": 150, "trunk": 150}
SURFACE_DIST_M = 60

_ROADS = "^(motorway|trunk|primary|secondary|tertiary)$"
_HEADINGS = {"N": 0.0, "E": 90.0, "S": 180.0, "W": 270.0}

# key -> (stored_at, (total, types) | None)
_cache: OrderedDict[tuple, tuple[float, tuple | None]] = OrderedDict()
_queue: OrderedDict[tuple, tuple[float, float, str | None]] = OrderedDict()
_worker_task = None
_sleep = asyncio.sleep


def heading_letter(direction: str | None) -> str | None:
    """'NB', 'northbound', 'N' -> 'N'; anything else -> None."""
    d = (direction or "").strip().upper()
    return d[0] if d[:1] in _HEADINGS else None


def _key(lat: float, lon: float, direction: str | None) -> tuple:
    return (round(lat, 3), round(lon, 3), heading_letter(direction))


def known(lat: float | None, lon: float | None, direction: str | None = None):
    """(total, types) from the cache, or None. Never does I/O."""
    if lat is None or lon is None:
        return None
    hit = _cache.get(_key(lat, lon, direction))
    if not hit:
        return None
    stored, value = hit
    if time.time() - stored > (HIT_TTL if value else MISS_TTL):
        return None
    return value


def want(lat: float | None, lon: float | None, direction: str | None = None) -> None:
    """Queue a lookup unless the cache already has a fresh answer."""
    if lat is None or lon is None:
        return
    k = _key(lat, lon, direction)
    hit = _cache.get(k)
    if hit and time.time() - hit[0] <= (HIT_TTL if hit[1] else MISS_TTL):
        return
    if k in _queue:
        return
    _queue[k] = (lat, lon, direction)
    while len(_queue) > QUEUE_MAX:
        _queue.popitem(last=False)


def _store(k: tuple, value) -> None:
    _cache[k] = (time.time(), value)
    _cache.move_to_end(k)
    while len(_cache) > CACHE_MAX:
        _cache.popitem(last=False)


def _meters(lat1, lon1, lat2, lon2) -> float:
    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = math.radians(lat2 - lat1)
    return 6_371_000 * math.hypot(x, y)


def _bearing(lat1, lon1, lat2, lon2) -> float:
    y = math.sin(math.radians(lon2 - lon1)) * math.cos(math.radians(lat2))
    x = (math.cos(math.radians(lat1)) * math.sin(math.radians(lat2))
         - math.sin(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.cos(math.radians(lon2 - lon1)))
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def _angle(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


def _nearest_segment(geom, lat, lon):
    """(distance m, bearing of that segment in way order) or None."""
    pts = [p for p in geom or [] if p and "lat" in p and "lon" in p]
    best = None
    for a, b in zip(pts, pts[1:], strict=False):
        # Distance to the segment, on a local flat projection.
        kx = math.cos(math.radians(lat))
        ax, ay = (a["lon"] - lon) * kx, a["lat"] - lat
        bx, by = (b["lon"] - lon) * kx, b["lat"] - lat
        dx, dy = bx - ax, by - ay
        t = 0.0
        if dx or dy:
            t = max(0.0, min(1.0, -(ax * dx + ay * dy) / (dx * dx + dy * dy)))
        px, py = ax + t * dx, ay + t * dy
        dist = math.hypot(px, py) * 111_195
        if best is None or dist < best[0]:
            best = (dist, _bearing(a["lat"], a["lon"], b["lat"], b["lon"]))
    return best


def _int(raw) -> int | None:
    try:
        n = int(str(raw).split(";")[0].strip())
    except (TypeError, ValueError):
        return None
    return n if 1 <= n <= 12 else None


def _hov_types(raw: str | None, total: int) -> dict[int, str]:
    """'designated|yes|yes' -> {1: 'hov'}: lanes are listed left to
    right in the way's direction."""
    if not raw:
        return {}
    parts = raw.split("|")
    if len(parts) != total:
        return {}
    return {i + 1: "hov" for i, p in enumerate(parts) if p.strip() in ("designated", "lane")}


def pick(elements, lat: float, lon: float, direction: str | None = None):
    """(total, types) for the way at the point heading ``direction``,
    from Overpass ``out tags geom`` elements, or None."""
    want_heading = _HEADINGS.get(heading_letter(direction) or "")
    choices = []
    for el in elements or []:
        tags = el.get("tags") or {}
        if el.get("type") != "way" or tags.get("highway", "").endswith("_link"):
            continue
        seg = _nearest_segment(el.get("geometry"), lat, lon)
        highway = tags.get("highway", "")
        if not seg or seg[0] > MAX_DIST_M.get(highway, SURFACE_DIST_M):
            continue
        # A freeway in reach beats a closer frontage road.
        dist, bearing = seg
        rank = (0 if highway in MAX_DIST_M else 1, dist)
        oneway = tags.get("oneway", "no")
        if oneway == "-1":
            bearing = (bearing + 180) % 360
        if oneway in ("yes", "-1", "true", "1") or tags.get("highway") == "motorway":
            if want_heading is not None and _angle(bearing, want_heading) > 60:
                continue
            total = _int(tags.get("lanes"))
            if not total:
                continue
            choices.append((rank, total, _hov_types(tags.get("hov:lanes"), total)))
            continue
        # Two-way road: the lanes going our way.
        forward = want_heading is None or _angle(bearing, want_heading) <= 90
        side = "forward" if forward else "backward"
        total = _int(tags.get(f"lanes:{side}"))
        if not total:
            both = _int(tags.get("lanes"))
            total = both // 2 if both and both % 2 == 0 else None
        if total and want_heading is not None:
            choices.append((rank, total,
                            _hov_types(tags.get(f"hov:lanes:{side}"), total)))
    if not choices:
        return None
    _, total, types = min(choices, key=lambda c: c[0])
    return total, types


def query(lat: float, lon: float) -> str:
    d = 0.002
    return (f'[out:json][timeout:10];way(around:{RADIUS_M},{lat:.5f},{lon:.5f})'
            f'[highway~"{_ROADS}"];'
            f"out tags geom({lat - d:.5f},{lon - d:.5f},{lat + d:.5f},{lon + d:.5f});")


async def lookup(client, lat: float, lon: float, direction: str | None = None):
    """One Overpass query. Returns (total, types), None for no answer,
    or raises on a transport failure (so the point is retried)."""
    resp = await client.post(OVERPASS_URL, data={"data": query(lat, lon)},
                             headers={"User-Agent": USER_AGENT}, timeout=60)
    if resp.status_code in (429, 503, 504):
        raise RuntimeError(f"overpass busy ({resp.status_code})")
    resp.raise_for_status()
    return pick(resp.json().get("elements"), lat, lon, direction)


async def _drain(get_client) -> None:
    while True:
        if not _queue or not UPSTREAM.allow("overpass-lanes", DAILY_CAP):
            await _sleep(30 if _queue else 5)
            continue
        k, (lat, lon, direction) = _queue.popitem(last=False)
        try:
            _store(k, await lookup(get_client(), lat, lon, direction))
        except Exception as exc:  # noqa: BLE001 - never kill the worker
            log.info("lane lookup failed: %s", exc)
            await _sleep(60)
        await _sleep(PACE_SECONDS)


def start_worker(get_client) -> None:
    global _worker_task
    if os.environ.get("PYTEST_CURRENT_TEST") or not DAILY_CAP:
        return  # tests never reach the real Overpass; a cap of 0 turns it off
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.get_running_loop().create_task(_drain(get_client))


def stats() -> dict:
    return {"cached": len(_cache), "queued": len(_queue),
            "today": UPSTREAM.used("overpass-lanes"), "cap": DAILY_CAP}


# ---------------------------------------------------------------- layouts

# CHP comment parses by (incident id, comment count): the comments only
# grow, and build_markers runs on every map request.
_CHP_REFS: dict[tuple, lanes.LaneRefs] = {}


def chp_layout(i) -> dict | None:
    """lane_layout for a CHP incident, or None. CHP never says how wide
    the road is: the count comes from the map lookup cache, and a miss
    queues a lookup so a later request has it."""
    key = (i.id, len(i.details))
    refs = _CHP_REFS.get(key)
    if refs is None:
        refs = lanes.chp_refs(i.details)
        if len(_CHP_REFS) > 5000:
            _CHP_REFS.clear()
        _CHP_REFS[key] = refs
    if not refs.any():
        return None
    hint = direction_hint(i.location)
    got = known(i.lat, i.lon, hint)
    if not got:
        want(i.lat, i.lon, hint)
        return None
    return lanes.resolve(refs, got[0], types=got[1], basis="lookup")


def text_layouts(markers) -> None:
    """lane_layout for state markers whose feed says lanes in words
    ("Right lane closed"), once the map lookup knows the road's width.
    Feeds with structured lanes (WZDx, NE Compass, CDOT) set it at
    parse time and are left alone."""
    for m in markers:
        if m.get("lane_layout") or not isinstance(m.get("lanes"), str):
            continue
        if m.get("kind") not in ("incident", "lane_closure"):
            continue
        refs = lanes.text_refs(m["lanes"])
        if not refs.any():
            continue
        got = known(m.get("lat"), m.get("lon"), m.get("dir"))
        if not got:
            want(m.get("lat"), m.get("lon"), m.get("dir"))
            continue
        m["lane_layout"] = lanes.resolve(refs, got[0], types=got[1], basis="lookup")


def lcs_layout(c) -> dict | None:
    """lane_layout for a Caltrans LCS closure, or None."""
    if c.total_lanes:
        return lanes.from_lcs(c.lanes_closed, c.total_lanes)
    if not lanes.lcs_refs(c.lanes_closed).any():
        return None
    got = known(c.begin_lat, c.begin_lon, c.direction)
    if not got:
        want(c.begin_lat, c.begin_lon, c.direction)
        return None
    return lanes.from_lcs(c.lanes_closed, None, lookup_total=got[0],
                          lookup_types=got[1])
