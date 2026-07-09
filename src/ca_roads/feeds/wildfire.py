"""Active California wildfires from the WFIGS current-incidents ArcGIS layer
(hosted by NIFC). The CAL FIRE incidents feed blocks non-browser clients, so
WFIGS is used instead; it is the authoritative interagency source and openly
queryable.

Each fire is a point of origin with name, size, and containment. ArcGIS
reports query failures as HTTP 200 with an {"error": ...} body; that is
treated as a failure so it surfaces instead of looking like "0 active fires".
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from ca_roads.cache import TTLCache
from ca_roads.feeds import USER_AGENT
from ca_roads.models import FeedResult, RoadEvent, Wildfire

SOURCE = "wfigs"
TTL_SECONDS = 5 * 60
MAX_SERVE_SECONDS = 60 * 60
TIMEOUT_SECONDS = 15.0

QUERY_URL = (
    "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/"
    "WFIGS_Incident_Locations_Current/FeatureServer/0/query"
)
QUERY_PARAMS = {
    "where": "POOState='US-CA' AND IncidentTypeCategory='WF' AND ActiveFireCandidate=1",
    "outFields": (
        "IncidentName,IncidentSize,PercentContained,"
        "FireDiscoveryDateTime,UniqueFireIdentifier,IncidentTypeCategory"
    ),
    "returnGeometry": "true",
    "outSR": "4326",
    "f": "json",
}


class WfigsQueryError(Exception):
    """The ArcGIS server answered 200 with an error body."""


def parse_wfigs_json(payload: dict) -> tuple[list[Wildfire], list[str]]:
    """Parse an ArcGIS query response into fires plus feed notes.

    Raises WfigsQueryError when the body carries an error object.
    """
    if "error" in payload:
        raise WfigsQueryError(f"WFIGS query error: {payload['error']}")
    notes: list[str] = []
    if payload.get("exceededTransferLimit"):
        notes.append("WFIGS response hit the server record cap; some fires may be omitted")
    fires: list[Wildfire] = []
    for i, feature in enumerate(payload.get("features") or []):
        geom = feature.get("geometry") or {}
        attrs = feature.get("attributes") or {}
        # Defense in depth: only real wildfires (WF), never prescribed burns
        # (RX), even if the server-side type filter ever stops applying.
        if attrs.get("IncidentTypeCategory", "WF") != "WF":
            continue
        lon = geom.get("x")
        lat = geom.get("y")
        if not isinstance(lat, int | float) or not isinstance(lon, int | float):
            continue
        if lat == 0.0 and lon == 0.0:
            continue
        fire_id = attrs.get("UniqueFireIdentifier") or f"objectid-{attrs.get('OBJECTID', i)}"
        size = attrs.get("IncidentSize")
        contained = attrs.get("PercentContained")
        discovered_ms = attrs.get("FireDiscoveryDateTime")
        fires.append(
            Wildfire(
                id=str(fire_id),
                name=(attrs.get("IncidentName") or "").strip(),
                lat=float(lat),
                lon=float(lon),
                size_acres=float(size) if isinstance(size, int | float) else None,
                percent_contained=(
                    float(contained) if isinstance(contained, int | float) else None
                ),
                discovered_at=(
                    datetime.fromtimestamp(discovered_ms / 1000, UTC)
                    if isinstance(discovered_ms, int | float) and discovered_ms > 0
                    else None
                ),
            )
        )
    return fires, notes


def describe(fire: Wildfire) -> str:
    text = "Wildfire"
    if fire.name:
        text += f": {fire.name}"
    if fire.size_acres is not None:
        text += f", {fire.size_acres:,.0f} acres"
    if fire.percent_contained is not None:
        text += f", {fire.percent_contained:.0f}% contained"
    return text


def to_event(fire: Wildfire) -> RoadEvent:
    return RoadEvent(
        source=SOURCE,
        id=f"fire_{fire.id}",
        family="fire",
        lat=fire.lat,
        lon=fire.lon,
        summary=describe(fire),
        reported_at=fire.discovered_at,
        record=fire,
    )


class WildfireSource:
    """Statewide cached fetcher (fires update slowly; 5-minute cache)."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self._cache = TTLCache()

    async def _fetch(self) -> tuple[list[Wildfire], list[str]]:
        resp = await self._client.get(
            QUERY_URL,
            params=QUERY_PARAMS,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return parse_wfigs_json(resp.json())

    async def get(self) -> FeedResult:
        outcome = await self._cache.get("ca", TTL_SECONDS, MAX_SERVE_SECONDS, self._fetch)
        if not outcome.served:
            return FeedResult(
                source=SOURCE, records=[], data_as_of=None, ok=False, error=outcome.error
            )
        fires, notes = outcome.value
        if outcome.stale:
            notes = [*notes, "live fetch failed; serving cached data"]
        return FeedResult(
            source=SOURCE,
            records=list(fires),
            data_as_of=outcome.fetched_at,
            stale=outcome.stale,
            error=outcome.error,
            notes=notes,
        )


# YearToDate, not Current: the Current layer holds only the last couple of
# days of uploads, so an active fire whose perimeter was mapped last week
# has no footprint there. Stale entries are harmless because callers
# name-match perimeters against the active incident list.
PERIMETER_URL = (
    "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/"
    "WFIGS_Interagency_Perimeters_YearToDate/FeatureServer/0/query"
)


async def perimeters_in_bbox(
    client: httpx.AsyncClient,
    lat_min: float,
    lon_min: float,
    lat_max: float,
    lon_max: float,
) -> list[dict]:
    """Simplified fire perimeter rings intersecting a bounding box.

    Geometry is server-simplified (maxAllowableOffset ~500m) since the use
    is distance-to-edge estimation, not cartography. Failures return empty:
    perimeter data refines fire distances, it never gates a report.
    """
    try:
        resp = await client.get(
            PERIMETER_URL,
            params={
                "where": "attr_POOState='US-CA'",
                "geometry": f"{lon_min},{lat_min},{lon_max},{lat_max}",
                "geometryType": "esriGeometryEnvelope",
                "spatialRel": "esriSpatialRelIntersects",
                "inSR": 4326,
                "outSR": 4326,
                "outFields": "poly_IncidentName,poly_GISAcres",
                "maxAllowableOffset": 0.005,
                "returnGeometry": "true",
                "f": "json",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=20.0,
        )
        resp.raise_for_status()
        payload = resp.json()
        if "error" in payload:
            return []
        out = []
        for feature in payload.get("features", []):
            attrs = feature.get("attributes") or {}
            rings = (feature.get("geometry") or {}).get("rings") or []
            points = [
                (pt[1], pt[0])
                for ring in rings
                for pt in ring
                if isinstance(pt, list) and len(pt) >= 2
            ]
            if points:
                out.append({
                    "name": (attrs.get("poly_IncidentName") or "").strip().upper(),
                    "acres": attrs.get("poly_GISAcres"),
                    "points": points,
                })
        return out
    except Exception:  # noqa: BLE001
        return []
