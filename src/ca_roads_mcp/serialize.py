"""Convert feed-layer records and results into JSON-friendly dicts for tools.

Every tool response includes a ``sources`` list with per-source ``data_as_of``
timestamps and health flags, so the consuming agent can reason about
freshness and trust instead of assuming the data is live and complete.
"""

from __future__ import annotations

import re
from datetime import datetime

from ca_roads.feeds import chains as chains_feed
from ca_roads.feeds import lcs as lcs_feed
from ca_roads.feeds import wildfire as wildfire_feed
from ca_roads.models import (
    ChainControl,
    ChpIncident,
    FeedResult,
    LaneClosure,
    Wildfire,
)

SOURCE_LABELS = {
    "chp": "CHP live incidents (media.chp.ca.gov, refreshes ~1/min)",
    "lcs": "Caltrans Lane Closure System (cwwp2.dot.ca.gov, 5-min cache)",
    "chains": "Caltrans chain controls (cwwp2.dot.ca.gov, 5-min cache)",
    "wfigs": "WFIGS interagency wildfire incidents (NIFC ArcGIS, 5-min cache)",
}


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") if dt else None


def source_status(result: FeedResult) -> dict:
    status = {
        "source": result.source,
        "description": SOURCE_LABELS.get(result.source, result.source),
        "ok": result.ok,
        "data_as_of": _iso(result.data_as_of),
    }
    if result.stale:
        status["stale"] = True
    if result.error:
        status["error"] = result.error
    if result.notes:
        status["notes"] = result.notes
    return status


# "Us101 N / Ccg" or "I80 W / Mace Blvd": the letter after the route token is
# the travel direction. "NB/SB/EB/WB" tokens appear in some locations too.
_DIR_AFTER_ROUTE_RE = re.compile(
    r"\b(?:I|US|SR|CA|HWY|RT|RTE)\s*-?\s*\d{1,3}\s+([NSEW])\b", re.IGNORECASE
)
_DIR_TOKEN_RE = re.compile(r"\b([NSEW])B\b", re.IGNORECASE)
_DIR_NAMES = {"N": "northbound", "S": "southbound", "E": "eastbound", "W": "westbound"}


def direction_hint(location: str) -> str | None:
    """Travel direction parsed from a CHP free-text location, when present."""
    m = _DIR_AFTER_ROUTE_RE.search(location or "")
    if not m:
        m = _DIR_TOKEN_RE.search(location or "")
    return _DIR_NAMES[m.group(1).upper()] if m else None


def incident_dict(i: ChpIncident) -> dict:
    return {
        "id": i.id,
        "type": i.log_type,
        "location": i.location,
        "direction_hint": direction_hint(i.location),
        "area": i.area,
        "lat": i.lat,
        "lon": i.lon,
        "reported_at": _iso(i.reported_at),
    }


def closure_dict(c: LaneClosure) -> dict:
    return {
        "index": c.index,
        "route": c.route,
        "county": c.county,
        "district": c.district,
        "direction": c.direction,
        "location": c.location_name,
        "nearby_place": c.nearby_place,
        # What the record means for through traffic. "full-roadway" is the
        # only class where the road itself is closed; "ramp" closures affect
        # only that ramp/connector; "one-way-traffic" means passable with
        # flagging delays.
        "closure_class": lcs_feed.closure_class(c),
        "closure_type": c.type_of_closure,
        "facility": c.facility,
        "work_type": c.type_of_work,
        "lanes_closed": c.lanes_closed,
        "total_lanes": c.total_lanes,
        "lanes": lcs_feed.lanes_summary(c),
        "estimated_delay_minutes": c.estimated_delay_minutes,
        "duration": c.duration,
        "is_full_closure": lcs_feed.is_full_roadway_closure(c),
        "begin": {"lat": c.begin_lat, "lon": c.begin_lon},
        "end": {"lat": c.end_lat, "lon": c.end_lon},
        "scheduled_end_epoch": c.end_epoch if not c.indefinite_end else None,
        "end_is_indefinite": c.indefinite_end,
        "summary": lcs_feed.describe(c),
    }


def chain_control_dict(c: ChainControl) -> dict:
    return {
        "index": c.index,
        "route": c.route,
        "county": c.county,
        "district": c.district,
        "direction": c.direction,
        "location": c.location_name,
        "nearby_place": c.nearby_place,
        "lat": c.lat,
        "lon": c.lon,
        "level": c.status,
        "meaning": c.status_description,
        "status_updated_at": _iso(c.status_updated_at),
        "summary": chains_feed.describe(c),
    }


def wildfire_dict(f: Wildfire) -> dict:
    return {
        "id": f.id,
        "name": f.name,
        "lat": f.lat,
        "lon": f.lon,
        "size_acres": f.size_acres,
        "percent_contained": f.percent_contained,
        "discovered_at": _iso(f.discovered_at),
        "summary": wildfire_feed.describe(f),
    }
