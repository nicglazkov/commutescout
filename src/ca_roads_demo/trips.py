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
import secrets as pysecrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from ca_roads_demo import watch as watch_mod

DEMO_URL = os.environ.get(
    "DEMO_URL", "https://ca-roads-demo-15002631928.us-west1.run.app")
MAX_TRIP_POINTS = 500
MAX_TRIP_STEPS = 80
TRIP_TTL_DAYS = 180

_TEMPLATE_PATH = Path(__file__).parent / "static" / "trip.html"
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
    body = None
    with contextlib.suppress(Exception):
        body = await request.json()
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
            steps.append({"text": str(s["text"])[:200],
                          "miles": round(float(s.get("miles") or 0), 2)})

    trip = {
        "from_name": str(body.get("from_name") or "Start")[:120],
        "to_name": str(body.get("to_name") or "End")[:120],
        "miles": round(float(body.get("miles") or 0), 1),
        "minutes": int(float(body.get("minutes") or 0)),
        "via": str(body.get("via") or "")[:80],
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
    trip = await watch_mod.get_store().get_trip(
        request.path_params["trip_id"])
    if trip is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(_trip_public(trip))


async def trip_page(request: Request) -> HTMLResponse:
    """Server-rendered so link unfurlers (which run no JS) see the og
    tags, and the page itself needs no second fetch."""
    global _template_cache
    trip = await watch_mod.get_store().get_trip(
        request.path_params["trip_id"])
    if trip is None:
        return HTMLResponse("<h1>This trip link has expired or never "
                            "existed.</h1>", status_code=404)
    if _template_cache is None:
        _template_cache = _TEMPLATE_PATH.read_text(encoding="utf-8")
    pub = _trip_public(trip)
    title = (f"{pub['from_name']} → {pub['to_name']} · "
             f"{pub['miles']:.0f} mi · CA Roads")
    mid = decode_polyline(pub["polyline"])
    mid = mid[len(mid) // 2] if mid else [37.5, -120.5]
    og_image = (f"{DEMO_URL}/api/staticmap?lat={mid[0]:.4f}"
                f"&lon={mid[1]:.4f}&z=9&k=incident")
    page = (_template_cache
            .replace("__TITLE__", html_mod.escape(title))
            .replace("__OG_IMAGE__", html_mod.escape(og_image))
            .replace("__OG_URL__", html_mod.escape(
                f"{DEMO_URL}/trip/{request.path_params['trip_id']}"))
            .replace("__TRIP_JSON__", json.dumps(pub).replace("</", "<\\/")))
    return HTMLResponse(page)
