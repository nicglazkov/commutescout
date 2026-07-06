"""Normalized record types returned by the feed layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ChpIncident:
    """One live CHP incident from the statewide sa.xml feed."""

    id: str
    log_type: str
    location: str
    area: str
    lat: float
    lon: float
    reported_at: datetime | None


@dataclass(frozen=True)
class LaneClosure:
    """One Caltrans LCS closure record (one scheduled window of one closure ID).

    ``is_1097``/``is_1098``/``is_1022`` are the CHP status codes: 1097 means the
    closure is physically established, 1098 picked up, 1022 canceled. A closure
    is "in place now" only when 1097 is set and 1098/1022 are not.
    """

    index: str
    district: int
    route: str
    county: str
    direction: str
    location_name: str
    nearby_place: str
    type_of_closure: str
    facility: str
    type_of_work: str
    lanes_closed: str
    total_lanes: int | None
    estimated_delay_minutes: int | None
    duration: str
    begin_lat: float
    begin_lon: float
    end_lat: float
    end_lon: float
    begin_milepost: float | None
    end_milepost: float | None
    start_epoch: int
    end_epoch: int
    indefinite_end: bool
    is_1097: bool
    is_1098: bool
    is_1022: bool
    epoch_1097: int


@dataclass(frozen=True)
class ChainControl:
    """One chain-control checkpoint from a Caltrans district cc feed.

    ``status`` is R-0 (none), R-1 (chains or snow tires), R-2 (chains required
    except 4WD/AWD with snow tires), or R-3 (chains on all vehicles).
    """

    index: str
    district: int
    route: str
    county: str
    direction: str
    location_name: str
    nearby_place: str
    lat: float
    lon: float
    in_service: bool
    status: str
    status_description: str
    status_updated_at: datetime | None


@dataclass(frozen=True)
class Wildfire:
    """One active wildfire from the WFIGS current-incidents layer.

    The point is the fire's origin, not its perimeter: a large fire can affect
    roads many miles from this point.
    """

    id: str
    name: str
    lat: float
    lon: float
    size_acres: float | None
    percent_contained: float | None
    discovered_at: datetime | None


@dataclass(frozen=True)
class RoadEvent:
    """Source-agnostic view of one road-affecting event, used for cross-source
    deduplication and corridor assembly."""

    source: str  # "chp" | "lcs" | "chains" | "wfigs"
    id: str
    family: str  # "accident" | "incident" | "closure" | "chains" | "fire"
    lat: float
    lon: float
    summary: str
    reported_at: datetime | None
    record: object = field(compare=False, default=None)


@dataclass
class FeedResult:
    """What a source returns: records plus enough health metadata for an agent
    to reason about freshness and trust.

    ``ok`` is False only when nothing could be served (no fresh fetch and no
    usable cache). ``stale`` means records came from a cache older than the
    refresh interval because the live fetch failed. ``notes`` carries explicit,
    human-readable feed anomalies (truncated feed, district feed missing, ...);
    feed problems are surfaced here instead of silently returning zero records.
    """

    source: str
    records: list
    data_as_of: datetime | None
    ok: bool = True
    stale: bool = False
    error: str | None = None
    notes: list[str] = field(default_factory=list)
