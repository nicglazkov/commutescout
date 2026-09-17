"""A complete Flare plugin in one file: the reference for anyone who
wants to run a source, public or private.

It implements every endpoint in docs/flare.md (handshake, alerts by
radius, report, confirm) over an in-memory store, passes
``python -m ca_roads.flare check``, and is the template a real source
starts from: replace ``Store`` with your data (a database, an upstream
feed, a SABRE plugin's sources ported over) and keep the HTTP layer.

Run it:

    pip install starlette uvicorn
    FLARE_TOKEN=optional-secret python server.py

Then check it:

    python -m ca_roads.flare check http://127.0.0.1:8300 [--token optional-secret]

Deploy behind HTTPS (a reverse proxy, Cloud Run, fly.io, a Raspberry
Pi with Caddy) and hand CommuteScout the manifest, or add it as a
private source in the app.
"""

from __future__ import annotations

import math
import os
import secrets
import time
from datetime import UTC, datetime, timedelta

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

PLUGIN = {
    "protocol": "flare/1",
    "id": os.environ.get("FLARE_ID", "example"),
    "name": os.environ.get("FLARE_NAME", "Example Flare plugin"),
    "version": "1.0.0",
    "capabilities": {"alerts": True, "report": True, "confirm": True, "notify": True},
    "kinds": ["POLICE_VISIBLE", "POLICE_HIDING", "CRASH_MINOR", "CRASH_MAJOR",
              "HAZARD_ON_ROAD", "HAZARD_SHOULDER_CAR", "ROAD_CLOSED", "LANE_CLOSED",
              "JAM_HEAVY", "WEATHER_FOG", "CHAINS_REQUIRED", "OTHER"],
    # [south, west, north, east]; California by default.
    "coverage": {"bbox": [32.5, -124.5, 42.0, -114.1]},
    "refresh_s": 60,
    "attribution": {"name": os.environ.get("FLARE_NAME", "Example Flare plugin"),
                    "url": "https://commutescout.com/developers"},
    "contact": os.environ.get("FLARE_CONTACT", "mailto:you@example.com"),
    "auth": "bearer" if os.environ.get("FLARE_TOKEN") else "none",
}
TOKEN = os.environ.get("FLARE_TOKEN")
KINDS = set(PLUGIN["kinds"])
TTL_S = {"POLICE": 1800, "CRASH": 2700, "HAZARD": 3600, "ROAD_CLOSED": 7200,
         "LANE_CLOSED": 5400, "JAM": 1200, "WEATHER": 3600, "CHAINS": 7200, "OTHER": 1800}
MAX_ALERTS = 500
MAX_RADIUS_M = 100_000
RATE_PER_MIN = 60


def ttl_for(kind: str) -> int:
    for prefix, ttl in TTL_S.items():
        if kind.startswith(prefix):
            return ttl
    return TTL_S["OTHER"]


def meters(lat1, lon1, lat2, lon2) -> float:
    kx = 111_320 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot((lat2 - lat1) * 111_320, (lon2 - lon1) * kx)


def error(status: int, code: str, message: str, hint: str | None = None) -> JSONResponse:
    body = {"code": code, "message": message}
    if hint:
        body["hint"] = hint
    return JSONResponse({"error": body}, status_code=status)


class Store:
    """Alerts in memory. Swap this for your data; keep the shape."""

    def __init__(self) -> None:
        self.alerts: dict[str, dict] = {}
        self.votes: dict[str, set[str]] = {}

    def _expire(self) -> None:
        now = datetime.now(UTC)
        for aid, a in list(self.alerts.items()):
            anchor = datetime.fromisoformat(a.get("confirm_ts") or a["report_ts"])
            if anchor + timedelta(seconds=a["ttl_s"]) < now:
                self.alerts.pop(aid, None)
                self.votes.pop(aid, None)

    def near(self, lat: float, lon: float, r: float) -> list[dict]:
        self._expire()
        hits = [a for a in self.alerts.values() if meters(lat, lon, a["lat"], a["lon"]) <= r]
        hits.sort(key=lambda a: meters(lat, lon, a["lat"], a["lon"]))
        return hits[:MAX_ALERTS]

    def add(self, kind: str, lat: float, lon: float, ts: str, description: str,
            heading: float | None, reporter: str) -> dict:
        aid = f"{PLUGIN['id']}:{secrets.token_hex(5)}"
        a = {"id": aid, "kind": kind, "lat": lat, "lon": lon, "report_ts": ts,
             "n_confirmations": 0, "reliability": 0.5, "ttl_s": ttl_for(kind),
             "notify": kind.startswith(("CRASH", "ROAD_CLOSED", "HAZARD"))}
        if description:
            a["description"] = description[:200]
        if heading is not None:
            a["heading_deg"] = heading
        self.alerts[aid] = a
        self.votes[aid] = {reporter}
        return a

    def confirm(self, aid: str, vote: str, reporter: str) -> dict | None:
        a = self.alerts.get(aid)
        if not a:
            return None
        if reporter in self.votes.setdefault(aid, set()):
            return a
        self.votes[aid].add(reporter)
        if vote == "up":
            a["n_confirmations"] += 1
            a["confirm_ts"] = datetime.now(UTC).isoformat()
            a["reliability"] = min(1.0, 0.5 + 0.15 * a["n_confirmations"])
        else:
            a["reliability"] = max(0.0, a["reliability"] - 0.2)
            if a["reliability"] <= 0.0:
                self.alerts.pop(aid, None)
                return a
        return a


store = Store()
_buckets: dict[str, list[float]] = {}


def _limited(request: Request) -> bool:
    ip = request.client.host if request.client else "?"
    now = time.monotonic()
    hits = [t for t in _buckets.get(ip, []) if now - t < 60]
    if len(hits) >= RATE_PER_MIN:
        _buckets[ip] = hits
        return True
    hits.append(now)
    _buckets[ip] = hits
    return False


def _authorized(request: Request) -> bool:
    if not TOKEN:
        return True
    return request.headers.get("authorization") == f"Bearer {TOKEN}"


async def handshake(_: Request) -> JSONResponse:
    return JSONResponse(PLUGIN, headers={"Cache-Control": "public, max-age=3600"})


async def alerts(request: Request) -> JSONResponse:
    if not _authorized(request):
        return error(401, "unauthorized", "This plugin wants a bearer token.")
    if _limited(request):
        return error(429, "rate_limited", "Slow down.", "Sixty requests a minute.")
    try:
        lat = float(request.query_params["lat"])
        lon = float(request.query_params["lon"])
        r = min(float(request.query_params.get("r", 25_000)), MAX_RADIUS_M)
    except (KeyError, ValueError):
        return error(400, "bad_request", "lat, lon and r (meters) are required.")
    s, w, n, e = PLUGIN["coverage"]["bbox"]
    if not (s - 1 <= lat <= n + 1 and w - 1 <= lon <= e + 1):
        return error(422, "outside_coverage", "That point is outside this plugin's coverage.")
    return JSONResponse({"alerts": store.near(lat, lon, r), "ttl_s": PLUGIN["refresh_s"],
                         "as_of": datetime.now(UTC).isoformat()})


async def report(request: Request) -> JSONResponse:
    if not _authorized(request):
        return error(401, "unauthorized", "This plugin wants a bearer token.")
    if _limited(request):
        return error(429, "rate_limited", "Slow down.")
    try:
        body = await request.json()
    except ValueError:
        return error(400, "bad_request", "JSON body required.")
    kind = body.get("kind")
    if kind not in KINDS:
        return error(422, "bad_request", "kind is not one this plugin serves.",
                     "See kinds in the handshake.")
    try:
        lat, lon = float(body["lat"]), float(body["lon"])
    except (KeyError, TypeError, ValueError):
        return error(400, "bad_request", "lat and lon are required.")
    heading = body.get("heading_deg")
    heading = float(heading) % 360 if heading is not None else None
    ts = body.get("ts") or datetime.now(UTC).isoformat()
    reporter = str(body.get("reporter") or "anonymous")[:64]
    a = store.add(kind, lat, lon, ts, str(body.get("description") or ""), heading, reporter)
    return JSONResponse({"id": a["id"], "alert": a}, status_code=201)


async def confirm(request: Request) -> JSONResponse:
    if not _authorized(request):
        return error(401, "unauthorized", "This plugin wants a bearer token.")
    try:
        body = await request.json()
    except ValueError:
        return error(400, "bad_request", "JSON body required.")
    vote = body.get("vote")
    if vote not in ("up", "gone"):
        return error(400, "bad_request", "vote must be up or gone.")
    a = store.confirm(str(body.get("alert_id") or ""), vote, str(body.get("reporter") or "?"))
    if a is None:
        return error(404, "unknown_alert", "No alert by that id.")
    return JSONResponse(a)


app = Starlette(routes=[
    Route("/flare/v1/handshake", handshake),
    Route("/flare/v1/alerts", alerts),
    Route("/flare/v1/report", report, methods=["POST"]),
    Route("/flare/v1/confirm", confirm, methods=["POST"]),
])


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8300")))
