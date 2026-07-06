"""Caltrans LCS (Lane Closure System) per-district feeds.

A closure is reported as "in place" only when CHP code 1097 (closure
established) is set and 1098 (picked up) / 1022 (canceled) are not.
Scheduled-but-not-yet-established closures are skipped to avoid false alarms.
Feeds are large (up to ~4 MB per district) and refresh on a 5-minute cache.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

import httpx

from ca_roads.cache import TTLCache
from ca_roads.feeds import USER_AGENT
from ca_roads.geo import ALL_DISTRICTS
from ca_roads.models import FeedResult, LaneClosure, RoadEvent
from ca_roads.xmlutil import child_text, iter_complete_records

SOURCE = "lcs"
TTL_SECONDS = 5 * 60
MAX_SERVE_SECONDS = 30 * 60
TIMEOUT_SECONDS = 30.0
# Closures whose scheduled end passed more than this long ago are ghost
# records that were never picked up in the system; hide them.
END_OVERRUN_GRACE_SECONDS = 4 * 3600


def feed_url(district: int) -> str:
    return f"https://cwwp2.dot.ca.gov/data/d{district}/lcs/lcsStatusD{district:02d}.xml"


def _to_float(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        return 0.0


def _to_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def _to_optional_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def parse_lcs_xml(data: bytes, district: int) -> tuple[list[LaneClosure], bool]:
    """Parse one district feed; second value is True if the document was
    malformed and only complete records were salvaged."""
    records, truncated = iter_complete_records(data, "lcs")
    closures: list[LaneClosure] = []
    for rec in records:
        index = child_text(rec, "index")
        if not index:
            continue
        closures.append(
            LaneClosure(
                index=index,
                district=district,
                route=child_text(rec, "beginRoute"),
                county=child_text(rec, "beginCounty"),
                direction=child_text(rec, "travelFlowDirection"),
                location_name=child_text(rec, "beginLocationName"),
                nearby_place=child_text(rec, "beginNearbyPlace"),
                type_of_closure=child_text(rec, "typeOfClosure"),
                type_of_work=child_text(rec, "typeOfWork"),
                lanes_closed=child_text(rec, "lanesClosed"),
                begin_lat=_to_float(child_text(rec, "beginLatitude")),
                begin_lon=_to_float(child_text(rec, "beginLongitude")),
                end_lat=_to_float(child_text(rec, "endLatitude")),
                end_lon=_to_float(child_text(rec, "endLongitude")),
                begin_milepost=_to_optional_float(child_text(rec, "beginMilepost")),
                end_milepost=_to_optional_float(child_text(rec, "endMilepost")),
                start_epoch=_to_int(child_text(rec, "closureStartEpoch")),
                end_epoch=_to_int(child_text(rec, "closureEndEpoch")),
                indefinite_end=child_text(rec, "isClosureEndIndefinite") == "true",
                is_1097=child_text(rec, "isCode1097") == "true",
                is_1098=child_text(rec, "isCode1098") == "true",
                is_1022=child_text(rec, "isCode1022") == "true",
                epoch_1097=_to_int(child_text(rec, "code1097Epoch")),
            )
        )
    return closures, truncated


def is_shoulder_only(lanes_closed: str) -> bool:
    """True when only shoulders/median are closed (no travel lane affected),
    e.g. 'RShoulder'. '3, RShoulder', 'All', 'Left HOV', turn-lane and
    auxiliary-lane closures still count as lane closures."""
    if not lanes_closed:
        return False
    lowered = lanes_closed.lower()
    if any(word in lowered for word in ("all", "hov", "turn", "aux")):
        return False
    return not any(ch.isdigit() for ch in lanes_closed)


def is_active(closure: LaneClosure, now_epoch: int | None = None) -> bool:
    """In place right now: 1097 established, not picked up, not canceled,
    coordinates present, affects a travel lane, and not a ghost record whose
    scheduled end passed more than the grace period ago."""
    if now_epoch is None:
        now_epoch = int(time.time())
    if not closure.is_1097 or closure.is_1098 or closure.is_1022:
        return False
    if closure.begin_lat == 0.0 and closure.begin_lon == 0.0:
        return False
    if is_shoulder_only(closure.lanes_closed):
        return False
    return (
        closure.indefinite_end
        or closure.end_epoch <= 0
        or now_epoch <= closure.end_epoch + END_OVERRUN_GRACE_SECONDS
    )


def describe(closure: LaneClosure) -> str:
    what = (
        "FULL CLOSURE"
        if closure.type_of_closure.lower() == "full"
        else f"{closure.type_of_closure} closure"
    )
    parts = []
    if closure.route:
        parts.append(closure.route)
    parts.append(what)
    text = " ".join(parts)
    if closure.location_name:
        text += f" @ {closure.location_name}"
    if closure.nearby_place:
        text += f" ({closure.nearby_place})"
    if closure.lanes_closed and closure.type_of_closure.lower() != "full":
        text += f", lanes: {closure.lanes_closed}"
    return text


def to_event(closure: LaneClosure) -> RoadEvent:
    reported = closure.epoch_1097 or closure.start_epoch
    return RoadEvent(
        source=SOURCE,
        id=f"lcs_{closure.index}",
        family="closure",
        lat=closure.begin_lat,
        lon=closure.begin_lon,
        summary=describe(closure),
        reported_at=datetime.fromtimestamp(reported, UTC) if reported > 0 else None,
        record=closure,
    )


class LcsSource:
    """Per-district cached fetcher; districts are fetched concurrently."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self._cache = TTLCache()

    async def _fetch_district(self, district: int) -> tuple[list[LaneClosure], bool]:
        resp = await self._client.get(
            feed_url(district),
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return parse_lcs_xml(resp.content, district)

    async def get(self, districts: tuple[int, ...] | list[int] | None = None) -> FeedResult:
        wanted = tuple(districts) if districts else ALL_DISTRICTS
        outcomes = await asyncio.gather(
            *(
                self._cache.get(
                    d,
                    TTL_SECONDS,
                    MAX_SERVE_SECONDS,
                    lambda d=d: self._fetch_district(d),
                )
                for d in wanted
            )
        )
        records: list[LaneClosure] = []
        notes: list[str] = []
        errors: list[str] = []
        data_as_of = None
        any_served = False
        stale = False
        for district, outcome in zip(wanted, outcomes, strict=True):
            if not outcome.served:
                errors.append(f"D{district}: {outcome.error}")
                notes.append(f"district {district} feed unavailable ({outcome.error})")
                continue
            any_served = True
            closures, truncated = outcome.value
            records.extend(closures)
            if truncated:
                notes.append(f"district {district} feed was malformed; partial records salvaged")
            if outcome.stale:
                stale = True
                notes.append(f"district {district} live fetch failed; serving cached data")
            if data_as_of is None or outcome.fetched_at < data_as_of:
                data_as_of = outcome.fetched_at
        return FeedResult(
            source=SOURCE,
            records=records,
            data_as_of=data_as_of,
            ok=any_served,
            stale=stale,
            error="; ".join(errors) if errors else None,
            notes=notes,
        )
