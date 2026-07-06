"""CHP statewide live incident feed (sa.xml).

The feed refreshes about once a minute and is fetched per request with
conditional GET: an unchanged feed answers 304 and the last parse is reused.
The server truncates the document mid-record when incident volume is high, so
parsing salvages complete records instead of failing (see xmlutil).
"""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx

from ca_roads.feeds import USER_AGENT
from ca_roads.models import ChpIncident, FeedResult, RoadEvent
from ca_roads.xmlutil import iter_complete_records

CHP_URL = "https://media.chp.ca.gov/sa_xml/sa.xml"
SOURCE = "chp"
TIMEOUT_SECONDS = 10.0
# On a failed fetch, the last good parse may be served up to this old.
MAX_SERVE_SECONDS = 10 * 60

TZ_PACIFIC = ZoneInfo("America/Los_Angeles")

# Observed LogTime formats, newest first ("Jul  5 2026  9:53PM" currently).
_TIME_FORMATS = (
    "%b %d %Y %I:%M%p",
    "%b %d %Y %I:%M %p",
    "%m/%d/%Y %I:%M %p",
    "%m/%d/%Y %H:%M",
)


def _clean(value: str) -> str:
    """Strip the quotes CHP wraps every value in."""
    return value.strip().strip('"').strip()


def parse_log_time(raw: str) -> datetime | None:
    """Parse a CHP LogTime into an aware Pacific datetime (None on failure).

    The feed pads single-digit days/hours with extra spaces; runs of
    whitespace are collapsed before parsing.
    """
    normalized = re.sub(r"\s+", " ", _clean(raw)).strip()
    if not normalized:
        return None
    for fmt in _TIME_FORMATS:
        try:
            return datetime.strptime(normalized, fmt).replace(tzinfo=TZ_PACIFIC)
        except ValueError:
            continue
    return None


def parse_latlon(raw: str) -> tuple[float, float] | None:
    """'38531446:121344046' -> (38.531446, -121.344046).

    The feed encodes western longitude as a positive value; negate via abs so
    an explicit minus sign (if CHP ever adds one) doesn't flip it eastward.
    """
    parts = _clean(raw).split(":")
    if len(parts) != 2:
        return None
    try:
        lat = int(parts[0].strip()) / 1_000_000.0
        lon = -abs(int(parts[1].strip()) / 1_000_000.0)
    except ValueError:
        return None
    if lat == 0.0 or lon == 0.0:
        return None
    return lat, lon


def parse_chp_xml(data: bytes) -> tuple[list[ChpIncident], bool]:
    """Parse sa.xml into incidents; second value is True when the feed was
    truncated and only complete records were salvaged. Records without valid
    coordinates are skipped."""
    records, truncated = iter_complete_records(data, "Log")
    incidents: list[ChpIncident] = []
    for log in records:
        log_id = (log.get("ID") or "").strip()
        if not log_id:
            continue
        fields = {child.tag: _clean(child.text or "") for child in log}
        coords = parse_latlon(fields.get("LATLON", ""))
        if coords is None:
            continue
        incidents.append(
            ChpIncident(
                id=log_id,
                log_type=fields.get("LogType", ""),
                location=fields.get("Location", ""),
                area=fields.get("Area", ""),
                lat=coords[0],
                lon=coords[1],
                reported_at=parse_log_time(fields.get("LogTime", "")),
            )
        )
    return incidents, truncated


def to_event(incident: ChpIncident) -> RoadEvent:
    lowered = incident.log_type.lower()
    if "collision" in lowered:
        family = "accident"
    elif "closure" in lowered:
        family = "closure"
    else:
        family = "incident"
    place = incident.location
    if incident.area:
        place = f"{place} ({incident.area})" if place else incident.area
    return RoadEvent(
        source=SOURCE,
        id=f"chp_{incident.id}",
        family=family,
        lat=incident.lat,
        lon=incident.lon,
        summary=f"{incident.log_type} @ {place}" if place else incident.log_type,
        reported_at=incident.reported_at,
        record=incident,
    )


class ChpSource:
    """Per-request fetcher with conditional GET and last-good fallback."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self._etag: str | None = None
        self._last_modified: str | None = None
        self._last_good: list[ChpIncident] | None = None
        self._last_good_notes: list[str] = []
        self._fetched_at: datetime | None = None
        self._fetched_monotonic: float = 0.0

    async def get(self) -> FeedResult:
        headers = {"User-Agent": USER_AGENT}
        # Only send validators when we hold a cached parse; otherwise a 304
        # would leave nothing to serve.
        if self._last_good is not None:
            if self._etag:
                headers["If-None-Match"] = self._etag
            if self._last_modified:
                headers["If-Modified-Since"] = self._last_modified
        try:
            resp = await self._client.get(CHP_URL, headers=headers, timeout=TIMEOUT_SECONDS)
            if resp.status_code == 304 and self._last_good is not None:
                self._stamp()
                return self._result(self._last_good, self._last_good_notes)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001 - serve last good on any fetch failure
            return self._fallback(f"{type(exc).__name__}: {exc}")

        incidents, truncated = parse_chp_xml(resp.content)
        notes = []
        if truncated:
            notes.append(
                "CHP feed was truncated by the server; only complete records were parsed"
            )
        self._etag = resp.headers.get("ETag")
        self._last_modified = resp.headers.get("Last-Modified")
        self._last_good = incidents
        self._last_good_notes = notes
        self._stamp()
        return self._result(incidents, notes)

    def _stamp(self) -> None:
        self._fetched_at = datetime.now(UTC)
        self._fetched_monotonic = time.monotonic()

    def _result(self, incidents: list[ChpIncident], notes: list[str]) -> FeedResult:
        return FeedResult(
            source=SOURCE,
            records=list(incidents),
            data_as_of=self._fetched_at,
            notes=list(notes),
        )

    def _fallback(self, error: str) -> FeedResult:
        age = time.monotonic() - self._fetched_monotonic
        if self._last_good is not None and age <= MAX_SERVE_SECONDS:
            return FeedResult(
                source=SOURCE,
                records=list(self._last_good),
                data_as_of=self._fetched_at,
                stale=True,
                error=error,
                notes=[*self._last_good_notes, "live fetch failed; serving last good data"],
            )
        return FeedResult(
            source=SOURCE, records=[], data_as_of=None, ok=False, error=error
        )
