"""The Flare endpoints of the unofficial Waze relay.

Everything in docs/flare.md that this plugin declares: the handshake, alerts
near a point, a confirmation vote, and, when the operator turns it on, a
report passed through to Waze. The data behind them comes from store.py; the
protocol that fetches it is the port of highway-radar-sabre-plus in waze/.

Run it:

    pip install -r requirements.txt
    python server.py

    python -m ca_roads.flare check http://127.0.0.1:8300
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
from collections.abc import AsyncIterator

import auth
import httpx
import mapping
import sessions as sessions_module
import store as store_module
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from store import CELL_RADIUS_M, Store
from waze.source import WazeSource

VERSION = "1.1.0"
# The United States, Alaska and Hawaii included. Coverage is what the plugin
# will answer for, not what it fetches: it only ever fetches the one-degree
# cells somebody asked about, so a wide box costs nothing on its own.
DEFAULT_BBOX = "18.0,-168.0,71.5,-66.5"
DESCRIPTION = ("Crowd reports from Waze: police, crashes, hazards, jams. "
               "Unofficial, at your own risk.")
MAX_RADIUS_M = 100_000
# A mediated caller asks per grid cell, so one backend covering a lot of
# ground is a lot of requests from one address: a few hundred a minute is
# ordinary and must not be throttled into 429s. Answering costs a dictionary
# lookup, and what actually protects the upstream is the hot-cell limit, not
# this. Abuse still hits a ceiling.
RATE_PER_MIN = int(os.environ.get("WAZE_RATE_PER_MIN") or 600)
HTTP_TIMEOUT_S = 30.0

log = logging.getLogger("waze_relay")


def _bbox(raw: str) -> list[float]:
    """``south,west,north,east`` in decimal degrees."""
    south, west, north, east = (float(p) for p in raw.split(","))
    return [south, west, north, east]


TOKEN = os.environ.get("FLARE_TOKEN") or None
BBOX = _bbox(os.environ.get("WAZE_BBOX") or DEFAULT_BBOX)
REFRESH_S = int(os.environ.get("WAZE_REFRESH_S") or 60)
SHRINK_STEPS = int(os.environ.get("WAZE_SHRINK_STEPS") or 2)
SUB_CELLS = int(os.environ.get("WAZE_SUB_CELLS") or store_module.SUB_CELLS)
HOT_CELLS = int(os.environ.get("WAZE_HOT_CELLS") or store_module.HOT_CELLS)
QUERY_BUDGET_S = float(os.environ.get("WAZE_QUERY_BUDGET_S") or 10)
STATE_FILE = os.environ.get("WAZE_STATE_FILE") or None
# Reporting to Waze is off unless the operator turns it on: the approved plan
# has the public listing carry no reports, and one shared anonymous account
# writing on behalf of anyone at all is the fastest way to lose the read path
# as well. A private deployment can set WAZE_REPORTS=1.
REPORTS = (os.environ.get("WAZE_REPORTS") or "").lower() in ("1", "true", "yes")
# A signed-in phone can hold an upstream session of its own, so its alerts
# are shaped by where it is rather than mixed in with everybody's. Off until
# the apps are ready for it, and bounded when on: see sessions.py for why one
# account per person from one address is not on the table.
USER_SESSIONS = (os.environ.get("WAZE_USER_SESSIONS") or "").lower() in ("1", "true", "yes")
USER_MAX = int(os.environ.get("WAZE_USER_SESSIONS_MAX") or sessions_module.MAX_CONCURRENT)
USER_IDLE_S = float(os.environ.get("WAZE_USER_IDLE_S") or sessions_module.IDLE_S)
# refresh_s is the hint for a mediated caller polling per grid cell once a
# minute. A phone holding its own session is a different animal: its cache
# goes stale in twelve seconds and it is moving, so it is told to come back
# at the protocol floor instead of caching a personal answer for a minute.
USER_POLL_S = int(os.environ.get("WAZE_USER_POLL_S") or 15)

PLUGIN = {
    "protocol": "flare/1",
    "id": os.environ.get("FLARE_ID") or "wz-flare",
    "name": os.environ.get("FLARE_NAME") or "Unofficial Waze relay (community)",
    "description": DESCRIPTION,
    "version": VERSION,
    "capabilities": {"alerts": True, "report": REPORTS, "confirm": True, "notify": False},
    "kinds": mapping.KINDS if not REPORTS else sorted(
        set(mapping.KINDS) | set(mapping.REPORTABLE_KINDS)),
    "coverage": {"bbox": BBOX},
    "refresh_s": REFRESH_S,
    "attribution": {
        "name": "Unofficial Waze relay (community)",
        "url": os.environ.get("FLARE_ATTRIBUTION_URL") or "https://commutescout.com/plugins",
    },
    "contact": os.environ.get("FLARE_CONTACT") or "https://commutescout.com/contact",
    "auth": "bearer" if TOKEN else "none",
}
if USER_SESSIONS:
    # A plugin extension, not part of flare/1: an app feature-detects it
    # here rather than hardcoding the path, and its absence means off.
    PLUGIN["extensions"] = {"user_sessions": {
        "path": "/flare/v1/me/alerts", "auth": "firebase",
        "idle_s": int(USER_IDLE_S), "max_concurrent": USER_MAX,
        "poll_s": USER_POLL_S,
    }}

store: Store | None = None
users: sessions_module.UserSessions | None = None
auth_client: httpx.AsyncClient | None = None
_buckets: dict[str, list[float]] = {}


def error(status: int, code: str, message: str, hint: str | None = None) -> JSONResponse:
    body = {"code": code, "message": message}
    if hint:
        body["hint"] = hint
    return JSONResponse({"error": body}, status_code=status)


def _authorized(request: Request) -> bool:
    return not TOKEN or request.headers.get("authorization") == f"Bearer {TOKEN}"


def _limited(request: Request) -> bool:
    who = request.client.host if request.client else "?"
    now = time.monotonic()
    hits = [t for t in _buckets.get(who, []) if now - t < 60]
    if len(hits) >= RATE_PER_MIN:
        _buckets[who] = hits
        return True
    hits.append(now)
    _buckets[who] = hits
    return False


async def handshake(_: Request) -> JSONResponse:
    return JSONResponse(PLUGIN, headers={"Cache-Control": "public, max-age=3600"})


async def alerts(request: Request) -> JSONResponse:
    if not _authorized(request):
        return error(401, "unauthorized", "This plugin wants a bearer token.")
    if _limited(request):
        return error(429, "rate_limited", "Slow down.",
                     f"{RATE_PER_MIN} requests a minute.")
    try:
        lat = float(request.query_params["lat"])
        lon = float(request.query_params["lon"])
        radius = min(float(request.query_params.get("r", CELL_RADIUS_M)), MAX_RADIUS_M)
    except (KeyError, ValueError):
        return error(400, "bad_request", "lat, lon and r (meters) are required.")
    if not store.in_coverage(lat, lon):
        return error(422, "outside_coverage",
                     "That point is outside this plugin's coverage.",
                     "See coverage.bbox in the handshake.")
    store.want(lat, lon)
    return JSONResponse({"alerts": store.near(lat, lon, radius),
                         "ttl_s": REFRESH_S, "as_of": store.as_of})


async def my_alerts(request: Request) -> JSONResponse:
    """Alerts for one signed-in person, from a session of their own.

    Answers from that person's cache at once and never waits on the
    upstream; a refresh runs behind the answer when the cache is stale or
    they have moved. When every session is taken, this falls back to the
    shared feed and says so, rather than refusing.
    """
    if not USER_SESSIONS:
        return error(404, "bad_request", "This plugin does not run per-user sessions.")
    if _limited(request):
        return error(429, "rate_limited", "Slow down.",
                     f"{RATE_PER_MIN} requests a minute.")
    key = await auth.verify(auth.bearer(request.headers.get("authorization")),
                            auth_client)
    if key is None:
        return error(401, "unauthorized", "A signed-in token is required here.",
                     "Use /flare/v1/alerts for the shared feed.")
    try:
        lat = sessions_module.snap(float(request.query_params["lat"]))
        lon = sessions_module.snap(float(request.query_params["lon"]))
        radius = min(float(request.query_params.get("r", CELL_RADIUS_M)), MAX_RADIUS_M)
    except (KeyError, ValueError):
        return error(400, "bad_request", "lat, lon and r (meters) are required.")
    if not store.in_coverage(lat, lon):
        return error(422, "outside_coverage",
                     "That point is outside this plugin's coverage.")
    session = await users.get(key) if users is not None else None
    if session is None:
        # Every session is taken, or the registry never came up. Either way
        # the shared feed is the honest fallback; nobody gets an error page
        # because the relay is busy.
        store.want(lat, lon)
        return JSONResponse({"alerts": store.near(lat, lon, radius), "ttl_s": USER_POLL_S,
                             "as_of": store.as_of, "session": "shared"})
    session.trigger_refresh_if_stale(lat, lon, radius)
    return JSONResponse({"alerts": session.alerts(lat, lon, radius, store.to_record),
                         "ttl_s": USER_POLL_S, "as_of": session.as_of, "session": "user"})


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
    alert_id = str(body.get("alert_id") or "")
    if store.record_by_id(alert_id) is None:
        return error(404, "unknown_alert", "No alert by that id.")
    # The vote stays here: it raises the count and the confidence this plugin
    # reports, and enough "not there" votes hide the alert. Waze is not told.
    store.votes.add(alert_id, vote, str(body.get("reporter") or "anonymous")[:64])
    record = store.record_by_id(alert_id)
    return JSONResponse(record if record is not None else {"id": alert_id, "hidden": True})


async def report(request: Request) -> JSONResponse:
    if not REPORTS:
        return error(404, "bad_request", "This plugin does not take reports.")
    if not _authorized(request):
        return error(401, "unauthorized", "This plugin wants a bearer token.")
    if _limited(request):
        return error(429, "rate_limited", "Slow down.")
    try:
        body = await request.json()
    except ValueError:
        return error(400, "bad_request", "JSON body required.")
    subtype = mapping.report_subtype(str(body.get("kind") or ""))
    if subtype is None:
        return error(422, "bad_request", "Waze takes no report of that kind.",
                     "See kinds in the handshake.")
    try:
        lat, lon = float(body["lat"]), float(body["lon"])
    except (KeyError, TypeError, ValueError):
        return error(400, "bad_request", "lat and lon are required.")
    if not store.in_coverage(lat, lon):
        return error(422, "outside_coverage", "That point is outside this plugin's coverage.")
    heading = body.get("heading_deg")
    heading = float(heading) % 360 if heading is not None else 0.0
    member, number = subtype
    try:
        result = await store.source.submit_report(
            lat=lat, lon=lon, heading_deg=heading, member=member, subtype_number=number)
    except Exception as exc:  # noqa: BLE001 - the upstream is not ours to trust
        log.warning("report failed: %s: %s", type(exc).__name__, exc)
        return error(503, "unavailable", "The upstream did not take the report.")
    if not result.accepted:
        return error(422, "bad_request", result.error or "The upstream refused the report.")
    return JSONResponse({"id": f"wz:{result.uuid}" if result.uuid else "wz:accepted",
                         "queued": True}, status_code=202)


async def status(_: Request) -> JSONResponse:
    body = {"id": PLUGIN["id"], "version": VERSION, **store.status()}
    if users is not None:
        body["user_sessions"] = users.status()
    return JSONResponse(body)


async def healthz(_: Request) -> JSONResponse:
    return JSONResponse({"ok": True})


@contextlib.asynccontextmanager
async def lifespan(_: Starlette) -> AsyncIterator[None]:
    global store, users, auth_client

    client = httpx.AsyncClient(timeout=HTTP_TIMEOUT_S, follow_redirects=False)
    source = WazeSource(client, shrink_steps=SHRINK_STEPS,
                        query_budget_s=QUERY_BUDGET_S, state_path=STATE_FILE)
    store = Store(source, bbox=BBOX, refresh_s=REFRESH_S, sub_cells=SUB_CELLS,
                  hot_cells=HOT_CELLS)
    if USER_SESSIONS:
        auth_client = httpx.AsyncClient(timeout=15.0)
        # The day's account budget is shared with the relay, so several user
        # sessions cannot each mint their own allowance.
        users = sessions_module.UserSessions(
            max_concurrent=USER_MAX, idle_s=USER_IDLE_S, budget=source.budget,
            shrink_steps=SHRINK_STEPS, query_budget_s=QUERY_BUDGET_S,
            client_factory=lambda: httpx.AsyncClient(timeout=HTTP_TIMEOUT_S,
                                                     follow_redirects=False))
    task = asyncio.create_task(store.run())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        if users is not None:
            await users.close_all()
        if auth_client is not None:
            await auth_client.aclose()
        await client.aclose()


app = Starlette(lifespan=lifespan, routes=[
    Route("/flare/v1/handshake", handshake),
    Route("/flare/v1/alerts", alerts),
    Route("/flare/v1/me/alerts", my_alerts),
    Route("/flare/v1/confirm", confirm, methods=["POST"]),
    Route("/flare/v1/report", report, methods=["POST"]),
    Route("/status", status),
    Route("/healthz", healthz),
])


def main() -> None:  # pragma: no cover
    import uvicorn

    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                        format="%(levelname)s %(name)s %(message)s")
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8300")))  # noqa: S104


if __name__ == "__main__":  # pragma: no cover
    main()
