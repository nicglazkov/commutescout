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
import hashlib
import json
import logging
import math
import os
import re
import time
from datetime import UTC, datetime, timedelta

from ca_roads_demo import valhalla

log = logging.getLogger("roadsnap")

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

# key -> compact JSON string of the snapped path (a list for closures,
# a dict for toll pairs), or None for a pair that failed the quality
# gates. Kept as the string Firestore holds and decoded on use: the
# same 19,600 paths as nested Python lists cost about 700 MB of RSS on
# a 2 GiB instance (measured 2026-09-16, the daily memory kill).
_mem: dict[str, str | None] = {}
_queue: list[str] = []
_queued: set[str] = set()
_pairs: dict[str, tuple] = {}
_tries: dict[str, int] = {}
_loaded = False
_worker_task = None
_db = None
# Transient router misses retry this many times before a pair is
# written off as unroutable.
MAX_TRANSIENT_TRIES = 5
# A failed boot mirror is retried on this cadence (doubling to ten
# minutes); the worker buys nothing until the mirror is complete.
LOAD_RETRY_SECONDS = 60
# The mirror is read in pages of this many documents. One query over
# the whole collection times out server-side on a busy boot (seen in
# production: 503 after 10,401 of 19,624 docs at 166 s, then 504 at
# 321 s), because the event loop is also warming fifty feeds and the
# stream is consumed slowly. Each page is its own short RPC.
LOAD_PAGE = 2000
# Injectable so tests can stop the worker without wall-clock waits.
_sleep = asyncio.sleep


class TransientSnapError(Exception):
    """The router had no answer this time; the pair stays retryable."""


def _ready() -> bool:
    """Routing needs the Stadia key. A keyless process must not drain
    the queue: a missing key looks like "unroutable" and would tombstone
    every pair in Firestore forever."""
    return bool(os.environ.get("STADIA_API_KEY", "").strip())


def _api_key() -> str:
    key = os.environ.get("STADIA_API_KEY", "").strip()
    if not key:
        raise RuntimeError("STADIA_API_KEY is not set")
    return key


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


async def load_persisted() -> bool:
    """Boot: mirror every previously computed snap into memory so a
    redeploy never re-routes what is already known.

    Returns True once the mirror is complete. A failed or partial load
    must never read as "nothing is known": the worker would then
    re-buy every pair the feeds show it, one paid routing call each,
    and write the same documents again. Callers retry until True."""
    global _loaded
    if _loaded:
        return True
    t0 = time.monotonic()
    loaded: dict[str, str | None] = {}
    try:
        col = _get_db().collection("road_snaps")
        last = None
        while True:
            query = col.order_by("__name__").limit(LOAD_PAGE)
            if last is not None:
                query = query.start_after(last)
            count = 0
            async for snap in query.stream():
                count += 1
                last = snap
                d = snap.to_dict() or {}
                loaded[snap.id] = (d["path"]
                                   if d.get("ok") and d.get("path") else None)
            if count < LOAD_PAGE:
                break
    except Exception as exc:  # noqa: BLE001 - any failure means "not loaded"
        log.error("road_snaps load failed after %d docs in %.1fs: %s: %s",
                  len(loaded), time.monotonic() - t0,
                  type(exc).__name__, exc)
        return False
    _mem.update(loaded)
    _loaded = True
    log.info("road_snaps loaded: %d docs in %.1fs (%d in memory)",
             len(loaded), time.monotonic() - t0, len(_mem))
    return True


def path_for(lat1, lon1, lat2, lon2) -> list | None:
    """Cached snap for an endpoint pair; unknown pairs are queued and
    return None (dot until the worker gets there)."""
    vals = (lat1, lon1, lat2, lon2)
    if not all(isinstance(v, (int, float)) and v for v in vals):
        return None
    key = _key(*vals)
    if key in _mem:
        raw = _mem[key]
        return json.loads(raw) if raw else None
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
    raw = (f"t3:{vals[0]:.4f},{vals[1]:.4f},{vals[2]:.4f},{vals[3]:.4f},"
           f"{brg:.0f},{token or ''}")
    key = hashlib.sha1(raw.encode()).hexdigest()[:20]
    if key in _mem:
        raw = _mem[key]
        got = json.loads(raw) if raw else None
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
    # Re-center resolved gantry points onto the snapped carriageway,
    # UNLESS the corridor has hand-verified waypoints: those were
    # placed on the carriageway by hand and are authoritative.
    from ca_roads_demo import tollwaypoints

    if (m.get("src") or "", corridor) in tollwaypoints.WAYPOINTS:
        return
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
    key = _api_key()
    coords = f"{lon1:.5f},{lat1:.5f};{lon2:.5f},{lat2:.5f}"
    trip = None
    for radius in (60, 150):
        locations = [
            {"lat": lat1, "lon": lon1, "heading": round(brg),
             "heading_tolerance": TOLL_BEARING_TOL, "radius": radius},
            {"lat": lat2, "lon": lon2, "heading": round(brg),
             "heading_tolerance": TOLL_BEARING_TOL, "radius": radius},
        ]
        try:
            trip = await valhalla.route(client, locations, api_key=key)
        except valhalla.NoCandidateError:
            continue  # no candidate within radius+heading: widen once
        if trip:
            break
    if not trip:
        # The router intermittently finds no candidate; that is a
        # transient miss, not a verdict. Raising lets the worker retry
        # instead of tombstoning a routable pair.
        raise TransientSnapError(f"no directional route {token} {coords}")
    dist = valhalla.trip_meters(trip)
    if dist > straight * MAX_RATIO or dist > straight + MAX_EXTRA_METERS:
        log.info("toll snap rejected (detour %sm vs %sm) %s %s",
                 int(dist), int(straight), token, coords)
        return None
    # Validation 1: the leg must actually run on the designated
    # highway. Any meaningful share on side streets (Airport Blvd
    # beside 101) is a wrong snap, not a drawable corridor. Valhalla
    # maneuvers carry street names and per-maneuver length (km).
    if token:
        pat = re.compile(rf"\b{re.escape(token)}\b")
        total = on_route = 0.0
        for leg in trip.get("legs") or []:
            for m in leg.get("maneuvers") or []:
                d = float(m.get("length") or 0) * 1000.0
                total += d
                names = " ".join(
                    (m.get("street_names") or [])
                    + (m.get("begin_street_names") or []))
                if pat.search(names):
                    on_route += d
        if total > 0 and on_route / total < TOLL_ON_ROUTE_MIN:
            log.info("toll snap rejected (%d%% on route %s) %s",
                     int(100 * on_route / total), token, coords)
            return None
    pts = valhalla.trip_points(trip)
    if len(pts) < 2:
        return None
    # Validation 2: the snapped endpoints must move in the corridor
    # direction (a backwards or wrong-carriageway snap fails here).
    # The decoded shape starts and ends on the snapped carriageway.
    a_loc, b_loc = pts[0], pts[-1]
    net = _bearing(a_loc[0], a_loc[1], b_loc[0], b_loc[1])
    if _bearing_gap(net, brg) > 60:
        log.info("toll snap rejected (net bearing %d vs %d) %s %s",
                 int(net), int(brg), token, coords)
        return None
    step = max(1, len(pts) // 80)
    path = [[round(p[0], 5), round(p[1], 5)] for p in pts[::step]]
    tail = [round(pts[-1][0], 5), round(pts[-1][1], 5)]
    if path[-1] != tail:
        path.append(tail)
    if len(path) < 2:
        return None
    return {"path": path,
            "a": [round(a_loc[0], 5), round(a_loc[1], 5)],
            "b": [round(b_loc[0], 5), round(b_loc[1], 5)]}


async def _snap(client, lat1, lon1, lat2, lon2) -> list | None:
    straight = _straight_meters(lat1, lon1, lat2, lon2)
    if straight < MIN_METERS or straight > MAX_METERS:
        return None
    try:
        trip = await valhalla.route(
            client,
            [{"lat": lat1, "lon": lon1}, {"lat": lat2, "lon": lon2}],
            api_key=_api_key())
    except valhalla.NoCandidateError:
        return None
    if not trip:
        return None
    dist = valhalla.trip_meters(trip)
    if dist > straight * MAX_RATIO or dist > straight + MAX_EXTRA_METERS:
        return None
    pts = valhalla.trip_points(trip)
    if len(pts) < 2:
        return None
    step = max(1, len(pts) // 80)
    path = [[round(p[0], 5), round(p[1], 5)] for p in pts[::step]]
    tail = [round(pts[-1][0], 5), round(pts[-1][1], 5)]
    if path[-1] != tail:
        path.append(tail)
    return path if len(path) > 1 else None


async def _drain(client) -> None:
    # No purchases until the boot mirror is complete (see load_persisted).
    delay = LOAD_RETRY_SECONDS
    while not await load_persisted():
        await _sleep(delay)
        delay = min(delay * 2, 600)
    while True:
        if not _ready():
            await _sleep(300)
            continue
        if not _queue:
            await _sleep(5)
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
        except TransientSnapError as exc:
            n = _tries.get(key, 0) + 1
            if n >= MAX_TRANSIENT_TRIES:
                log.info("toll snap rejected after %d tries: %s", n, exc)
                _tries.pop(key, None)
                path = None
            else:
                _tries[key] = n
                _queued.add(key)
                _pairs[key] = pair
                _queue.append(key)
                await _sleep(10)
                continue
        except Exception as exc:  # noqa: BLE001 - router hiccup: retry later
            # Visible on purpose: a pair that fails the same way every
            # time would otherwise loop here forever, one paid call per
            # try, with nothing in the logs.
            log.warning("snap retry later %s: %s: %s", key,
                        type(exc).__name__, str(exc)[:160])
            _queued.add(key)
            _pairs[key] = pair
            _queue.append(key)
            await _sleep(30)
            continue
        raw = json.dumps(path, separators=(",", ":")) if path else None
        _mem[key] = raw
        try:
            # expire_at feeds the Firestore TTL policy on road_snaps:
            # a stretch nobody has needed for a year is re-bought if
            # it ever comes back, and storage plus boot memory stay
            # bounded.
            await _get_db().collection("road_snaps").document(key).set({
                "ok": path is not None,
                "path": raw,
                "ts": time.time(),
                "expire_at": datetime.now(UTC) + timedelta(days=365),
            })
        except Exception as exc:  # noqa: BLE001 - keep serving, but say so
            # An unpersisted purchase is bought again after the next
            # restart.
            log.warning("snap persist failed %s: %s", key,
                        type(exc).__name__)
        # One line per paid routing purchase: the audit trail for the
        # Stadia bill, and the queue depth says whether the worker is
        # keeping up with the feeds.
        log.info("snap %s %s ok=%s queue=%d",
                 "toll" if pair[0] == "T" else "closure", key,
                 path is not None, len(_queue))
        await _sleep(PACE_SECONDS)


def start_worker(client) -> None:
    """Idempotent: one polite background snapper per process."""
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_drain(client))
