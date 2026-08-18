"""Stadia Maps Valhalla routing client shared by roadsnap and app.

One POST per route request; the api_key travels as a query param (the
browser pages call the same endpoint keyless under Stadia domain auth,
this module is only for server-side callers). Valhalla encodes leg
geometry as precision-6 polylines and reports lengths in kilometers.
"""

import httpx

ROUTE_URL = "https://api.stadiamaps.com/route/v1"
UA = {"User-Agent":
      "commutescout.com road snapper (https://commutescout.com)"}


class NoCandidateError(Exception):
    """Valhalla found no routable edge near an input location."""


def decode_polyline6(encoded: str) -> list[list[float]]:
    index = lat = lon = 0
    out: list[list[float]] = []
    while index < len(encoded):
        deltas = []
        for _ in range(2):
            shift = result = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        lat += deltas[0]
        lon += deltas[1]
        out.append([lat / 1e6, lon / 1e6])
    return out


async def route(client: httpx.AsyncClient, locations: list[dict], *,
                api_key: str, timeout: float = 20.0,
                **options) -> dict | None:
    """Route through the given locations, returning Valhalla's trip dict
    or None when no route came back. HTTP 400 means no routable edge
    near a location (raises NoCandidateError so callers can widen their
    search); other error statuses raise httpx.HTTPStatusError."""
    body = {"locations": locations, "costing": "auto", **options}
    resp = await client.post(ROUTE_URL, params={"api_key": api_key},
                             json=body, headers=UA, timeout=timeout)
    if resp.status_code == 400:
        raise NoCandidateError(resp.text[:200])
    resp.raise_for_status()
    trip = (resp.json() or {}).get("trip") or {}
    return trip if trip.get("legs") else None


def trip_points(trip: dict) -> list[list[float]]:
    """Concatenated [lat, lon] points across all legs."""
    pts: list[list[float]] = []
    for leg in trip.get("legs") or []:
        pts.extend(decode_polyline6(leg.get("shape") or ""))
    return pts


def trip_meters(trip: dict) -> float:
    return float((trip.get("summary") or {}).get("length") or 0) * 1000.0
