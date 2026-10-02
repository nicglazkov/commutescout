"""Speed and red light cameras from OpenStreetMap, as a Flare plugin.

Fixed cameras do not come and go like a police report, so there is no
upstream to poll: the plugin serves a small file (cameras.json, rebuilt
by refresh.py) and answers the two read endpoints of docs/flare.md.
Nothing is reported to it and nothing is confirmed through it; a camera
that is wrong is fixed where the data lives, on openstreetmap.org, and
every alert links to its record there.

Run it:

    pip install -r requirements.txt
    python server.py

Check it:

    python -m ca_roads.flare check http://127.0.0.1:8310
"""

from __future__ import annotations

import json
import math
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

ID = "osm-cameras"
VERSION = "1.0.0"
PLUGIN = {
    "protocol": "flare/1",
    "id": ID,
    "name": "Speed and red light cameras (OpenStreetMap)",
    "version": VERSION,
    "description": ("Fixed speed and red light cameras mapped by OpenStreetMap contributors. "
                    "Coverage is whatever has been mapped: good in some cities, thin in others."),
    "capabilities": {"alerts": True, "report": False, "confirm": False, "notify": False},
    "kinds": ["CAMERA_RED_LIGHT", "CAMERA_SPEED"],
    # [south, west, north, east]: the fifty states.
    "coverage": {"bbox": [18.0, -168.0, 71.5, -66.5]},
    # The file changes monthly; an hour keeps a caller's copy inside the
    # day-long ttl with room to spare.
    "refresh_s": 3600,
    "attribution": {"name": "OpenStreetMap contributors",
                    "url": "https://www.openstreetmap.org/copyright"},
    "contact": os.environ.get("FLARE_CONTACT", "mailto:hello@commutescout.com"),
    "auth": "none",
}
MAX_ALERTS = 500
MAX_RADIUS_M = 100_000
TTL_S = 86_400
RATE_PER_MIN = 120
LABEL = {"CAMERA_SPEED": "Speed camera", "CAMERA_RED_LIGHT": "Red light camera"}


def meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    kx = 111_320 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot((lat2 - lat1) * 111_320, (lon2 - lon1) * kx)


def error(status: int, code: str, message: str, hint: str | None = None) -> JSONResponse:
    body = {"code": code, "message": message}
    if hint:
        body["hint"] = hint
    return JSONResponse({"error": body}, status_code=status)


class Cameras:
    """The file in memory, in one-degree buckets so a lookup reads a few
    hundred records, not all of them."""

    def __init__(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        self.as_of: str = data.get("as_of") or datetime.now(UTC).isoformat()
        self.count = len(data["cameras"])
        self.buckets: dict[tuple[int, int], list[dict]] = {}
        for cam in data["cameras"]:
            key = (math.floor(cam["lat"]), math.floor(cam["lon"]))
            self.buckets.setdefault(key, []).append(cam)

    def near(self, lat: float, lon: float, r: float) -> list[dict]:
        dlat = r / 111_320
        dlon = r / (111_320 * max(0.1, math.cos(math.radians(lat))))
        hits = []
        for by in range(math.floor(lat - dlat), math.floor(lat + dlat) + 1):
            for bx in range(math.floor(lon - dlon), math.floor(lon + dlon) + 1):
                for cam in self.buckets.get((by, bx), ()):
                    d = meters(lat, lon, cam["lat"], cam["lon"])
                    if d <= r:
                        hits.append((d, cam["id"], cam))
        hits.sort(key=lambda h: h[:2])
        return [cam for _, _, cam in hits[:MAX_ALERTS]]


def alert(cam: dict, report_ts: str) -> dict:
    """One camera as a Flare alert record."""
    label = LABEL[cam["kind"]]
    out = {
        "id": f"{ID}:n{cam['id']}",
        "kind": cam["kind"],
        "lat": cam["lat"],
        "lon": cam["lon"],
        "description": f"{label}, limit {cam['mph']} mph." if cam.get("mph") else f"{label}.",
        # A fixed camera has no report time of its own. The start of the
        # current hour keeps the record inside its day-long ttl on every
        # poll without the timestamp changing on each one.
        "report_ts": report_ts,
        "ttl_s": TTL_S,
        "reliability": 0.7,
        "notify": False,
        "source_url": f"https://www.openstreetmap.org/node/{cam['id']}",
    }
    if cam.get("mph"):
        out["extra"] = {"limit_mph": cam["mph"]}
    return out


store = Cameras(Path(os.environ.get("CAMERAS_FILE") or Path(__file__).with_name("cameras.json")))
_buckets: dict[str, list[float]] = {}


def _limited(request: Request) -> bool:
    ip = request.client.host if request.client else "?"
    now = time.monotonic()
    if len(_buckets) > 10_000:
        _buckets.clear()
    hits = [t for t in _buckets.get(ip, []) if now - t < 60]
    if len(hits) >= RATE_PER_MIN:
        _buckets[ip] = hits
        return True
    hits.append(now)
    _buckets[ip] = hits
    return False


async def handshake(_: Request) -> JSONResponse:
    return JSONResponse(PLUGIN, headers={"Cache-Control": "public, max-age=3600"})


async def alerts(request: Request) -> JSONResponse:
    if _limited(request):
        return error(429, "rate_limited", "Slow down.", f"{RATE_PER_MIN} requests a minute.")
    try:
        lat = float(request.query_params["lat"])
        lon = float(request.query_params["lon"])
        r = min(float(request.query_params.get("r", 25_000)), MAX_RADIUS_M)
    except (KeyError, ValueError):
        return error(400, "bad_request", "lat, lon and r (meters) are required.")
    if not (math.isfinite(lat) and math.isfinite(lon) and math.isfinite(r) and r > 0):
        return error(400, "bad_request", "lat, lon and r must be finite numbers.")
    s, w, n, e = PLUGIN["coverage"]["bbox"]
    if not (s - 1 <= lat <= n + 1 and w - 1 <= lon <= e + 1):
        return error(422, "outside_coverage", "That point is outside this plugin's coverage.")
    hour = datetime.now(UTC).replace(minute=0, second=0, microsecond=0).isoformat()
    return JSONResponse({"alerts": [alert(c, hour) for c in store.near(lat, lon, r)],
                         "ttl_s": PLUGIN["refresh_s"], "as_of": store.as_of})


async def status(_: Request) -> JSONResponse:
    return JSONResponse({"ok": True, "version": VERSION, "cameras": store.count,
                         "as_of": store.as_of})


app = Starlette(routes=[
    Route("/flare/v1/handshake", handshake),
    Route("/flare/v1/alerts", alerts),
    Route("/status", status),
])


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8310")))  # noqa: S104
