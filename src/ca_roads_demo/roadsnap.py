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
import math
import os
import time

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


def apply(markers: list[dict]) -> list[dict]:
    """Attach snapped paths to closures lacking usable native geometry.
    Mutates the marker dicts (they are cache-shared, so a snap sticks
    for every later request). Closures whose feeds provide real
    geometry are never touched."""
    for m in markers:
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
            path = await _snap(client, *pair)
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
