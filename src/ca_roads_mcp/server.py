"""MCP server: live California road conditions.

Six tools over the ca_roads feed layer, served over stdio (local dev) or
streamable HTTP (hosted). Docstrings are written for the LLM consuming the
tools: they say what the data is, how fresh it is, and where it falls short.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from ca_roads.dedupe import dedupe
from ca_roads.feeds import bay511 as bay511_feed
from ca_roads.feeds import chains as chains_feed
from ca_roads.feeds import chp as chp_feed
from ca_roads.feeds import lcs as lcs_feed
from ca_roads.feeds import nvroads as nvroads_feed
from ca_roads.feeds import nws as nws_feed
from ca_roads.feeds import quakes as quakes_feed
from ca_roads.feeds import tomtom as tomtom_feed
from ca_roads.feeds import wildfire as wildfire_feed
from ca_roads.geo import haversine_meters
from ca_roads.roaddata import RoadData
from ca_roads_mcp import corridors as corr
from ca_roads_mcp import regions as reg
from ca_roads_mcp.geocode import geocode, geocode_candidates
from ca_roads_mcp.routes import matches_route, normalize_route
from ca_roads_mcp.serialize import (
    camera_dict,
    chain_control_dict,
    closure_dict,
    incident_dict,
    rwis_dict,
    sign_dict,
    source_status,
    wildfire_dict,
)

INSTRUCTIONS = """\
Live California road conditions from CHP (incidents), Caltrans (lane
closures and chain controls), and WFIGS (wildfires). All data is official,
public, and read-only. Every response carries a `sources` list with a
`data_as_of` timestamp per source - always relay meaningful staleness or
feed errors to the user. This service reports CURRENT conditions only; it
cannot forecast. Remind users to verify before they drive (dial 511 or check
quickmap.dot.ca.gov). Not affiliated with any government agency.
"""

mcp = FastMCP("CommuteScout", instructions=INSTRUCTIONS)

_road: RoadData | None = None


def get_road() -> RoadData:
    global _road
    if _road is None:
        _road = RoadData()
    return _road



def _read_only(title: str) -> ToolAnnotations:
    """Directory-required annotations: every tool here reads public
    data and mutates nothing."""
    return ToolAnnotations(title=title, readOnlyHint=True,
                           openWorldHint=True)
MILES_PER_METER = 1 / 1609.344


async def _noop() -> None:
    return None


async def _route_context(
    road, sample_points: list[tuple[float, float]]
) -> tuple[list[dict], list[dict], list[str]]:
    """Weather alerts, notable road-weather stations, and quake notes for
    a set of points along a route or region. All context sources fail to
    empty; they enrich a report but never break one."""
    alerts, rwis_r, quakes = await asyncio.gather(
        nws_feed.alerts_at_points(road.client, sample_points),
        road.road_weather(),
        quakes_feed.recent_significant(road.client),
    )
    notable_wx: list[dict] = []
    for station in rwis_r.records:
        if station.lat is None or station.lon is None:
            continue
        near = min(
            haversine_meters(station.lat, station.lon, p[0], p[1])
            for p in sample_points
        )
        if near > 12_000:
            continue
        flags = []
        # A freezing-pavement flag needs a cold air reading to back it up:
        # some stations report 0.0 for surface temp when the sensor has no
        # data, which would otherwise cry ice in July.
        cold_air = station.air_temp_c is not None and station.air_temp_c <= 6
        if (
            station.surface_temp_c is not None
            and station.surface_temp_c <= 1
            and cold_air
        ):
            flags.append(f"pavement {station.surface_temp_c} C")
        if station.air_temp_c is not None and station.air_temp_c <= 0:
            flags.append(f"air {station.air_temp_c} C")
        if station.wind_gust_mph is not None and station.wind_gust_mph >= 35:
            flags.append(f"gusts {station.wind_gust_mph} mph")
        if station.visibility_m is not None and station.visibility_m < 800:
            flags.append(f"visibility {int(station.visibility_m)} m")
        if flags:
            entry = rwis_dict(station)
            entry["notable"] = ", ".join(flags)
            notable_wx.append(entry)
    quake_notes = []
    for q in quakes:
        near = min(
            haversine_meters(q["lat"], q["lon"], p[0], p[1])
            for p in sample_points
        )
        if near <= 80_000 and q.get("magnitude"):
            quake_notes.append(
                f"M{q['magnitude']} earthquake in the last 24h "
                f"({q.get('place', 'nearby')}); check for pavement damage "
                "reports on mountain and canyon roads"
            )
    return alerts, notable_wx[:3], quake_notes


def _downsample(points: list, max_points: int = 120) -> list:
    if len(points) <= max_points:
        return [[round(lat, 4), round(lon, 4)] for lat, lon in points]
    step = len(points) / max_points
    return [
        [round(points[int(i * step)][0], 4), round(points[int(i * step)][1], 4)]
        for i in range(max_points)
    ]


async def _attach_perimeters(fire_dicts: list[dict], bbox: tuple) -> None:
    """Attach simplified perimeter rings to fires that have one mapped.

    A perimeter turns a fire from a dot into its actual footprint on the
    map, and the edge is what matters for a road. Name-matched; failures
    leave the dicts untouched."""
    if not fire_dicts:
        return
    perimeters = await wildfire_feed.perimeters_in_bbox(
        get_road().client, *bbox
    )
    by_name = {p["name"]: p for p in perimeters if p["name"]}
    for d in fire_dicts:
        perim = by_name.get((d.get("name") or "").upper())
        if perim:
            d["perimeter"] = _downsample(perim["points"])


def _fires_bbox(fire_dicts: list[dict], pad: float = 0.4) -> tuple | None:
    lats = [d["lat"] for d in fire_dicts if isinstance(d.get("lat"), int | float)]
    lons = [d["lon"] for d in fire_dicts if isinstance(d.get("lon"), int | float)]
    if not lats:
        return None
    return (min(lats) - pad, min(lons) - pad, max(lats) + pad, max(lons) + pad)


async def _signs_near(points: list[tuple[float, float]], within_km: float = 8,
                      cap: int = 8) -> list[dict]:
    result = await get_road().message_signs()
    hits = []
    for s in (r for r in result.records if r.text):
        if s.lat is None or s.lon is None:
            continue
        dist = min(
            haversine_meters(s.lat, s.lon, p[0], p[1]) for p in points
        )
        if dist <= within_km * 1000:
            hits.append((dist, s))
    hits.sort(key=lambda t: t[0])
    return [sign_dict(s) for _, s in hits[:cap]]


async def _cameras_near(point: tuple[float, float], limit: int = 3,
                        radius_km: float = 35) -> list[dict]:
    result = await get_road().cameras()
    nearby = [
        c for c in result.records
        if c.lat and c.lon
        and haversine_meters(*point, c.lat, c.lon) <= radius_km * 1000
    ]
    nearby.sort(key=lambda c: haversine_meters(*point, c.lat, c.lon))
    live, _ = await _live_cameras(nearby, limit)
    return [camera_dict(c) for c in live]


async def _attach_scenery(payload: dict, points: list[tuple[float, float]],
                          cam_limit: int = 2) -> None:
    """Attach nearby signs and verified cameras to a tool payload.

    Every tool that reports events should also show what the road itself
    is saying (signs) and looking like (cameras); users read the map as
    the product, and a bare dot layer looks broken next to the legend.
    Anchors on the returned records' own coordinates."""
    if not points:
        return
    usable = [
        p for p in points
        if isinstance(p[0], int | float) and isinstance(p[1], int | float)
        and p[0]
    ][:40]
    if not usable:
        return
    centroid = (
        sum(p[0] for p in usable) / len(usable),
        sum(p[1] for p in usable) / len(usable),
    )
    signs, cameras = await asyncio.gather(
        _signs_near(usable, within_km=8, cap=6),
        _cameras_near(centroid, limit=cam_limit),
    )
    if signs:
        payload["signs"] = signs
    if cameras:
        payload["cameras"] = cameras


def parse_center(center: str) -> tuple[float, float] | None:
    try:
        lat_s, lon_s = center.split(",")
        return float(lat_s), float(lon_s)
    except ValueError:
        return None


CENTER_FORMAT_ERROR = "center must be 'lat,lon', e.g. '38.58,-121.49'"


def incident_severity(log_type: str) -> int:
    """Sort key for regional reports: worst first."""
    lowered = log_type.lower()
    if "1144" in lowered or "fatal" in lowered:
        return 0
    if any(code in lowered for code in ("1179", "1181", "20001")):
        return 1  # injury collisions
    if any(code in lowered for code in ("1182", "1183")) or "collision" in lowered:
        return 2
    if "fire" in lowered:
        return 3
    if "closure" in lowered:
        return 4
    return 5  # hazards, disabled vehicles, everything else


REGION_INCIDENT_CAP = 15
REGION_CLOSURE_CAP = 12
REGION_FIRE_CAP = 10


@mcp.tool(annotations=_read_only("Check a route"))
async def check_route(
    from_place: str,
    to_place: str,
    from_coords: str | None = None,
    to_coords: str | None = None,
) -> dict:
    """Check current conditions along a major California highway corridor.

    The flagship trip-check tool: give it a start and end place and it
    returns everything active along that stretch right now - CHP incidents,
    lane closures physically in place, chain controls, and wildfires within
    ~10 miles - ordered by miles from the start, plus a summary.

    ALWAYS pass from_coords and to_coords ("lat,lon") when you know where
    the places are - for landmarks, small towns, or anything not a major
    city they are required for a good answer. Coordinates do two things:
    they let unlisted places resolve to the nearest corridor (e.g. "Alice's
    Restaurant" snaps to I-280 on the Peninsula), and they CLIP the route to
    the span actually being driven, so a trip to a mid-corridor destination
    doesn't report events beyond it.

    Corridors covered: I-80 Sacramento-Reno, US-50 to South Lake Tahoe, I-5,
    US-101, SR-17, SR-99, SR-1, I-15 to Vegas, Bay Area freeways, Tahoe-area
    routes. This is NOT a general router: if nothing matches (even with
    coordinates), the response lists the covered corridors; fall back to the
    filtered tools with center= for anything else.

    Freshness: CHP incidents refresh about once a minute; closures, chain
    controls, and fires are on a 5-minute cache. Current conditions only -
    this cannot forecast tomorrow's weather or closures.
    """
    from_point = parse_center(from_coords) if from_coords else None
    if from_coords and from_point is None:
        return {"error": f"from_coords: {CENTER_FORMAT_ERROR}"}
    to_point = parse_center(to_coords) if to_coords else None
    if to_coords and to_point is None:
        return {"error": f"to_coords: {CENTER_FORMAT_ERROR}"}

    # Caller-supplied coordinates are authoritative; only missing sides get
    # geocoded (offline gazetteer first, network geocoders for addresses and
    # landmarks). This keeps warm calls with coordinates at zero geocoding
    # latency.
    road = get_road()
    resolved_notes: list[str] = []
    if from_point is None:
        from_geo = await geocode(road.client, from_place)
        if from_geo:
            from_point = (from_geo[0], from_geo[1])
    if to_point is None:
        # Corridor aliases ("Tahoe", "the coast") are their own resolution:
        # when both trip ends match a corridor by name, anchoring to the
        # corridor is right and asking "which Tahoe?" is nonsense. Only
        # non-alias destinations go through candidate disambiguation.
        alias_match = corr.resolve_corridor(from_place, to_place)
        if alias_match:
            # Alias trips skip disambiguation, but still geocode the
            # destination plainly: the point anchors the clip and lets
            # the alternatives check see which other corridors serve it.
            to_geo = await geocode(road.client, to_place)
            if to_geo:
                to_point = (to_geo[0], to_geo[1])
            to_cands = []
        else:
            to_cands = await geocode_candidates(
                road.client, to_place, near=from_point
            )
        # Multiple far-apart matches: the wrong guess sends someone across
        # the hills. Refuse and make the caller ask which one was meant.
        # A comma-qualified place ("Riverside Dr, San Jose") means the
        # caller already disambiguated: take the nearest match, never
        # re-ask - that way clarification converges in one round.
        spread = [
            c for c in to_cands
            if haversine_meters(c[0], c[1], to_cands[0][0], to_cands[0][1])
            > 15_000
        ]
        if to_cands and spread and "," not in to_place:
            options = [
                ", ".join(c[2].split(", ")[:4]) for c in to_cands[:3]
            ]
            return {
                "needs_clarification": True,
                "which": "destination",
                "options": options,
                "error": (
                    f"'{to_place}' matches multiple places. Do not guess. "
                    "Ask the user which one they meant, offering these "
                    "options."
                ),
            }
        if to_cands:
            to_geo = to_cands[0]
            to_point = (to_geo[0], to_geo[1])
            short_name = ", ".join(to_geo[2].split(", ")[:3])
            resolved_notes.append(f"destination resolved to: {short_name}")

    if from_point and to_point:
        span_km = haversine_meters(*from_point, *to_point) / 1000
        if span_km < 12:
            mid = (
                f"{(from_point[0] + to_point[0]) / 2:.4f},"
                f"{(from_point[1] + to_point[1]) / 2:.4f}"
            )
            return {
                "local_trip": True,
                "error": (
                    f"'{from_place}' to '{to_place}' is a short local trip "
                    f"(~{span_km:.0f} km); corridor checks cover highway "
                    "trips. Call get_incidents and get_lane_closures with "
                    f"center='{mid}' and radius_km=10 instead - that covers "
                    "every road between the two points."
                ),
                "suggested_center": mid,
            }

    match = corr.resolve_corridor_ext(from_place, to_place, from_point, to_point)
    if match is None:
        return {
            "error": (
                f"No corridor found covering '{from_place}' to '{to_place}'. "
                "This tool covers a curated set of major California "
                "corridors. Pass from_coords/to_coords to snap nearby places "
                "onto a corridor, or use the filtered tools with center=."
            ),
            "supported_corridors": corr.corridor_names(),
        }
    corridor = match.corridor
    districts = corr.corridor_districts(corridor)

    # Clip the corridor to the span actually being driven. Ends without
    # coordinates anchor to the corridor endpoint on their side.
    total = corr.total_length(corridor)
    clip_notes: list[str] = []
    along_from = total if match.reversed else 0.0
    along_to = 0.0 if match.reversed else total
    if from_point:
        snap_dist, snapped = corr.distance_to_corridor(corridor, *from_point)
        if snap_dist <= corr.SNAP_MAX_METERS:
            along_from = snapped
        else:
            clip_notes.append(
                f"'{from_place}' is {snap_dist / 1609:.0f} miles off this "
                "corridor; using the corridor end instead"
            )
    if to_point:
        snap_dist, snapped = corr.distance_to_corridor(corridor, *to_point)
        if snap_dist <= corr.SNAP_MAX_METERS:
            along_to = snapped
        else:
            clip_notes.append(
                f"'{to_place}' is {snap_dist / 1609:.0f} miles off this "
                "corridor; using the corridor end instead"
            )
    heading_back = along_from > along_to
    window_lo = max(0.0, min(along_from, along_to) - 3_000)
    window_hi = min(total, max(along_from, along_to) + 3_000)

    chp_r, lcs_r, cc_r, fire_r = await asyncio.gather(
        road.incidents(),
        road.lane_closures(districts=districts),
        road.chain_controls(districts=districts),
        road.wildfires(),
    )

    events = dedupe(
        [chp_feed.to_event(i) for i in chp_r.records]
        + [lcs_feed.to_event(c) for c in lcs_r.records]
        + [chains_feed.to_event(c) for c in cc_r.records]
        + [wildfire_feed.to_event(f) for f in fire_r.records]
    )
    placed = [
        p
        for p in corr.events_on_corridor(corridor, events)
        if window_lo <= p.along_m <= window_hi
    ]
    placed.sort(key=lambda p: p.along_m, reverse=heading_back)

    items = []
    counts = {"incidents": 0, "closures": 0, "chain_controls": 0, "wildfires": 0}
    max_chain = ""
    full_closures = 0
    for p in placed:
        e = p.event
        record = e.record
        if e.source == "chp":
            kind = "incident"
            counts["incidents"] += 1
            detail = incident_dict(record)
        elif e.source == "lcs":
            kind = "lane_closure"
            counts["closures"] += 1
            if lcs_feed.is_full_roadway_closure(record):
                full_closures += 1
            detail = closure_dict(record)
        elif e.source == "chains":
            kind = "chain_control"
            counts["chain_controls"] += 1
            max_chain = max(max_chain, record.status)
            detail = chain_control_dict(record)
        else:
            kind = "wildfire"
            counts["wildfires"] += 1
            detail = wildfire_dict(record)
        items.append(
            {
                "kind": kind,
                "mile_along_route": round(
                    abs(p.along_m - along_from) * MILES_PER_METER, 1
                ),
                "summary": e.summary,
                "detail": detail,
            }
        )

    summary_bits = []
    if counts["chain_controls"]:
        summary_bits.append(
            f"{counts['chain_controls']} chain control point(s) active, "
            f"strictest level {max_chain}"
        )
    if full_closures:
        summary_bits.append(f"{full_closures} FULL closure(s) in place")
    lane_only = counts["closures"] - full_closures
    if lane_only > 0:
        summary_bits.append(f"{lane_only} lane closure(s) in place")
    if counts["incidents"]:
        summary_bits.append(f"{counts['incidents']} active CHP incident(s)")
    if counts["wildfires"]:
        summary_bits.append(
            f"{counts['wildfires']} wildfire(s) within ~10 miles of the route"
        )
    summary = (
        f"{corridor.name}, {from_place} to {to_place}: "
        + ("; ".join(summary_bits) if summary_bits else "no active incidents, "
           "closures, chain controls, or nearby wildfires reported")
        + "."
    )

    origin = list(from_point) if from_point else list(
        corr.point_at(corridor, along_from)
    )
    destination = list(to_point) if to_point else list(
        corr.point_at(corridor, along_to)
    )
    sample_points = [
        corr.point_at(corridor, along_from + frac * (along_to - along_from))
        for frac in (0.0, 0.5, 1.0)
    ]
    weather_alerts, road_weather, quake_notes = await _route_context(
        road, sample_points
    )

    dense_points = [
        corr.point_at(corridor, along_from + frac * (along_to - along_from))
        for frac in (0.0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0)
    ]
    fire_details = [
        item["detail"] for item in items if item.get("kind") == "wildfire"
    ]
    lat_pad = 0.4
    route_bbox = (
        min(p[0] for p in dense_points) - lat_pad,
        min(p[1] for p in dense_points) - lat_pad,
        max(p[0] for p in dense_points) + lat_pad,
        max(p[1] for p in dense_points) + lat_pad,
    )
    route_signs, route_cameras, _ = await asyncio.gather(
        _signs_near(dense_points),
        _cameras_near(sample_points[1]),
        _attach_perimeters(fire_details, route_bbox),
    )

    traffic = None
    if tomtom_feed.api_key():
        flow_points = [
            corr.point_at(corridor, along_from + frac * (along_to - along_from))
            for frac in (0.1, 0.3, 0.5, 0.7, 0.9)
        ]
        samples = await asyncio.gather(
            *(tomtom_feed.flow_at_point(road.client, p[0], p[1])
              for p in flow_points)
        )
        traffic = tomtom_feed.summarize(list(samples))

    nevada = []
    if corridor.id in ("i80-sac-reno", "us50-sac-tahoe", "i15-barstow-vegas"):
        nv_events = await nvroads_feed.events(road.client)
        route_names = {r.replace("-", "").lower() for r in corridor.routes}
        for event in nv_events:
            road_name = (event.get("road") or "").replace("-", "").lower()
            if any(r in road_name or road_name in r for r in route_names if r):
                nevada.append(event)
        nevada = nevada[:6]

    alternatives = []
    if from_point and to_point:
        for other in corr.CORRIDORS:
            if other.id == corridor.id:
                continue
            d_from, _ = corr.distance_to_corridor(other, *from_point)
            d_to, _ = corr.distance_to_corridor(other, *to_point)
            if d_from <= corr.SNAP_MAX_METERS and d_to <= corr.SNAP_MAX_METERS:
                alternatives.append(other.name)

    result = {
        "corridor": corridor.name,
        "direction": f"{from_place} -> {to_place}",
        "origin": origin,
        "destination": destination,
        # Straight-line along the corridor skeleton; actual road miles run
        # longer. Present it as an approximation.
        "trip_miles_approx": round(abs(along_to - along_from) * MILES_PER_METER, 1),
        "summary": summary,
        "events": items,
        "route_geometry": corr.clip_geometry(corridor, along_from, along_to),
        "sources": [source_status(r) for r in (chp_r, lcs_r, cc_r, fire_r)],
    }
    if weather_alerts:
        result["weather_alerts"] = weather_alerts
    if road_weather:
        result["road_weather"] = road_weather
    if traffic:
        result["traffic"] = traffic
    if nevada:
        result["nevada_continuation"] = nevada
    if route_signs:
        result["signs"] = route_signs
    if route_cameras:
        result["cameras"] = route_cameras
    if alternatives:
        result["alternative_corridors"] = alternatives[:3]
        resolved_notes.append(
            "other corridors also connect these places: "
            + ", ".join(alternatives[:3])
            + ". Offer to check one if this route looks bad."
        )
    all_notes = resolved_notes + clip_notes + quake_notes
    if all_notes:
        result["notes"] = all_notes
    return result


@mcp.tool(annotations=_read_only("Check a region"))
async def check_region(region: str) -> dict:
    """Full current-conditions report for a California region.

    Use this for area-scale questions ("how is the Bay Area?", "what's
    happening in SoCal?") instead of stitching together point queries. It
    sweeps every source over the whole region at once: CHP incidents
    (severity-sorted, worst first), lane closures in place (full closures
    called out), chain controls, and wildfires inside the region.

    Regions: Bay Area, Sacramento metro, Tahoe/Sierra, Central Valley,
    Southern California, San Diego, Central Coast, North State. An
    unrecognized region name returns the list.

    Large regions are capped to the most severe items; the counts are
    always exact and the response says when a list was truncated.
    Freshness: CHP ~1/min fetched live, everything else 5-minute cache.
    """
    resolved = reg.resolve_region(region)
    if resolved is None:
        return {
            "error": f"Unknown region '{region}'.",
            "supported_regions": reg.region_names(),
        }

    road = get_road()
    chp_r, lcs_r, cc_r, fire_r = await asyncio.gather(
        road.incidents(),
        road.lane_closures(districts=list(resolved.districts)),
        road.chain_controls(districts=list(resolved.districts)),
        road.wildfires(),
    )

    incidents = sorted(
        (i for i in chp_r.records if resolved.contains(i.lat, i.lon)),
        key=lambda i: incident_severity(i.log_type),
    )
    closures = [
        c for c in lcs_r.records if resolved.contains(c.begin_lat, c.begin_lon)
    ]
    closures.sort(key=lcs_feed.closure_severity)
    chains = [c for c in cc_r.records if resolved.contains(c.lat, c.lon)]
    fires = [f for f in fire_r.records if resolved.contains(f.lat, f.lon)]
    fires.sort(key=lambda f: -(f.size_acres or 0))

    full_closures = sum(1 for c in closures if lcs_feed.is_full_roadway_closure(c))
    ramp_closures = sum(1 for c in closures if lcs_feed.closure_class(c) == "ramp")
    injury = sum(1 for i in incidents if incident_severity(i.log_type) <= 1)
    max_chain = max((c.status for c in chains), default="")

    notes = []
    if len(incidents) > REGION_INCIDENT_CAP:
        notes.append(
            f"showing the {REGION_INCIDENT_CAP} most severe of "
            f"{len(incidents)} incidents"
        )
    if len(closures) > REGION_CLOSURE_CAP:
        notes.append(
            f"showing {REGION_CLOSURE_CAP} of {len(closures)} closures "
            "(full closures first)"
        )
    if len(fires) > REGION_FIRE_CAP:
        notes.append(f"showing the {REGION_FIRE_CAP} largest of {len(fires)} fires")

    bits = []
    if incidents:
        bits.append(
            f"{len(incidents)} active CHP incident(s)"
            + (f", {injury} involving injuries" if injury else "")
        )
    if closures:
        detail = f", {full_closures} FULL roadway" if full_closures else ""
        if ramp_closures:
            detail += f", {ramp_closures} ramp-only"
        bits.append(f"{len(closures)} closure(s) in place{detail}")
    if chains:
        bits.append(f"{len(chains)} chain control(s) active, strictest {max_chain}")
    if fires:
        bits.append(f"{len(fires)} active wildfire(s) in the region")
    lat_min, lat_max, lon_min, lon_max = resolved.bbox
    region_points = [
        ((lat_min + lat_max) / 2, (lon_min + lon_max) / 2),
        (lat_min, lon_min),
        (lat_max, lon_max),
    ]
    weather_alerts, road_weather, quake_notes = await _route_context(
        get_road(), region_points
    )

    summary = f"{resolved.name}: " + (
        "; ".join(bits) if bits else "no active incidents, closures, chain "
        "controls, or wildfires reported"
    ) + "."

    fire_dicts = []
    for f in fires[:REGION_FIRE_CAP]:
        d = wildfire_dict(f)
        d["near_highways"] = sorted({
            c.routes[0]
            for c in corr.CORRIDORS
            if corr.distance_to_corridor(c, f.lat, f.lon)[0] <= corr.FIRE_BUFFER_METERS
        })
        fire_dicts.append(d)

    payload = {
        "region": resolved.name,
        "summary": summary,
        "counts": {
            "incidents": len(incidents),
            "injury_incidents": injury,
            "lane_closures": len(closures),
            "full_closures": full_closures,
            "ramp_closures": ramp_closures,
            "chain_controls": len(chains),
            "wildfires": len(fires),
        },
        "filters": {"region": resolved.id},
        "incidents": [incident_dict(i) for i in incidents[:REGION_INCIDENT_CAP]],
        "closures": [closure_dict(c) for c in closures[:REGION_CLOSURE_CAP]],
        "chain_controls": [chain_control_dict(c) for c in chains],
        "wildfires": fire_dicts,
        "notes": notes + quake_notes,
        "sources": [source_status(r) for r in (chp_r, lcs_r, cc_r, fire_r)],
    }
    if weather_alerts:
        payload["weather_alerts"] = weather_alerts
    if road_weather:
        payload["road_weather"] = road_weather
    region_signs = await _signs_near(
        region_points, within_km=140, cap=10
    )
    if region_signs:
        payload["signs"] = region_signs
    await _attach_perimeters(
        fire_dicts, (lat_min - 0.2, lon_min - 0.2, lat_max + 0.2, lon_max + 0.2)
    )
    if resolved.id == "bay-area" and bay511_feed.api_key():
        events_511 = await bay511_feed.events(get_road().client)
        if events_511:
            payload["events_511"] = events_511[:8]
    return payload


@mcp.tool(annotations=_read_only("Live incidents"))
async def get_incidents(
    highway: str | None = None,
    area: str | None = None,
    center: str | None = None,
    radius_km: float = 40,
) -> dict:
    """Live CHP traffic incidents statewide, optionally filtered.

    Data: the California Highway Patrol statewide computer-aided dispatch
    feed - collisions, traffic hazards, disabled vehicles, closures as CHP
    logs them. Refreshes about once a minute; incidents disappear when CHP
    closes the log. Fetched live on every call.

    Filters (combinable):
    - highway: a route like "I-80", "US 50", "17", "Hwy 99". Matches
      incidents whose location text mentions that route.
    - center: "lat,lon" with radius_km - incidents within that circle. THIS
      IS THE RIGHT FILTER FOR A TOWN OR PLACE NAME: use your knowledge of
      where the place is (e.g. Coyote, CA -> "37.22,-121.74") with radius_km
      15-30. A circle catches every road around the place, not just one
      highway.
    - area: substring match on the CHP dispatch-area name. These are CHP
      communication-center names ("Hollister Gilroy", "East Sac", "Golden
      Gate"), NOT town names - do not pass a town here. There is no county
      filter because CHP's feed carries no county field; for a county, use
      center on the county seat with a radius covering the county.

    Limits: locations are free-text from dispatchers; a few incidents lack
    usable coordinates and are omitted. No history - current logs only.
    """
    result = await get_road().incidents()
    records = result.records
    warning = None
    canonical = normalize_route(highway) if highway else None
    if canonical:
        records = [i for i in records if matches_route(i.location, canonical)]
    if area:
        needle = area.lower()
        matched = [i for i in records if needle in i.area.lower()]
        if not matched and records:
            # The #1 misuse is passing a town name; make the miss loud and
            # give the model a recovery path instead of a silent zero.
            active_areas = sorted({i.area for i in records if i.area})
            warning = (
                f"No incidents matched area='{area}'. The area filter matches "
                "CHP dispatch-area names, not towns. Areas currently "
                f"reporting incidents: {', '.join(active_areas)}. If you "
                "meant a town or place, call again with center='lat,lon' "
                "(radius_km 15-30) instead - that catches every road around "
                "the place."
            )
        records = matched
    if center:
        point = parse_center(center)
        if point is None:
            return {"error": CENTER_FORMAT_ERROR}
        records = [
            i
            for i in records
            if haversine_meters(*point, i.lat, i.lon) <= radius_km * 1000
        ]
    payload = {
        "count": len(records),
        "filters": {"highway": canonical, "area": area, "center": center},
        "incidents": [incident_dict(i) for i in records],
        "sources": [source_status(result)],
    }
    if warning:
        payload["warning"] = warning
    if canonical or center:
        await _attach_scenery(payload, [(i.lat, i.lon) for i in records])
    return payload


@mcp.tool(annotations=_read_only("Lane closures"))
async def get_lane_closures(
    route: str | None = None,
    district: int | None = None,
    center: str | None = None,
    radius_km: float = 40,
) -> dict:
    """Caltrans lane and road closures physically in place RIGHT NOW.

    Data: the Caltrans Lane Closure System (LCS). Only closures that crews
    have actually established (CHP code 1097) and not yet picked up are
    returned - scheduled-but-not-started closures are excluded, so this is
    "what is blocking lanes now", not a construction calendar.
    Refresh: 5-minute cache over per-district Caltrans feeds.

    Filters: route (e.g. "I-80", "US 101", "1"); district (Caltrans district
    1-12, e.g. 3 = Sacramento/Tahoe, 4 = Bay Area, 7 = Los Angeles);
    center "lat,lon" with radius_km - closures whose begin or end point is
    inside the circle. For a town or place, center is the filter that
    catches work on EVERY road around it, including small state routes.

    Read closure_class on each record, it is what the closure means for
    through traffic:
    - "full-roadway": the road itself is closed in that direction. The only
      class that means "you can't drive through".
    - "ramp": a ramp or connector is closed (even when the raw record says
      "Full", that means the ramp is fully closed, not the highway).
    - "one-way-traffic": alternating single lane with flagging; passable
      with delays. Common on two-lane mountain roads.
    - "alternating-lanes", "moving", "traffic-break": rolling or brief work;
      minor delays.
    - "lane": some lanes closed; the lanes field says how many of how many.
    estimated_delay_minutes is present when crews reported one.
    Shoulder-only work is excluded entirely.
    """
    districts = [district] if district else None
    result = await get_road().lane_closures(districts=districts)
    records = result.records
    canonical = normalize_route(route) if route else None
    if canonical:
        records = [c for c in records if c.route == canonical]
    if center:
        point = parse_center(center)
        if point is None:
            return {"error": CENTER_FORMAT_ERROR}
        limit = radius_km * 1000
        records = [
            c
            for c in records
            if haversine_meters(*point, c.begin_lat, c.begin_lon) <= limit
            or (
                (c.end_lat or c.end_lon)
                and haversine_meters(*point, c.end_lat, c.end_lon) <= limit
            )
        ]
    payload = {
        "count": len(records),
        "filters": {"route": canonical, "district": district, "center": center},
        "closures": [closure_dict(c) for c in records],
        "sources": [source_status(result)],
    }
    if canonical or center:
        await _attach_scenery(
            payload, [(c.begin_lat, c.begin_lon) for c in records]
        )
    return payload


@mcp.tool(annotations=_read_only("Chain controls"))
async def get_chain_controls(
    route: str | None = None,
    center: str | None = None,
    radius_km: float = 40,
) -> dict:
    """Current chain-control requirements on California mountain highways.

    Data: Caltrans chain-control status for fixed checkpoints on mountain
    routes (I-80 Donner, US-50 Echo Summit, SR-88, SR-89, and others).
    Levels: R-1 = chains OR snow tires required; R-2 = chains required
    except 4WD/AWD with snow tires on all four; R-3 = chains on ALL vehicles
    (rare, usually precedes closure). Refresh: 5-minute cache.

    Filters: route (e.g. "80", "US-50", "SR-88"); center "lat,lon" with
    radius_km for all checkpoints around a place (e.g. around Truckee),
    whatever highway they are on.

    Off-season (roughly May-October) there are usually no controls anywhere;
    the response says so explicitly rather than returning an empty list.
    Chain requirements can change hour to hour in storms - tell the user the
    data_as_of time and to carry chains anyway when snow is possible.
    """
    result = await get_road().chain_controls()
    records = result.records
    canonical = normalize_route(route) if route else None
    if canonical:
        records = [c for c in records if c.route == canonical]
    if center:
        point = parse_center(center)
        if point is None:
            return {"error": CENTER_FORMAT_ERROR}
        records = [
            c
            for c in records
            if haversine_meters(*point, c.lat, c.lon) <= radius_km * 1000
        ]
    payload = {
        "count": len(records),
        "filters": {"route": canonical, "center": center},
        "chain_controls": [chain_control_dict(c) for c in records],
        "sources": [source_status(result)],
    }
    if not records and result.ok:
        where = f"on {canonical}" if canonical else (
            "near that point" if center else "anywhere in California"
        )
        payload["message"] = f"No chain controls active {where} right now."
    if records and (canonical or center):
        await _attach_scenery(
            payload, [(c.lat, c.lon) for c in records], cam_limit=3
        )
    return payload


@mcp.tool(annotations=_read_only("Wildfires"))
async def get_wildfires(
    near_route: str | None = None,
    center: str | None = None,
    radius_km: float = 50,
) -> dict:
    """Active California wildfires, flagged when close to a major highway.

    Data: the interagency WFIGS current-wildfire feed (NIFC) - name, size in
    acres, percent contained, discovery date. Points are each fire's ORIGIN,
    not its perimeter: a large fire can affect roads far from this point.
    Refresh: 5-minute cache; size/containment typically update once or twice
    a day. Small, fast-moving local fires may appear in CHP incident logs
    (get_incidents, type "FIRE-Report of Fire") before this feed has them.

    Filters:
    - near_route (e.g. "I-5", "101") - only fires within ~10 miles of that
      highway's corridor line.
    - center "lat,lon" with radius_km - fires around a place, regardless of
      highway.
    Without either, every active CA fire is returned, each carrying a
    `near_highways` list of major corridors within ~10 miles (empty = not
    near a covered major highway; it may still affect local roads).

    This tool does NOT know about road closures caused by fires - cross-check
    get_incidents and get_lane_closures for the affected area.
    """
    result = await get_road().wildfires()
    canonical = normalize_route(near_route) if near_route else None
    route_corridors = (
        [c for c in corr.CORRIDORS if canonical in c.routes] if canonical else []
    )
    if canonical and not route_corridors:
        return {
            "error": f"No corridor line available for {canonical}; call without "
            "near_route and check the near_highways field instead.",
            "sources": [source_status(result)],
        }
    point = None
    if center:
        point = parse_center(center)
        if point is None:
            return {"error": CENTER_FORMAT_ERROR}

    fires = []
    for f in result.records:
        near = []
        for c in corr.CORRIDORS:
            dist, _ = corr.distance_to_corridor(c, f.lat, f.lon)
            if dist <= corr.FIRE_BUFFER_METERS:
                near.append(c.routes[0])
        if canonical and canonical not in near:
            continue
        if point and haversine_meters(*point, f.lat, f.lon) > radius_km * 1000:
            continue
        d = wildfire_dict(f)
        d["near_highways"] = sorted(set(near))
        fires.append(d)

    # Refine with actual perimeters: for a big fire, the origin point can
    # sit miles inside the burn area, so distance-to-origin understates how
    # close the fire's edge is to a road or to the asked-about place. The
    # simplified ring also ships so the fire draws as its footprint.
    notes = []
    if fires and len(fires) <= 12:
        bbox = _fires_bbox(fires)
        if bbox:
            await _attach_perimeters(fires, bbox)
        if point:
            lat, lon = point
            for d in fires:
                if d.get("perimeter"):
                    edge_m = min(
                        haversine_meters(lat, lon, plat, plon)
                        for plat, plon in d["perimeter"]
                    )
                    d["perimeter_edge_km"] = round(edge_m / 1000, 1)
        if any(d.get("perimeter") for d in fires):
            notes.append(
                "perimeter is the mapped fire edge (simplified); "
                "perimeter_edge_km, when present, is measured from the "
                "queried point to that edge - prefer it over origin-point "
                "distance for large fires"
            )
    payload = {
        "count": len(fires),
        "filters": {"near_route": canonical, "center": center},
        "wildfires": fires,
        "sources": [source_status(result)],
    }
    if notes:
        payload["notes"] = notes
    return payload




@mcp.tool(annotations=_read_only("Rank busiest routes"))
async def rank_routes(by: str = "activity", limit: int = 5) -> dict:
    """Which major corridors have the most going on right now.

    Answers broad questions like "what are the busiest routes", "where is
    traffic worst", or "which highways should I avoid today" across all 17
    tracked corridors. by="activity" ranks on live events (full closures
    weigh most, then incidents, lane closures, chain controls);
    by="congestion" ranks on measured speed vs free-flow at each
    corridor's midpoint and needs the traffic feed to be configured -
    if it is not, the ranking silently falls back to activity.

    Each entry carries the counts and a one-line reason, so the answer
    can say WHY a corridor ranks where it does, not just list names.
    """
    road = get_road()
    chp_r, lcs_r, cc_r = await asyncio.gather(
        road.incidents(), road.lane_closures(), road.chain_controls(),
    )
    events = dedupe(
        [chp_feed.to_event(i) for i in chp_r.records]
        + [lcs_feed.to_event(c) for c in lcs_r.records]
        + [chains_feed.to_event(c) for c in cc_r.records]
    )

    want_congestion = by == "congestion" and tomtom_feed.api_key() is not None
    entries = []
    for corridor in corr.CORRIDORS:
        placed = corr.events_on_corridor(corridor, events)
        incidents = sum(1 for p in placed if p.event.source == "chp")
        closures = [p.event.record for p in placed if p.event.source == "lcs"]
        fulls = sum(1 for c in closures if lcs_feed.is_full_roadway_closure(c))
        chains = sum(1 for p in placed if p.event.source == "chains")
        score = incidents + len(closures) + 3 * fulls + 2 * chains
        entry = {
            "corridor": corridor.name,
            "routes": list(corridor.routes),
            "counts": {
                "incidents": incidents,
                "closures": len(closures),
                "full_closures": fulls,
                "chain_controls": chains,
            },
            "midpoint": list(corr.point_at(corridor, corr.total_length(corridor) / 2)),
        }
        bits = []
        if fulls:
            bits.append(f"{fulls} FULL closure(s)")
        if incidents:
            bits.append(f"{incidents} incident(s)")
        if len(closures) - fulls:
            bits.append(f"{len(closures) - fulls} lane closure(s)")
        if chains:
            bits.append(f"{chains} chain control(s)")
        entry["reason"] = "; ".join(bits) if bits else "quiet"
        entry["activity_score"] = score
        entries.append(entry)

    if want_congestion:
        samples = await asyncio.gather(*(
            tomtom_feed.flow_at_point(road.client, e["midpoint"][0], e["midpoint"][1])
            for e in entries
        ))
        for entry, sample in zip(entries, samples, strict=True):
            if sample and sample.get("current_mph") and sample.get("freeflow_mph"):
                ratio = sample["current_mph"] / sample["freeflow_mph"]
                entry["current_mph"] = sample["current_mph"]
                entry["freeflow_mph"] = sample["freeflow_mph"]
                entry["congestion_score"] = round(1 - ratio, 3)
        key = "congestion_score"
        entries = [e for e in entries if key in e] or entries
    else:
        key = "activity_score"

    entries.sort(key=lambda e: e.get(key, 0), reverse=True)
    limit = max(1, min(limit, 17))
    return {
        "ranked_by": key.replace("_score", ""),
        "routes": entries[:limit],
        "sources": [source_status(r) for r in (chp_r, lcs_r, cc_r)],
        "notes": [
            "scores compare corridors to each other right now; a quiet day "
            "ranks something first anyway - check the reason field"
        ],
    }


async def _live_cameras(candidates, limit: int):
    """Keep only cameras whose image is actually live.

    The feed's in-service flag is not enough: plenty of "in service"
    cameras return a placeholder frame with some variant of "camera
    offline" burned in. The reliable discriminator is freshness: live
    cameras rewrite their snapshot every minute or so, placeholders are
    files frozen at the moment the camera died. Byte size alone does
    not work - a nearly black night frame compresses under 12 KB and
    once got every live Donner camera dropped at 1 AM.
    """
    client = get_road().client
    sem = asyncio.Semaphore(6)

    async def check(cam):
        async with sem:
            try:
                resp = await client.get(
                    cam.image_url,
                    timeout=8,
                    headers={"User-Agent": "ca-roads-mcp"},
                )
            except Exception:  # noqa: BLE001 - unreachable image = offline
                return None
        content_type = resp.headers.get("content-type", "")
        if (
            resp.status_code != 200
            or not content_type.startswith("image")
            or len(resp.content) < 2_000
        ):
            return None
        modified = resp.headers.get("last-modified")
        if modified:
            try:
                age = (
                    datetime.now(UTC)
                    - parsedate_to_datetime(modified)
                ).total_seconds()
                return cam if age <= 1800 else None
            except (TypeError, ValueError):
                pass
        # No usable freshness header: fall back to the size heuristic.
        return cam if len(resp.content) >= 12_000 else None

    checked = await asyncio.gather(*(check(c) for c in candidates[: limit * 3]))
    live = [c for c in checked if c is not None][:limit]
    dropped = sum(1 for c in checked if c is None)
    return live, dropped


@mcp.tool(annotations=_read_only("Highway cameras"))
async def get_cameras(
    center: str | None = None,
    route: str | None = None,
    radius_km: float = 30,
    limit: int = 6,
) -> dict:
    """Live Caltrans roadside camera snapshots near a point or on a route.

    Data: ~3,000 in-service Caltrans cameras statewide. Every returned
    image_url was verified live moments ago (offline cameras that serve a
    placeholder frame are filtered out), so images can be shown directly.
    Snapshots refresh roughly every minute; stream_url (when present) is
    an HLS video stream.

    Filters: center "lat,lon" (required unless route is given) with
    radius_km; route (e.g. "I-80", "50") narrows to that highway. Results
    sort nearest-first when a center is given. Use a camera to let the
    user SEE conditions: fog on the pass, snow on the pavement, traffic
    density at an interchange.
    """
    if not center and not route:
        return {"error": "Pass center 'lat,lon' and/or route."}
    result = await get_road().cameras()
    records = result.records
    canonical = normalize_route(route) if route else None
    if canonical:
        records = [c for c in records if normalize_route(c.route) == canonical]
    point = None
    if center:
        point = parse_center(center)
        if point is None:
            return {"error": CENTER_FORMAT_ERROR}
        records = [
            c for c in records
            if c.lat and c.lon
            and haversine_meters(*point, c.lat, c.lon) <= radius_km * 1000
        ]
        records.sort(key=lambda c: haversine_meters(*point, c.lat, c.lon))
    live, dropped = await _live_cameras(records, max(1, min(limit, 10)))
    notes = list(result.notes)
    if dropped:
        notes.append(
            f"{dropped} nearby camera(s) were offline or serving a "
            "placeholder image and were filtered out"
        )
    return {
        "data_as_of": result.data_as_of.isoformat() if result.data_as_of else None,
        "count": len(live),
        "filters": {"center": center, "route": route, "radius_km": radius_km},
        "cameras": [camera_dict(c) for c in live],
        "notes": notes,
        "sources": [source_status(result)],
    }


@mcp.tool(annotations=_read_only("Message signs"))
async def get_road_signs(
    route: str | None = None,
    center: str | None = None,
    radius_km: float = 80,
) -> dict:
    """What Caltrans changeable message signs are displaying right now.

    Data: statewide CMS sign text, blank and out-of-service signs already
    filtered - every record is a message a driver is physically seeing.
    Signs carry the road's operational truth ("CHAINS REQUIRED 10 MI
    AHEAD", "FULL CLOSURE HWY 96 DUE TO FIRE", "PREPARE TO STOP"), often
    before the event shows up in any other feed. Refresh: ~2-minute cache.

    Filters: route (e.g. "I-80") and/or center "lat,lon" with radius_km.
    Quote sign text verbatim to the user - it is the most current and
    most local signal this server has.
    """
    result = await get_road().message_signs()
    records = [s for s in result.records if s.text]
    canonical = normalize_route(route) if route else None
    if canonical:
        records = [s for s in records if normalize_route(s.route) == canonical]
    if center:
        point = parse_center(center)
        if point is None:
            return {"error": CENTER_FORMAT_ERROR}
        records = [
            s for s in records
            if s.lat and s.lon
            and haversine_meters(*point, s.lat, s.lon) <= radius_km * 1000
        ]
        records.sort(key=lambda s: haversine_meters(*point, s.lat, s.lon))
    return {
        "data_as_of": result.data_as_of.isoformat() if result.data_as_of else None,
        "count": len(records[:25]),
        "filters": {"route": route, "center": center, "radius_km": radius_km},
        "signs": [sign_dict(s) for s in records[:25]],
        "sources": [source_status(result)],
    }


@mcp.tool(annotations=_read_only("Nearby events (nationwide)"))
async def get_nearby_events(
    center: str,
    radius_km: float = 40,
    kinds: str = "incident,closure,chain,fire",
) -> dict:
    """Live road events near a point anywhere CommuteScout covers, not
    just California: 32 states today, growing.

    Data: the same multi-state feeds the live map shows, normalized -
    state DOT incidents, roadwork and closures, chain and traction
    advisories, and nationwide wildfires. Every event names its
    publishing agency in the source field. Coverage varies by state
    (some publish roadwork only; docs/state-coverage.md has the
    matrix); states added later appear here automatically.

    For CALIFORNIA questions prefer the dedicated tools above (richer
    detail: dispatch logs, lane counts, chain levels). Use THIS tool
    for any location outside California, near a state border, or as a
    supplement when a California tool comes back empty.

    center is "lat,lon". kinds is a comma list from: incident, closure,
    chain, fire, sign, rwis, camera. radius_km caps at 160.
    """
    import math

    point = parse_center(center)
    if point is None:
        return {"error": CENTER_FORMAT_ERROR}
    radius_km = min(max(radius_km, 1.0), 160.0)
    lat, lon = point
    dlat = radius_km / 111.0
    dlon = radius_km / max(20.0, 111.0 * math.cos(math.radians(lat)))
    box = (lat - dlat, lon - dlon, lat + dlat, lon + dlon)
    want = {k.strip() for k in kinds.split(",") if k.strip()}
    from ca_roads_demo import states as expansion

    markers = await expansion.markers_for_bbox(get_road().client, box, want)
    events = []
    for m in markers:
        dist = haversine_meters(lat, lon, m["lat"], m["lon"])
        if dist > radius_km * 1000:
            continue
        events.append({
            "kind": m.get("kind"),
            "lat": round(m["lat"], 4), "lon": round(m["lon"], 4),
            "miles_away": round(dist * MILES_PER_METER, 1),
            "type": m.get("type"),
            "summary": m.get("label") or m.get("name")
            or m.get("message"),
            "route": m.get("route"),
            "closure_class": m.get("cls"),
            "source": m.get("src"),
        })
    events.sort(key=lambda e: e["miles_away"])
    trimmed = events[:80]
    payload = {
        "count": len(trimmed),
        "total_in_radius": len(events),
        "filters": {"center": center, "radius_km": radius_km,
                    "kinds": sorted(want)},
        "events": trimmed,
        "data_as_of": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    if not trimmed:
        payload["message"] = (
            "No live events in the covered feeds within this radius. "
            "If this state only publishes roadwork, quiet is normal; "
            "coverage notes: docs/state-coverage.md."
        )
    return payload


@mcp.prompt()
def road_trip_check(from_place: str, to_place: str) -> str:
    """Check road conditions for a trip between two California places."""
    return f"""\
I'm about to drive from {from_place} to {to_place}. Check current road
conditions for this trip:

1. Call check_route with from_place="{from_place}" and to_place="{to_place}".
2. If the corridor is covered, summarize what matters for a driver, in order
   along the route: chain controls first (say what level and what vehicles
   need), then full closures, then lane closures and incidents that could
   cause delays, then any wildfires near the route.
3. If check_route doesn't cover the trip, fall back to get_incidents,
   get_lane_closures, and get_chain_controls filtered to the highways the
   trip would use.
4. Report the data_as_of times and any source errors so I know how fresh
   this is. This is current status, not a forecast.
5. Close with: conditions change - verify before driving (511 or
   quickmap.dot.ca.gov).
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="CommuteScout MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="stdio for local use, http for hosted streamable HTTP",
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8080)))
    args = parser.parse_args()
    if args.transport == "http":
        import uvicorn
        from mcp.server.transport_security import TransportSecuritySettings

        from ca_roads_mcp.ratelimit import RateLimitMiddleware

        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.settings.stateless_http = True
        # The SDK's DNS-rebinding protection only allows localhost hosts by
        # default, which answers 421 behind Cloud Run's hostname. This is a
        # public, unauthenticated, read-only API served over TLS by the
        # platform; host-header validation adds nothing here.
        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        )
        app = RateLimitMiddleware(mcp.streamable_http_app())
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
