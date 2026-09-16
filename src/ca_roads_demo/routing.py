"""Server-side route planning: Valhalla via Stadia with our own knowledge
on top.

Full closures become hard exclusions (points along the closed stretch
that the router must not use), and every candidate that comes back is
re-ranked by what lies on it: incidents, lane closures and chain
controls within 200 m of the line, each charged in minutes of hassle.
The route on top is the fastest one that does not drive through
today's trouble; the others stay one tap away with the reason spelled
out. Plugin and user reports will enter through the same two doors
(an exclusion or a penalty) once they exist.

Everything here is pure except ``plan``, which takes the fetcher as an
argument so tests never touch the network.
"""

from __future__ import annotations

import math
from collections.abc import Awaitable, Callable
from typing import Any

# Valhalla options per one-tap preset. Preferences, not bans: Valhalla
# treats use_highways/use_tolls as a cost, so a route that cannot avoid
# them still comes back.
PRESETS: dict[str, dict] = {
    "fastest": {},
    "no_highways": {"costing_options": {"auto": {"use_highways": 0}}},
    "no_tolls": {"costing_options": {"auto": {"use_tolls": 0}}},
    "shortest": {"shortest": True},
    "avoid_chains": {},
}

NEAR_M = 200.0            # a thing counts when it sits on the road itself
EXCLUDE_CAP = 50          # Valhalla's exclude_locations limit
EXCLUDE_SPACING_M = 1500  # points along a closed stretch, so every edge is hit

# Minutes of hassle a candidate is charged for each thing on it. Tuned
# to what a driver would trade distance for: a collision is a slowdown
# and a lane drop, an R-3 chain control is chains on or a turnaround.
PENALTY_MIN: dict[str, float] = {
    "collision": 6, "fire": 6, "hazard": 3, "other": 2,
    "lane": 4, "ramp": 1, "one-way-traffic": 5, "alternating-lanes": 5,
    "closure": 3,
    "R-1": 5, "R-2": 12, "R-3": 30,
}
LABELS = {
    "collision": ("collision", "collisions"),
    "fire": ("fire report", "fire reports"),
    "hazard": ("hazard", "hazards"),
    "other": ("incident", "incidents"),
    "lane": ("lane closure", "lane closures"),
    "ramp": ("ramp closure", "ramp closures"),
    "one-way-traffic": ("one-way stretch", "one-way stretches"),
    "alternating-lanes": ("one-way stretch", "one-way stretches"),
    "closure": ("closure", "closures"),
    "R-1": ("R-1 chain control", "R-1 chain controls"),
    "R-2": ("R-2 chain control", "R-2 chain controls"),
    "R-3": ("R-3 chain control", "R-3 chain controls"),
}


def meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Equirectangular distance: exact enough at a few hundred meters."""
    kx = 111_320.0 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot((lat2 - lat1) * 111_320.0, (lon2 - lon1) * kx)


def incident_kind(log_type: str | None) -> str:
    t = (log_type or "").lower()
    if "collision" in t or "hit and run" in t or "crash" in t:
        return "collision"
    if "fire" in t:
        return "fire"
    if any(w in t for w in ("hazard", "debris", "animal", "object", "roadway")):
        return "hazard"
    return "other"


def chain_level(status: str | None) -> str | None:
    s = (status or "").upper().replace(" ", "")
    for lvl in ("R-3", "R-2", "R-1"):
        if lvl in s or lvl.replace("-", "") in s:
            return lvl
    return None


def _along(path: list, spacing_m: float) -> list[tuple[float, float]]:
    """Points every ``spacing_m`` along a polyline, both ends included."""
    pts = [(float(p[0]), float(p[1])) for p in path
           if isinstance(p, (list, tuple)) and len(p) >= 2]
    if len(pts) < 2:
        return pts
    out = [pts[0]]
    since = 0.0
    for a, b in zip(pts, pts[1:], strict=False):
        seg = meters(a[0], a[1], b[0], b[1])
        if seg <= 0:
            continue
        pos = 0.0
        while since + (seg - pos) >= spacing_m:
            step = spacing_m - since
            pos += step
            f = pos / seg
            out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
            since = 0.0
        since += seg - pos
    if out[-1] != pts[-1]:
        out.append(pts[-1])
    return out


def exclusions(markers: list[dict], *, avoid_chains: bool = False) -> list[dict]:
    """Points the router must not route through: every full closure
    (sampled along its road-following path when the snapper has one),
    plus R-2 and R-3 chain controls when the driver asked to avoid
    chains. Capped at Valhalla's 50."""
    seen: set[tuple[float, float]] = set()
    out: list[dict] = []

    def add(lat, lon):
        key = (round(lat, 4), round(lon, 4))
        if key in seen or len(out) >= EXCLUDE_CAP:
            return
        seen.add(key)
        out.append({"lat": round(lat, 6), "lon": round(lon, 6)})

    for m in markers:
        kind = m.get("kind")
        if kind == "lane_closure" and m.get("cls") == "full-roadway":
            path = m.get("path")
            if isinstance(path, list) and len(path) >= 2:
                for lat, lon in _along(path, EXCLUDE_SPACING_M):
                    add(lat, lon)
            else:
                add(m["lat"], m["lon"])
                end = m.get("end")
                if isinstance(end, (list, tuple)) and len(end) >= 2:
                    add(end[0], end[1])
        elif avoid_chains and kind == "chain_control":
            if chain_level(m.get("status")) in ("R-2", "R-3"):
                add(m["lat"], m["lon"])
    return out


def _seg_dist(lat: float, lon: float, a: tuple, b: tuple) -> float:
    """Meters from a point to the segment a-b, in a local flat frame."""
    kx = 111_320.0 * math.cos(math.radians(lat))
    ky = 111_320.0
    ax, ay = (a[1] - lon) * kx, (a[0] - lat) * ky
    bx, by = (b[1] - lon) * kx, (b[0] - lat) * ky
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(ax, ay)
    t = max(0.0, min(1.0, -(ax * dx + ay * dy) / (dx * dx + dy * dy)))
    return math.hypot(ax + t * dx, ay + t * dy)


def on_route(lat: float, lon: float, pts: list, near_m: float = NEAR_M) -> bool:
    """Whether a point lies within ``near_m`` of the polyline. A coarse
    vertex pass (every 8th point, 3 km) gates the exact segment test."""
    n = len(pts)
    if n < 2:
        return False
    coarse = 3000.0 + near_m
    for i in range(0, n, 8):
        p = pts[i]
        if meters(lat, lon, p[0], p[1]) <= coarse:
            lo, hi = max(0, i - 8), min(n - 1, i + 8)
            for j in range(lo, hi):
                if _seg_dist(lat, lon, pts[j], pts[j + 1]) <= near_m:
                    return True
    return False


def penalty_kind(m: dict) -> str | None:
    kind = m.get("kind")
    if kind == "incident":
        return incident_kind(m.get("type"))
    if kind == "lane_closure":
        cls = m.get("cls")
        if cls == "full-roadway":
            return None  # excluded upstream; if it is still on the line, count it hard below
        if cls == "alternating-lanes":
            cls = "one-way-traffic"  # one tally for both flavors of one-way work
        return cls if cls in PENALTY_MIN else "closure"
    if kind == "chain_control":
        return chain_level(m.get("status"))
    return None


def score(pts: list, markers: list[dict]) -> dict:
    """Hassle on one candidate: minutes charged and a labeled tally."""
    counts: dict[str, int] = {}
    minutes = 0.0
    for m in markers:
        lat, lon = m.get("lat"), m.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        if m.get("kind") == "lane_closure" and m.get("cls") == "full-roadway":
            k = "full closure"
            if on_route(lat, lon, pts):
                counts[k] = counts.get(k, 0) + 1
                minutes += 45  # the router could not avoid it: say so loudly
            continue
        k = penalty_kind(m)
        if not k or not on_route(lat, lon, pts):
            continue
        counts[k] = counts.get(k, 0) + 1
        minutes += PENALTY_MIN.get(k, 2)
    hassles = []
    for k, n in sorted(counts.items(), key=lambda kv: -PENALTY_MIN.get(kv[0], 45)):
        one, many = LABELS.get(k, (k, k))
        hassles.append({"kind": k, "count": n,
                        "label": f"{n} {one if n == 1 else many}"})
    return {"penalty_min": round(minutes, 1), "hassles": hassles}


def _trip_points(trip: dict) -> list:
    from ca_roads_demo.valhalla import trip_points
    return trip_points(trip)


Fetcher = Callable[[dict], Awaitable[dict | None]]


async def plan(fetch: Fetcher, markers: list[dict], locations: list[dict],
               preset: str = "fastest") -> dict:
    """Plan through ``locations`` and rank what comes back.

    ``fetch(body)`` posts a Valhalla request body and returns the parsed
    JSON (``trip`` plus ``alternates``) or None. A request that fails
    with exclusions in place is retried without them, and the answer
    says so.
    """
    preset = preset if preset in PRESETS else "fastest"
    excl = exclusions(markers, avoid_chains=(preset == "avoid_chains"))
    body: dict[str, Any] = {
        "locations": locations, "costing": "auto",
        "alternates": 2 if len(locations) == 2 else 0,
        "directions_options": {"units": "miles"},
        **PRESETS[preset],
    }
    if excl:
        body["exclude_locations"] = excl
    note = None
    data = await fetch(body)
    if not (data and (data.get("trip") or {}).get("legs")) and excl:
        body.pop("exclude_locations", None)
        data = await fetch(body)
        note = ("No route avoids every current full closure, so this one "
                "may drive through one; check the conditions list.")
        excl = []
    if not (data and (data.get("trip") or {}).get("legs")):
        return {"routes": [], "preset": preset, "excluded": 0, "note": note}
    candidates = [data["trip"]] + [
        a["trip"] for a in data.get("alternates") or []
        if isinstance(a, dict) and (a.get("trip") or {}).get("legs")]
    ranked = []
    for trip in candidates:
        pts = _trip_points(trip)
        s = score(pts, markers)
        secs = float((trip.get("summary") or {}).get("time") or 0)
        ranked.append({"trip": trip, "score_s": round(secs + s["penalty_min"] * 60),
                       "penalty_min": s["penalty_min"], "hassles": s["hassles"]})
    ranked.sort(key=lambda r: r["score_s"])
    return {"routes": ranked, "preset": preset, "excluded": len(excl), "note": note}
