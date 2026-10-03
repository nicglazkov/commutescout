"""What the mobile app needs from the server that the web map did not.

- ``POST /api/nav/route``: the navigation router. The app's navigation
  SDK (Ferrostar) posts a Valhalla request here instead of to Stadia,
  so the Stadia key never ships in an app binary, every route carries
  the same full-closure exclusions the web planner applies (plugin road
  closures included), and the traffic profile is one setting here when
  the plan changes (``NAV_COSTING=auto_traffic``). The answer is
  Stadia's OSRM-format response, untouched, which Ferrostar parses.
- ``GET /api/speedlimit``: the posted limit on the road ahead, for the
  speedometer when no trip is running.
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import time

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ca_roads.budget import UPSTREAM
from ca_roads.stadia import auth_headers
from ca_roads_demo import flare_sources, routing

ROUTE_URL = "https://api.stadiamaps.com/route/v1"
# A report placed within this distance of a road snaps onto it; further
# away it stays where the person put it (a field, a trailhead, a beach).
SNAP_MAX_M = 60.0
USER_AGENT = "commutescout.com drive app (https://commutescout.com/developers)"

NAV_COSTING = os.environ.get("NAV_COSTING", "auto")
# Sized against the purchased Stadia plan, not against what the service
# could physically serve. A nav, route, speed-limit or snap request
# costs about 20 credits and a static map tile about 1, so the defaults
# here, in app.py and in roadsnap.py (300 nav, 400 speed limits, 300
# road snaps, 200 planner routes, 4,000 tiles) come to 28,000 credits a
# day, about 840,000 a month against a 1,000,000 allowance; tests/
# test_budget.py adds them up. Nothing joins without lowering one. Raise them
# with the environment variables when real usage justifies it, and set
# the hard cap in the Stadia dashboard too: these counters live in the
# process and a deploy grants the whole day again.
STADIA_NAV_DAILY = int(os.environ.get("STADIA_NAV_DAILY", "300"))
# Posted speed limits for the speedometer while driving with no trip:
# one short route a minute per moving phone at most, cached by road
# stretch, under its own daily budget.
STADIA_LIMIT_DAILY = int(os.environ.get("STADIA_LIMIT_DAILY", "400"))


def _locations(raw) -> list[dict] | None:
    if not isinstance(raw, list) or not 2 <= len(raw) <= 10:
        return None
    out = []
    for p in raw:
        if not isinstance(p, dict):
            return None
        try:
            lat, lon = float(p.get("lat")), float(p.get("lon"))
        except (TypeError, ValueError):
            return None
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        keep = {k: v for k, v in p.items()
                if k in ("lat", "lon", "type", "heading", "heading_tolerance", "radius",
                         "preferred_side", "waypoint_name")}
        keep["lat"], keep["lon"] = lat, lon
        out.append(keep)
    return out


def nav_body(body: dict, locations: list[dict], exclusions: list[dict]) -> dict:
    """Stadia's request: the app's body with the parts we own replaced.
    The profile is ours (the traffic flip), exclusions are ours, and
    two-point trips ask for alternates so the app can offer a choice."""
    out = {k: v for k, v in body.items()
           if k in ("format", "filters", "banner_instructions", "voice_instructions",
                    "units", "language", "directions_options", "costing_options",
                    "date_time", "alternates", "exclude_polygons")}
    out["locations"] = locations
    out["costing"] = NAV_COSTING
    out.setdefault("format", "osrm")
    if len(locations) == 2 and "alternates" not in out:
        out["alternates"] = 2
    if exclusions:
        out["exclude_locations"] = exclusions
    return out


async def api_nav_route(request: Request):
    from ca_roads_demo import app as demo

    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = None
    if not isinstance(body, dict):
        return JSONResponse({"error": "JSON body required"}, status_code=400)
    locations = _locations(body.get("locations"))
    if not locations:
        return JSONResponse({"error": "locations: 2 to 10 {lat, lon} points"},
                            status_code=400)
    api_key = os.environ.get("STADIA_API_KEY", "").strip()
    if not api_key:
        return JSONResponse({"error": "navigation is not configured"}, status_code=503)
    if demo._client_over_daily(request, "nav"):
        return demo._daily_cap_response()
    if not UPSTREAM.allow("stadia-nav", STADIA_NAV_DAILY):
        return JSONResponse({"error": "navigation budget spent for today"}, status_code=503)
    lats = [p["lat"] for p in locations]
    lons = [p["lon"] for p in locations]
    box = (max(-90.0, min(lats) - 0.25), max(-180.0, min(lons) - 0.25),
           min(90.0, max(lats) + 0.25), min(180.0, max(lons) + 0.25))
    exclusions: list[dict] = []
    try:
        near = flare_sources.snap_point(locations[0]["lat"], locations[0]["lon"])
        markers, *_ = await demo.build_markers(box, {"closure", "plugin"}, near=near)
        exclusions = routing.exclusions(markers)
    except Exception:  # noqa: BLE001 - a route without exclusions beats no route
        pass
    road = demo.tools.get_road()
    upstream = nav_body(body, locations, exclusions)
    try:
        resp = await road.client.post(ROUTE_URL, json=upstream,
                                      headers=auth_headers(api_key, USER_AGENT), timeout=25.0)
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": "the router did not answer"}, status_code=502)
    if resp.status_code >= 400 and exclusions:
        # An exclusion can make a trip unroutable (closure at the door).
        upstream.pop("exclude_locations", None)
        try:
            resp = await road.client.post(ROUTE_URL, json=upstream,
                                          headers=auth_headers(api_key, USER_AGENT),
                                          timeout=25.0)
        except Exception:  # noqa: BLE001
            return JSONResponse({"error": "the router did not answer"}, status_code=502)
    media = resp.headers.get("content-type", "application/json")
    if resp.status_code < 400:
        # The drive is about to start along this line: keep it warm for
        # the relay so the community alerts are there before the driver.
        with contextlib.suppress(Exception):
            from ca_roads_demo.valhalla import trip_points
            trip = json.loads(resp.content).get("trip") or {}
            flare_sources.poller.note_route(trip_points(trip))
    return Response(resp.content, status_code=resp.status_code, media_type=media,
                    headers={"Cache-Control": "no-store",
                             "X-Nav-Costing": NAV_COSTING,
                             "X-Nav-Exclusions": str(len(exclusions))})


def _meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math

    k = math.cos(math.radians((lat1 + lat2) / 2))
    dx = (lon2 - lon1) * 111_320 * k
    dy = (lat2 - lat1) * 110_540
    return math.hypot(dx, dy)


def nearest_road(trip: dict) -> dict | None:
    """The road point a zero-length route (both ends at the click) starts
    from: {lat, lon, road}, or None. The plan has no locate endpoint, but
    a route's shape begins at the correlated point and its first maneuver
    names the street."""
    from ca_roads_demo.valhalla import decode_polyline6

    legs = (trip or {}).get("legs") or []
    if not legs:
        return None
    pts = decode_polyline6(legs[0].get("shape") or "")
    if not pts:
        return None
    names = ((legs[0].get("maneuvers") or [{}])[0].get("street_names") or [])
    return {"lat": round(pts[0][0], 6), "lon": round(pts[0][1], 6),
            "road": names[0] if names else None}


async def api_snap(request: Request):
    """Where a report goes: the nearest road point when the click is
    within SNAP_MAX_M of one, else the click itself. Never refuses a
    spot; the answer says whether it moved and by how much."""
    from ca_roads_demo import app as demo

    try:
        lat, lon = float(request.query_params["lat"]), float(request.query_params["lon"])
    except (KeyError, ValueError):
        return JSONResponse({"error": "lat and lon required"}, status_code=400)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return JSONResponse({"error": "lat and lon out of range"}, status_code=400)
    same = {"snapped": False, "lat": lat, "lon": lon, "road": None, "distance_m": 0}
    api_key = os.environ.get("STADIA_API_KEY", "").strip()
    if not api_key or demo._client_over_daily(request, "snap") \
            or not UPSTREAM.allow("stadia-nav", STADIA_NAV_DAILY):
        return JSONResponse(same, headers={"Cache-Control": "no-store"})
    road = demo.tools.get_road()
    here = {"lat": lat, "lon": lon}
    try:
        resp = await road.client.post(
            ROUTE_URL, json={"locations": [here, dict(here)], "costing": "auto"},
            headers=auth_headers(api_key, USER_AGENT), timeout=10.0)
        if resp.status_code >= 400:
            return JSONResponse(same, headers={"Cache-Control": "no-store"})
        near = nearest_road(json.loads(resp.content).get("trip") or {})
    except Exception:  # noqa: BLE001 - a report without a snap beats no report
        return JSONResponse(same, headers={"Cache-Control": "no-store"})
    if not near:
        return JSONResponse(same, headers={"Cache-Control": "no-store"})
    d = round(_meters(lat, lon, near["lat"], near["lon"]), 1)
    if d > SNAP_MAX_M:
        return JSONResponse(same, headers={"Cache-Control": "no-store"})
    return JSONResponse({"snapped": True, **near, "distance_m": d},
                        headers={"Cache-Control": "no-store"})


# ---------------------------------------------------------------- speed limit

# (asked at, answer, how long it holds): a known limit for an hour, a
# failed ask for two minutes.
_LIMITS: dict[tuple, tuple[float, dict, float]] = {}
_LIMIT_TTL = 3600.0
_LIMIT_FAIL_TTL = 120.0
_LIMIT_MAX = 5000


def _ahead(lat: float, lon: float, heading: float, meters: float) -> dict:
    """A point `meters` along `heading` from (lat, lon)."""
    k = math.cos(math.radians(lat)) or 1e-6
    return {"lat": round(lat + meters * math.cos(math.radians(heading)) / 110_540, 6),
            "lon": round(lon + meters * math.sin(math.radians(heading)) / (111_320 * k), 6)}


def limit_from_osrm(body: dict, within_m: float = 200.0) -> dict:
    """The posted limit on the road just ahead, from the maxspeed
    annotation of an OSRM-format route: the first known value within
    `within_m` of the start. {} when the map does not say."""
    try:
        leg = body["routes"][0]["legs"][0]
        ann = leg.get("annotation") or {}
        speeds, dists = ann.get("maxspeed") or [], ann.get("distance") or []
    except (KeyError, IndexError, TypeError):
        return {}
    gone = 0.0
    for i, m in enumerate(speeds):
        if gone > within_m:
            break
        if isinstance(m, dict) and not m.get("unknown") and m.get("speed"):
            kmh = float(m["speed"]) * (1.609344 if m.get("unit") == "mph" else 1.0)
            return {"kmh": round(kmh), "mph": round(kmh / 1.609344)}
        gone += float(dists[i]) if i < len(dists) else 0.0
    return {}


async def api_speedlimit(request: Request):
    """GET /api/speedlimit?lat=&lon=&heading= : the posted limit on the
    road ahead, for the speedometer when no trip is running (a trip
    carries its own). Empty when unknown, never an error the app has to
    handle. Cached by a 100 m cell and a 45 degree heading sector."""
    from ca_roads_demo import app as demo

    try:
        lat, lon = float(request.query_params["lat"]), float(request.query_params["lon"])
        heading = float(request.query_params.get("heading", "0")) % 360
    except (KeyError, ValueError):
        return JSONResponse({"error": "lat and lon required"}, status_code=400)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return JSONResponse({"error": "lat and lon out of range"}, status_code=400)
    headers = {"Cache-Control": "private, max-age=30"}
    key = (round(lat, 3), round(lon, 3), int(heading // 45))
    hit = _LIMITS.get(key)
    now = time.monotonic()
    if hit and now - hit[0] < hit[2]:
        return JSONResponse(hit[1], headers={**headers, "X-Cache": "hit"})
    api_key = os.environ.get("STADIA_API_KEY", "").strip()
    if not api_key or demo._client_over_daily(request, "speedlimit") \
            or not UPSTREAM.allow("stadia-limit", STADIA_LIMIT_DAILY):
        return JSONResponse({}, headers=headers)
    road = demo.tools.get_road()
    try:
        resp = await road.client.post(
            ROUTE_URL,
            json={"locations": [{"lat": lat, "lon": lon}, _ahead(lat, lon, heading, 350)],
                  "costing": "auto", "format": "osrm",
                  "filters": {"action": "include",
                              "attributes": ["shape_attributes.speed_limit",
                                             "shape_attributes.length"]}},
            headers=auth_headers(api_key, USER_AGENT), timeout=10.0)
        out = limit_from_osrm(json.loads(resp.content)) if resp.status_code < 400 else {}
        ttl = _LIMIT_TTL if resp.status_code < 400 else _LIMIT_FAIL_TTL
    except Exception:  # noqa: BLE001 - a blank limit beats an error on the dashboard
        # A timeout or a dropped connection is not "the map does not
        # say": it is remembered only briefly, so the next car on this
        # stretch asks again.
        out, ttl = {}, _LIMIT_FAIL_TTL
    if len(_LIMITS) >= _LIMIT_MAX:
        _LIMITS.pop(next(iter(_LIMITS)))
    _LIMITS[key] = (now, out, ttl)
    return JSONResponse(out, headers=headers)
