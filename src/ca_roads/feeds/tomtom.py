"""TomTom traffic flow: actual current speeds versus free-flow.

Activated by the TOMTOM_API_KEY environment variable; without it every
call returns None and route reports simply omit the traffic section. The
flow-segment endpoint answers for a single point, so callers sample a few
points along a corridor; results cache for a minute per rounded point.
Free tier: 2,500 requests/day, plenty at this project's scale.
"""

from __future__ import annotations

import asyncio
import os
import time

import httpx

from ca_roads.budget import UPSTREAM

FLOW_URL = (
    "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
)
TIMEOUT_SECONDS = 8.0
TTL_SECONDS = 60.0

_cache: dict[tuple[float, float], tuple[float, dict | None]] = {}
# TomTom's free tier is 2,500 non-tile requests a day for the whole
# key; past this the flow layer goes grey instead of the key going
# dark for everyone.
TOMTOM_FLOW_DAILY = int(os.environ.get("TOMTOM_FLOW_DAILY", "2000"))


def api_key() -> str | None:
    return os.environ.get("TOMTOM_API_KEY") or None


async def flow_at_point(
    client: httpx.AsyncClient, lat: float, lon: float
) -> dict | None:
    key = api_key()
    if not key:
        return None
    cache_key = (round(lat, 2), round(lon, 2))
    now = time.monotonic()
    cached = _cache.get(cache_key)
    if cached and now - cached[0] < TTL_SECONDS:
        return cached[1]
    if not UPSTREAM.allow("tomtom-flow", TOMTOM_FLOW_DAILY):
        return None
    try:
        resp = await client.get(
            FLOW_URL,
            params={"point": f"{lat},{lon}", "unit": "MPH", "key": key},
            timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        seg = resp.json().get("flowSegmentData") or {}
        value = {
            "current_mph": seg.get("currentSpeed"),
            "freeflow_mph": seg.get("freeFlowSpeed"),
            "confidence": seg.get("confidence"),
            "closed": bool(seg.get("roadClosure")),
        }
    except Exception:  # noqa: BLE001 - context source, never fatal
        value = None
    _cache[cache_key] = (now, value)
    return value


def summarize(samples: list[dict]) -> dict | None:
    """Aggregate point samples into one traffic verdict."""
    usable = [
        s for s in samples
        if s and s.get("current_mph") and s.get("freeflow_mph")
    ]
    if not usable:
        return None
    ratios = [s["current_mph"] / s["freeflow_mph"] for s in usable]
    worst_i = min(range(len(usable)), key=lambda i: ratios[i])
    return {
        "sampled_points": len(usable),
        "avg_current_mph": round(
            sum(s["current_mph"] for s in usable) / len(usable)
        ),
        "avg_freeflow_mph": round(
            sum(s["freeflow_mph"] for s in usable) / len(usable)
        ),
        "worst_point": {
            "current_mph": usable[worst_i]["current_mph"],
            "freeflow_mph": usable[worst_i]["freeflow_mph"],
        },
        "flowing_freely": min(ratios) > 0.75,
    }


# ── Routing with time-of-day traffic ─────────────────────────────────────────
# The Routing API answers for any departure time: a future departAt is
# costed on TomTom's historical speed profiles for that weekday and
# hour, and a departure in the next hour or so also folds in live
# traffic. That is the data behind "when should I leave": one request
# per candidate departure, every one counted against the same free
# daily allowance the flow layer draws on, so the cap here keeps both
# inside it. Profiles for a future hour do not change between calls,
# so those answers cache for hours; "now" answers cache for minutes.

ROUTE_URL = "https://api.tomtom.com/routing/1/calculateRoute/{locs}/json"
TOMTOM_ROUTE_DAILY = int(os.environ.get("TOMTOM_ROUTE_DAILY", "500"))
ROUTE_TIMEOUT_SECONDS = 15.0
ROUTE_TTL_NOW = 120.0
ROUTE_TTL_FUTURE = 6 * 3600.0
_ROUTE_CACHE_MAX = 2000
_route_cache: dict[tuple, tuple[float, float, dict | None]] = {}


def _route_summary(route: dict, with_points: bool) -> dict:
    s = route.get("summary") or {}
    out = {
        "travel_s": s.get("travelTimeInSeconds"),
        "historic_s": s.get("historicTrafficTravelTimeInSeconds"),
        "no_traffic_s": s.get("noTrafficTravelTimeInSeconds"),
        "live_s": s.get("liveTrafficIncidentsTravelTimeInSeconds"),
        "delay_s": s.get("trafficDelayInSeconds"),
        "length_m": s.get("lengthInMeters"),
        "departure": s.get("departureTime"),
        "arrival": s.get("arrivalTime"),
    }
    if with_points:
        pts = []
        for leg in route.get("legs") or []:
            for p in leg.get("points") or []:
                pts.append([p["latitude"], p["longitude"]])
        out["points"] = pts
    return out


async def route_times(
    client: httpx.AsyncClient,
    origin: tuple[float, float],
    destination: tuple[float, float],
    depart_at: str | None = None,
    *,
    with_points: bool = False,
) -> dict | None:
    """Drive time from origin to destination leaving at ``depart_at``
    (ISO 8601 with a UTC offset; None means now), or None.

    The answer carries the traffic-aware time and, alongside it, the
    historical-profile, live and no-traffic times, so a caller can say
    how much of the drive is traffic. None means no key, the daily cap
    is spent, TomTom refused the request (a departure in the past), or
    the network failed: callers degrade, never break.
    """
    key = api_key()
    if not key:
        return None
    ck = (round(origin[0], 4), round(origin[1], 4),
          round(destination[0], 4), round(destination[1], 4),
          depart_at or "now", with_points)
    now = time.monotonic()
    hit = _route_cache.get(ck)
    if hit and now - hit[0] < hit[1]:
        return hit[2]
    if not UPSTREAM.allow("tomtom-route", TOMTOM_ROUTE_DAILY):
        return None
    locs = f"{origin[0]},{origin[1]}:{destination[0]},{destination[1]}"
    params = {
        "traffic": "true", "computeTravelTimeFor": "all",
        "routeType": "fastest", "travelMode": "car", "key": key,
        "routeRepresentation": "polyline" if with_points else "summaryOnly",
    }
    if depart_at:
        params["departAt"] = depart_at
    try:
        resp = await client.get(ROUTE_URL.format(locs=locs), params=params,
                                timeout=ROUTE_TIMEOUT_SECONDS)
        if resp.status_code == 429:
            # The free tier allows a few requests a second; one patient
            # retry rides out a burst.
            await asyncio.sleep(1.2)
            resp = await client.get(ROUTE_URL.format(locs=locs), params=params,
                                    timeout=ROUTE_TIMEOUT_SECONDS)
        if resp.status_code == 429 or resp.status_code >= 500:
            return None  # transient: never cached
        if resp.status_code >= 400:
            value = None  # refused as asked (a past departure): cached
        else:
            routes = resp.json().get("routes") or []
            value = _route_summary(routes[0], with_points) if routes else None
    except Exception:  # noqa: BLE001 - a context source, never fatal
        return None
    if len(_route_cache) >= _ROUTE_CACHE_MAX:
        _route_cache.pop(next(iter(_route_cache)))
    _route_cache[ck] = (now, _route_ttl(depart_at), value)
    return value


def _route_ttl(depart_at: str | None) -> float:
    """Hours for a departure well ahead (profiles only); minutes for one
    near enough that live traffic is part of the answer."""
    from datetime import UTC, datetime

    if not depart_at:
        return ROUTE_TTL_NOW
    try:
        ahead = (datetime.fromisoformat(depart_at)
                 - datetime.now(UTC)).total_seconds()
    except ValueError:
        return ROUTE_TTL_NOW
    return ROUTE_TTL_FUTURE if ahead > 2 * 3600 else 300.0
