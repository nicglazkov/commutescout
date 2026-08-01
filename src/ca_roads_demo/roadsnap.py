"""Road-snapping for closures whose feeds publish endpoints but no
geometry (Caltrans LCS, WSDOT alerts, Travel-IQ events without
polylines, CDOT planned events).

The rule this serves: a line shown to a user must follow the road.
Feeds without native geometry get their begin/end pair routed ONCE,
the shape cached in Firestore forever and mirrored in memory, and a
polite worker drains the queue at sub-router-limit pace. Until a
closure's snap completes it renders as a dot; a snap that fails the
quality gates (no route, absurd detour, endpoints too far apart) is
remembered as "no line" so a guess is never drawn.

Local dev has no ADC: Firestore calls are best-effort and the module
degrades to in-process caching.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import math
import os
import re
import time

log = logging.getLogger("roadsnap")

OSRM_URL = "https://router.project-osrm.org/route/v1/driving/"
UA = {"User-Agent":
      "commutescout.com closure snapper (https://commutescout.com)"}
# Pairs closer than this render fine as short straight segments (the
# client draws sub-800m two-point paths as-is); farther than the max
# is a data smell, not a drawable closure.
MIN_METERS = 150
MAX_METERS = 120_000
# A route much longer than the crow-flies distance means the router
# connected the endpoints via some other road: wrong shape, no line.
MAX_RATIO = 3.0
MAX_EXTRA_METERS = 20_000
PACE_SECONDS = 0.7

_mem: dict[str, list | None] = {}
_queue: list[str] = []
_queued: set[str] = set()
_pairs: dict[str, tuple] = {}
_loaded = False
_worker_task = None
_db = None


def _key(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
    raw = f"{lat1:.4f},{lon1:.4f},{lat2:.4f},{lon2:.4f}"
    return hashlib.sha1(raw.encode()).hexdigest()[:20]


def _get_db():
    global _db
    if _db is None:
        from google.cloud import firestore

        _db = firestore.AsyncClient(
            project=os.environ.get("GOOGLE_CLOUD_PROJECT", "ca-roads-mcp"))
    return _db


def _straight_meters(lat1, lon1, lat2, lon2) -> float:
    dx = (lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2)) * 111_320
    dy = (lat2 - lat1) * 110_540
    return math.hypot(dx, dy)


def _bearing(lat1, lon1, lat2, lon2) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dl = lo2 - lo1
    x = math.sin(dl) * math.cos(la2)
    y = (math.cos(la1) * math.sin(la2)
         - math.sin(la1) * math.cos(la2) * math.cos(dl))
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _bearing_gap(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


async def load_persisted() -> None:
    """Boot: mirror every previously computed snap into memory so a
    redeploy never re-routes what is already known."""
    global _loaded
    if _loaded:
        return
    _loaded = True
    with contextlib.suppress(Exception):
        db = _get_db()
        async for snap in db.collection("road_snaps").stream():
            d = snap.to_dict() or {}
            _mem[snap.id] = (json.loads(d["path"])
                             if d.get("ok") and d.get("path") else None)


def path_for(lat1, lon1, lat2, lon2) -> list | None:
    """Cached snap for an endpoint pair; unknown pairs are queued and
    return None (dot until the worker gets there)."""
    vals = (lat1, lon1, lat2, lon2)
    if not all(isinstance(v, (int, float)) and v for v in vals):
        return None
    key = _key(*vals)
    if key in _mem:
        return _mem[key]
    if key not in _queued:
        _queued.add(key)
        _pairs[key] = vals
        _queue.append(key)
    return None


def toll_pair_for(a, b, brg: float, token: str | None) -> dict | None:
    """Directional snap for a toll gantry pair: cached like path_for,
    but keyed on the travel bearing and route token too, so the fixed
    snapper never reads the old direction-blind cache entries. Returns
    {"path": [...], "a": [lat, lon], "b": [lat, lon]} with the
    endpoints re-centered onto the correct carriageway."""
    vals = (a[0], a[1], b[0], b[1])
    if not all(isinstance(v, (int, float)) and v for v in vals):
        return None
    raw = (f"t2:{vals[0]:.4f},{vals[1]:.4f},{vals[2]:.4f},{vals[3]:.4f},"
           f"{brg:.0f},{token or ''}")
    key = hashlib.sha1(raw.encode()).hexdigest()[:20]
    if key in _mem:
        got = _mem[key]
        return got if isinstance(got, dict) else None
    if key not in _queued:
        _queued.add(key)
        _pairs[key] = ("T", vals[0], vals[1], vals[2], vals[3], brg,
                       token or "")
        _queue.append(key)
    return None


def corridor_segments(points: list) -> list[list]:
    """Road-following polyline parts through an ordered gantry chain.
    Each consecutive pair snaps independently (cached forever, same
    Firestore store as closures): adjacent signs closer than MIN_METERS
    bridge directly (that short, straight IS the road), unresolved or
    rejected pairs leave a gap rather than a guessed chord. The line
    grows as the background worker drains the queue."""
    segs: list[list] = []
    for a, b in zip(points, points[1:], strict=False):
        straight = _straight_meters(a[0], a[1], b[0], b[1])
        if straight > MAX_METERS:
            continue
        if straight < MIN_METERS:
            seg = [[round(a[0], 5), round(a[1], 5)],
                   [round(b[0], 5), round(b[1], 5)]]
        else:
            seg = path_for(a[0], a[1], b[0], b[1])
            if not seg:
                continue
        if segs and segs[-1][-1] == seg[0]:
            segs[-1].extend(seg[1:])
        else:
            segs.append(list(seg))
    return segs


def apply(markers: list[dict]) -> list[dict]:
    """Attach snapped paths to closures lacking usable native geometry,
    and road-following segment chains to toll corridors.
    Mutates the marker dicts (they are cache-shared, so a snap sticks
    for every later request). Closures whose feeds provide real
    geometry are never touched."""
    for m in markers:
        if m.get("kind") == "toll" and isinstance(m.get("entries"), list):
            if m.get("segs"):
                continue  # baked geometry (bridges) is never re-routed
            _apply_toll(m)
            continue
        if m.get("kind") != "lane_closure":
            continue
        path = m.get("path")
        if isinstance(path, list) and len(path) > 2:
            continue          # native road geometry wins
        end = m.get("end")
        if (not end and isinstance(path, list) and len(path) == 2
                and isinstance(path[1], list)):
            end = path[1]
        if not isinstance(end, (list, tuple)) or len(end) < 2:
            continue
        snapped = path_for(m.get("lat"), m.get("lon"), end[0], end[1])
        if snapped:
            m["path"] = snapped
            m["end"] = snapped[-1]
    return markers


def _apply_toll(m: dict) -> None:
    """Snap a toll corridor with direction discipline. Each gantry
    pair routes with the pair's travel bearing so OSRM picks the
    correct carriageway (the old direction-blind snap put 101 NB
    onto Airport Blvd when a gantry sat nearer the SB side), and the
    resolved snap re-centers the gantry points onto the road, so
    price tags and highlight dots sit ON the carriageway."""
    corridor = m.get("corridor") or m.get("name") or ""
    mnum = re.search(r"(\d{2,3})", corridor)
    token = mnum.group(1) if mnum else None
    chain: list = []
    refs: list[tuple[int, int]] = []
    for ei, e in enumerate(m["entries"]):
        for pi, pt in enumerate(e.get("pts") or []):
            chain.append(pt)
            refs.append((ei, pi))
    if len(chain) < 2:
        return
    segs: list[list] = []
    snapped: dict[int, list] = {}
    for i, (a, b) in enumerate(zip(chain, chain[1:], strict=False)):
        straight = _straight_meters(a[0], a[1], b[0], b[1])
        if straight > MAX_METERS:
            continue
        if straight < MIN_METERS:
            seg = [[round(a[0], 5), round(a[1], 5)],
                   [round(b[0], 5), round(b[1], 5)]]
        else:
            d = toll_pair_for(a, b, _bearing(a[0], a[1], b[0], b[1]),
                              token)
            if not d:
                continue
            seg = d["path"]
            snapped[i] = d["a"]
            snapped[i + 1] = d["b"]
        if segs and segs[-1][-1] == seg[0]:
            segs[-1].extend(seg[1:])
        else:
            segs.append(list(seg))
    if segs:
        m["segs"] = segs
    # Re-center resolved gantry points onto the snapped carriageway.
    for idx, pt in snapped.items():
        ei, pi = refs[idx]
        m["entries"][ei]["pts"][pi] = [round(pt[0], 5), round(pt[1], 5)]


# The tolerance OSRM gets per waypoint: wide enough for corridor
# curvature between distant gantries, tight enough to reject the
# opposite carriageway (which differs by ~180).
TOLL_BEARING_TOL = 50
# Share of a leg's distance that must run on the corridor's own route
# number for the snap to count as "on the highway".
TOLL_ON_ROUTE_MIN = 0.80


async def _snap_toll(client, lat1, lon1, lat2, lon2, brg, token):
    straight = _straight_meters(lat1, lon1, lat2, lon2)
    if straight < MIN_METERS or straight > MAX_METERS:
        return None
    coords = f"{lon1:.5f},{lat1:.5f};{lon2:.5f},{lat2:.5f}"
    bearings = f"{brg:.0f},{TOLL_BEARING_TOL};{brg:.0f},{TOLL_BEARING_TOL}"
    data = None
    for radius in ("60;60", "150;150"):
        resp = await client.get(
            f"{OSRM_URL}{coords}", headers=UA, timeout=20.0,
            params={"overview": "full", "geometries": "geojson",
                    "steps": "true", "continue_straight": "true",
                    "bearings": bearings, "radiuses": radius})
        if resp.status_code == 400:
            continue  # no candidate within radius+bearing: widen once
        resp.raise_for_status()
        body = resp.json() or {}
        if (body.get("routes") or []):
            data = body
            break
    if not data:
        log.info("toll snap rejected (no directional route) %s %s",
                 token, coords)
        return None
    route = data["routes"][0]
    dist = route.get("distance") or 0
    if dist > straight * MAX_RATIO or dist > straight + MAX_EXTRA_METERS:
        log.info("toll snap rejected (detour %sm vs %sm) %s %s",
                 int(dist), int(straight), token, coords)
        return None
    # Validation 1: the leg must actually run on the designated
    # highway. Any meaningful share on side streets (Airport Blvd
    # beside 101) is a wrong snap, not a drawable corridor.
    if token:
        pat = re.compile(rf"\b{re.escape(token)}\b")
        total = on_route = 0.0
        for leg in route.get("legs") or []:
            for s in leg.get("steps") or []:
                d = s.get("distance") or 0
                total += d
                names = " ".join(str(s.get(k) or "")
                                 for k in ("ref", "name", "destinations"))
                if pat.search(names):
                    on_route += d
        if total > 0 and on_route / total < TOLL_ON_ROUTE_MIN:
            log.info("toll snap rejected (%d%% on route %s) %s",
                     int(100 * on_route / total), token, coords)
            return None
    # Validation 2: the snapped endpoints must move in the corridor
    # direction (a backwards or wrong-carriageway snap fails here).
    wps = data.get("waypoints") or []
    if len(wps) < 2:
        return None
    a_loc = wps[0].get("location") or [lon1, lat1]
    b_loc = wps[1].get("location") or [lon2, lat2]
    net = _bearing(a_loc[1], a_loc[0], b_loc[1], b_loc[0])
    if _bearing_gap(net, brg) > 60:
        log.info("toll snap rejected (net bearing %d vs %d) %s %s",
                 int(net), int(brg), token, coords)
        return None
    pts = (route.get("geometry") or {}).get("coordinates") or []
    if len(pts) < 2:
        return None
    step = max(1, len(pts) // 80)
    path = [[round(p[1], 5), round(p[0], 5)] for p in pts[::step]]
    tail = [round(pts[-1][1], 5), round(pts[-1][0], 5)]
    if path[-1] != tail:
        path.append(tail)
    if len(path) < 2:
        return None
    return {"path": path,
            "a": [round(a_loc[1], 5), round(a_loc[0], 5)],
            "b": [round(b_loc[1], 5), round(b_loc[0], 5)]}


async def _snap(client, lat1, lon1, lat2, lon2) -> list | None:
    straight = _straight_meters(lat1, lon1, lat2, lon2)
    if straight < MIN_METERS or straight > MAX_METERS:
        return None
    coords = f"{lon1:.5f},{lat1:.5f};{lon2:.5f},{lat2:.5f}"
    resp = await client.get(
        f"{OSRM_URL}{coords}", headers=UA, timeout=20.0,
        params={"overview": "full", "geometries": "geojson"})
    resp.raise_for_status()
    routes = (resp.json() or {}).get("routes") or []
    if not routes:
        return None
    route = routes[0]
    dist = route.get("distance") or 0
    if dist > straight * MAX_RATIO or dist > straight + MAX_EXTRA_METERS:
        return None
    pts = (route.get("geometry") or {}).get("coordinates") or []
    if len(pts) < 2:
        return None
    step = max(1, len(pts) // 80)
    path = [[round(p[1], 5), round(p[0], 5)] for p in pts[::step]]
    tail = [round(pts[-1][1], 5), round(pts[-1][0], 5)]
    if path[-1] != tail:
        path.append(tail)
    return path if len(path) > 1 else None


async def _drain(client) -> None:
    await load_persisted()
    while True:
        if not _queue:
            await asyncio.sleep(5)
            continue
        key = _queue.pop(0)
        _queued.discard(key)
        pair = _pairs.pop(key, None)
        if pair is None or key in _mem:
            continue
        try:
            # A callable yields the CURRENT shared client, so a pool
            # reset does not leave the worker on a dead pool forever.
            cli = client() if callable(client) else client
            if pair[0] == "T":
                path = await _snap_toll(cli, *pair[1:])
            else:
                path = await _snap(cli, *pair)
        except Exception:  # noqa: BLE001 - router hiccup: retry later
            _queued.add(key)
            _pairs[key] = pair
            _queue.append(key)
            await asyncio.sleep(30)
            continue
        _mem[key] = path
        with contextlib.suppress(Exception):
            await _get_db().collection("road_snaps").document(key).set({
                "ok": path is not None,
                "path": json.dumps(path) if path else None,
                "ts": time.time(),
            })
        await asyncio.sleep(PACE_SECONDS)


def start_worker(client) -> None:
    """Idempotent: one polite background snapper per process."""
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_drain(client))
