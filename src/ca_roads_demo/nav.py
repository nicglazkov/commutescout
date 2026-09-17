"""What the mobile app needs from the server that the web map did not.

- ``POST /api/nav/route``: the navigation router. The app's navigation
  SDK (Ferrostar) posts a Valhalla request here instead of to Stadia,
  so the Stadia key never ships in an app binary, every route carries
  the same full-closure exclusions the web planner applies (plugin road
  closures included), and the traffic profile is one setting here when
  the plan changes (``NAV_COSTING=auto_traffic``). The answer is
  Stadia's OSRM-format response, untouched, which Ferrostar parses.
- ``GET /api/tiles/style.json`` and ``GET /api/tiles/{style}/{z}/{x}/{y}``:
  a raster base map for the app, proxied so the key stays here and the
  edge caches a day of tiles.
"""

from __future__ import annotations

import json
import os
import time

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ca_roads.budget import UPSTREAM
from ca_roads.stadia import auth_headers
from ca_roads_demo import routing

ROUTE_URL = "https://api.stadiamaps.com/route/v1"
# A report placed within this distance of a road snaps onto it; further
# away it stays where the person put it (a field, a trailhead, a beach).
SNAP_MAX_M = 60.0
TILE_URL = "https://tiles.stadiamaps.com/tiles/{style}/{z}/{x}/{y}{scale}.png"
USER_AGENT = "commutescout.com drive app (https://commutescout.com/developers)"
PUBLIC_BASE = os.environ.get("DEMO_URL", "https://commutescout.com").rstrip("/")

NAV_COSTING = os.environ.get("NAV_COSTING", "auto")
STADIA_NAV_DAILY = int(os.environ.get("STADIA_NAV_DAILY", "6000"))
STADIA_APP_TILES_DAILY = int(os.environ.get("STADIA_APP_TILES_DAILY", "150000"))
TILE_STYLES = ("alidade_smooth", "alidade_smooth_dark", "outdoors")
ATTRIBUTION = ("&copy; <a href=\"https://stadiamaps.com/\">Stadia Maps</a> "
               "&copy; <a href=\"https://openmaptiles.org/\">OpenMapTiles</a> "
               "&copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a> "
               "contributors")

_TILES: dict[str, tuple[float, bytes]] = {}
_TILE_TTL = 3600.0
_TILE_MAX = 1500


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
        markers, *_ = await demo.build_markers(box, {"closure", "plugin"})
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


def style_json(base: str = PUBLIC_BASE, style: str = "alidade_smooth") -> dict:
    """A MapLibre style for one of TILE_STYLES: the apps pick light,
    dark or outdoors and every tile still comes through the proxy."""
    if style not in TILE_STYLES:
        style = "alidade_smooth"
    return {
        "version": 8,
        "name": f"CommuteScout {style}",
        "sources": {"base": {
            "type": "raster", "tileSize": 256,
            "tiles": [f"{base}/api/tiles/{style}/{{z}}/{{x}}/{{y}}@2x.png"],
            "minzoom": 0, "maxzoom": 18, "attribution": ATTRIBUTION,
        }},
        "layers": [{"id": "base", "type": "raster", "source": "base"}],
    }


async def api_tile_style(request: Request):
    style = request.query_params.get("style") or "alidade_smooth"
    if style not in TILE_STYLES:
        return JSONResponse({"error": {
            "code": "unknown_style",
            "message": "style must be one of " + ", ".join(TILE_STYLES)}}, status_code=400)
    return JSONResponse(style_json(style=style), headers={"Cache-Control": "public, max-age=3600"})


async def api_tile(request: Request):
    from ca_roads_demo import app as demo

    style = request.path_params["style"]
    if style not in TILE_STYLES:
        return Response(status_code=404)
    try:
        z, x = int(request.path_params["z"]), int(request.path_params["x"])
        yfile = request.path_params["yfile"]
        scale = "@2x" if yfile.endswith("@2x.png") else ""
        y = int(yfile.removesuffix("@2x.png").removesuffix(".png"))
    except (KeyError, ValueError):
        return Response(status_code=404)
    if not (0 <= z <= 18 and 0 <= x < 2 ** z and 0 <= y < 2 ** z):
        return Response(status_code=404)
    key = f"{style}/{z}/{x}/{y}{scale}"
    now = time.monotonic()
    hit = _TILES.get(key)
    cache = {"Cache-Control": "public, max-age=86400, stale-while-revalidate=604800"}
    if hit and now - hit[0] < _TILE_TTL:
        return Response(hit[1], media_type="image/png", headers=cache)
    api_key = os.environ.get("STADIA_API_KEY", "").strip()
    if not api_key:
        return Response(status_code=404)
    if (demo._client_over_daily(request, "tiles")
            or not UPSTREAM.allow("stadia-app-tiles", STADIA_APP_TILES_DAILY)):
        return Response(status_code=429, headers={"Retry-After": "3600"})
    road = demo.tools.get_road()
    try:
        resp = await road.client.get(TILE_URL.format(style=style, z=z, x=x, y=y, scale=scale),
                                     headers=auth_headers(api_key, USER_AGENT), timeout=10.0)
    except Exception:  # noqa: BLE001
        return Response(status_code=502)
    if resp.status_code != 200:
        return Response(status_code=resp.status_code if resp.status_code in (404, 429) else 502)
    if len(_TILES) >= _TILE_MAX:
        for k, _ in sorted(_TILES.items(), key=lambda kv: kv[1][0])[: _TILE_MAX // 4]:
            _TILES.pop(k, None)
    _TILES[key] = (now, resp.content)
    return Response(resp.content, media_type="image/png", headers=cache)
