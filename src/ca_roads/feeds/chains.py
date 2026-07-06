"""Caltrans chain-control (winter driving) per-district feeds.

Same CWWP portal and district shape as the LCS feeds. Each record is a fixed
checkpoint on a mountain route with a status: R-0 (no controls), R-1 (chains
or snow tires), R-2 (chains required except 4WD/AWD with snow tires), R-3
(chains on all vehicles). Off-season every record is R-0.

Flatland districts (4, 5, 12) publish no chain-control feed at all and answer
404/500; that means "no chain-control checkpoints in this district", not an
error, and is cached like a normal empty result.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from ca_roads.cache import TTLCache
from ca_roads.feeds import USER_AGENT
from ca_roads.geo import ALL_DISTRICTS
from ca_roads.models import ChainControl, FeedResult, RoadEvent
from ca_roads.xmlutil import child_text, iter_complete_records

SOURCE = "chains"
TTL_SECONDS = 5 * 60
MAX_SERVE_SECONDS = 30 * 60
TIMEOUT_SECONDS = 30.0

TZ_PACIFIC = ZoneInfo("America/Los_Angeles")

# Sentinel cached for districts that publish no chain-control feed.
_NO_FEED = "no-feed"


def feed_url(district: int) -> str:
    return f"https://cwwp2.dot.ca.gov/data/d{district}/cc/ccStatusD{district:02d}.xml"


def _to_float(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        return 0.0


def _parse_status_time(date: str, time_str: str) -> datetime | None:
    if not date or not time_str:
        return None
    try:
        return datetime.strptime(f"{date} {time_str}", "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=TZ_PACIFIC
        )
    except ValueError:
        return None


def parse_cc_xml(data: bytes, district: int) -> tuple[list[ChainControl], bool]:
    records, truncated = iter_complete_records(data, "cc")
    controls: list[ChainControl] = []
    for rec in records:
        index = child_text(rec, "index")
        if not index:
            continue
        controls.append(
            ChainControl(
                index=index,
                district=district,
                route=child_text(rec, "route"),
                county=child_text(rec, "county"),
                direction=child_text(rec, "direction"),
                location_name=child_text(rec, "locationName"),
                nearby_place=child_text(rec, "nearbyPlace"),
                lat=_to_float(child_text(rec, "latitude")),
                lon=_to_float(child_text(rec, "longitude")),
                in_service=child_text(rec, "inService").lower() == "true",
                status=child_text(rec, "status"),
                status_description=child_text(rec, "statusDescription"),
                status_updated_at=_parse_status_time(
                    child_text(rec, "statusDate"), child_text(rec, "statusTime")
                ),
            )
        )
    return controls, truncated


def is_active(control: ChainControl) -> bool:
    """Active = in service, has coordinates, and a level above R-0."""
    if not control.in_service:
        return False
    if control.lat == 0.0 and control.lon == 0.0:
        return False
    if not control.status:
        return False
    return control.status.upper() != "R-0"


def describe(control: ChainControl) -> str:
    text = f"Chains {control.status}"
    if control.route:
        text += f" on {control.route}"
    if control.location_name:
        text += f" @ {control.location_name}"
    if control.nearby_place:
        text += f" ({control.nearby_place})"
    return text


def to_event(control: ChainControl) -> RoadEvent:
    return RoadEvent(
        source=SOURCE,
        id=f"cc_{control.index}",
        family="chains",
        lat=control.lat,
        lon=control.lon,
        summary=describe(control),
        reported_at=control.status_updated_at,
        record=control,
    )


class ChainSource:
    """Per-district cached fetcher; districts are fetched concurrently."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self._cache = TTLCache()

    async def _fetch_district(self, district: int) -> tuple[list[ChainControl], bool] | str:
        resp = await self._client.get(
            feed_url(district),
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_SECONDS,
        )
        # Districts without mountain routes publish no feed and answer 404 or
        # 500 permanently. Cache that as a normal empty result so it isn't
        # re-requested on every call or reported as a red failure.
        if resp.status_code in (404, 500):
            return _NO_FEED
        resp.raise_for_status()
        return parse_cc_xml(resp.content, district)

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
        records: list[ChainControl] = []
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
            if outcome.value == _NO_FEED:
                continue
            controls, truncated = outcome.value
            records.extend(controls)
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
