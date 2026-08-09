"""Shareable trip pages and the storage behind them.

A trip is a saved snapshot of a planned route: endpoints, summary,
geometry, and directions. Anyone can create one from the planner (rate
limited, size capped, no account) and the share URL renders a
standalone page with the route on a map, live conditions along it, and
og tags so the link unfurls in group chats.

Geometry is stored as an encoded polyline string because Firestore
rejects nested arrays; steps are a list of maps. Trips expire after
180 days via a Firestore TTL policy on expire_at."""

from __future__ import annotations

import contextlib
import html as html_mod
import json
import os
import re
import secrets as pysecrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from ca_roads_demo import watch as watch_mod

DEMO_URL = os.environ.get(
    "DEMO_URL", "https://commutescout.com")
MAX_TRIP_POINTS = 500
MAX_TRIP_STEPS = 80
TRIP_TTL_DAYS = 180
# Trip creation has its own quota instead of the shared request bucket:
# the page's event beacons drain that bucket, which made the Share
# button 429 for normal use. In-process like every other guard.
TRIPS_PER_DAY_PER_IP = 20
_trip_counts: dict[str, tuple[str, int]] = {}


def _trip_allowed(ip: str) -> bool:
    day = datetime.now(UTC).date().isoformat()
    stored_day, count = _trip_counts.get(ip, (day, 0))
    if stored_day != day:
        count = 0
    if count >= TRIPS_PER_DAY_PER_IP:
        return False
    _trip_counts[ip] = (day, count + 1)
    if len(_trip_counts) > 5000:
        _trip_counts.clear()
    return True

_TEMPLATE_PATH = Path(__file__).parent / "static" / "trip.html"
_TRIP_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_MAX_TRIP_BODY = 256 * 1024


def _clean(value, limit):
    return re.sub(r"[\x00-\x1f\x7f]", " ", str(value or "")).strip()[:limit]


# Every placeholder the trip template carries. Substituting through one
# regex pass keeps an inserted value from being read as a placeholder by
# a later replacement (see the comment in trip_page).
_PLACEHOLDER_RE = re.compile(r"__(?:TITLE|OG_IMAGE|OG_URL|TRIP_JSON)__")
_template_cache: str | None = None


def encode_polyline(points: list, precision: int = 5) -> str:
    """Google polyline encoding of [lat, lon] pairs."""
    factor = 10 ** precision
    out: list[str] = []
    prev_lat = prev_lon = 0
    for pt in points:
        lat = round(float(pt[0]) * factor)
        lon = round(float(pt[1]) * factor)
        for value in (lat - prev_lat, lon - prev_lon):
            value = ~(value << 1) if value < 0 else value << 1
            while value >= 0x20:
                out.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            out.append(chr(value + 63))
        prev_lat, prev_lon = lat, lon
    return "".join(out)


def decode_polyline(encoded: str, precision: int = 5) -> list:
    factor = 10 ** precision
    points = []
    index = lat = lon = 0
    while index < len(encoded):
        for target in ("lat", "lon"):
            shift = result = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if target == "lat":
                lat += delta
            else:
                lon += delta
        points.append([lat / factor, lon / factor])
    return points


async def api_trip_create(request: Request) -> JSONResponse:
    from ca_roads_demo.app import client_ip

    if not _trip_allowed(client_ip(request)):
        return JSONResponse(
            {"error": "daily share-link limit reached; try tomorrow"},
            status_code=429)
    raw = b""
    async for chunk in request.stream():
        raw += chunk
        if len(raw) > _MAX_TRIP_BODY:
            return JSONResponse({"error": "request too large"},
                                status_code=413)
    body = None
    with contextlib.suppress(Exception):
        body = json.loads(raw) if raw else None
    if not isinstance(body, dict):
        return JSONResponse({"error": "json body required"}, status_code=400)

    raw_pts = body.get("latlngs") or []
    if not (2 <= len(raw_pts) <= MAX_TRIP_POINTS):
        return JSONResponse(
            {"error": f"latlngs must be 2-{MAX_TRIP_POINTS} points"},
            status_code=400)
    try:
        points = [[float(p[0]), float(p[1])] for p in raw_pts]
    except (TypeError, ValueError, IndexError):
        return JSONResponse({"error": "latlngs must be [lat, lon] pairs"},
                            status_code=400)
    for lat, lon in (points[0], points[-1]):
        if not watch_mod.in_california(lat, lon):
            return JSONResponse({"error": "trips must start and end in "
                                          "California"}, status_code=400)

    steps = []
    for s in (body.get("steps") or [])[:MAX_TRIP_STEPS]:
        if isinstance(s, dict) and s.get("text"):
            steps.append({"text": _clean(s["text"], 200),
                          "miles": round(float(s.get("miles") or 0), 2)})

    trip = {
        "from_name": _clean(body.get("from_name"), 120) or "Start",
        "to_name": _clean(body.get("to_name"), 120) or "End",
        "miles": round(float(body.get("miles") or 0), 1),
        "minutes": int(float(body.get("minutes") or 0)),
        "via": _clean(body.get("via"), 80),
        "polyline": encode_polyline(points),
        "steps": steps,
        "created_at": datetime.now(UTC).isoformat(),
        "expire_at": datetime.now(UTC) + timedelta(days=TRIP_TTL_DAYS),
    }
    trip_id = pysecrets.token_urlsafe(6)
    store = watch_mod.get_store()
    await store.create_trip(trip_id, trip)
    return JSONResponse({"id": trip_id, "url": f"{DEMO_URL}/trip/{trip_id}"})


def _trip_public(trip: dict) -> dict:
    return {k: trip[k] for k in ("from_name", "to_name", "miles", "minutes",
                                 "via", "polyline", "steps", "created_at")
            if k in trip}


async def api_trip_get(request: Request) -> JSONResponse:
    tid = request.path_params["trip_id"]
    if not _TRIP_ID_RE.match(tid):
        return JSONResponse({"error": "not found"}, status_code=404)
    trip = await watch_mod.get_store().get_trip(tid)
    if trip is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(_trip_public(trip))


async def trip_page(request: Request) -> HTMLResponse:
    """Server-rendered so link unfurlers (which run no JS) see the og
    tags, and the page itself needs no second fetch."""
    global _template_cache
    tid = request.path_params["trip_id"]
    if not _TRIP_ID_RE.match(tid):
        # Raise so the app's branded 404 handler renders the site shell
        # (header, footer, link home) instead of a bare heading.
        raise HTTPException(status_code=404)
    trip = await watch_mod.get_store().get_trip(tid)
    if trip is None:
        raise HTTPException(status_code=404)
    if _template_cache is None:
        _template_cache = _TEMPLATE_PATH.read_text(encoding="utf-8")
    pub = _trip_public(trip)
    title = (f"{pub['from_name']} → {pub['to_name']} · "
             f"{pub['miles']:.0f} mi · CommuteScout")
    mid = decode_polyline(pub["polyline"])
    mid = mid[len(mid) // 2] if mid else [37.5, -120.5]
    og_image = (f"{DEMO_URL}/api/staticmap?lat={mid[0]:.4f}"
                f"&lon={mid[1]:.4f}&z=9&k=incident")
    # One pass, not a chain of .replace() calls. Chained replaces re-scan
    # the text they just inserted, so a trip name of literally
    # "__TRIP_JSON__" survived escaping (escaping does not touch
    # underscores), landed inside the og:title attribute, and was then
    # substituted by the next call in the chain. json.dumps output starts
    # with '{"', which closed content=" and let the rest of the JSON,
    # including attacker-controlled names, be parsed as markup. Anyone
    # could plant one through POST /api/trip and it fired for every
    # visitor who opened the link. Substituting in a single pass means a
    # replacement value is never treated as a placeholder.
    values = {
        "__TITLE__": html_mod.escape(title),
        "__OG_IMAGE__": html_mod.escape(og_image),
        "__OG_URL__": html_mod.escape(
            f"{DEMO_URL}/trip/{request.path_params['trip_id']}"),
        "__TRIP_JSON__": json.dumps(pub).replace("</", "<\\/"),
    }
    page = _PLACEHOLDER_RE.sub(lambda m: values[m.group(0)], _template_cache)
    return HTMLResponse(page)
