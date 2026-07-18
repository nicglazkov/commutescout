"""CHP statewide live incident feed (sa.xml).

The feed refreshes about once a minute. get() serves the last parse from an
in-memory TTL cache and refreshes in the background (stale-while-revalidate),
so a request never waits on CHP; the underlying _fetch uses conditional GET,
so an unchanged feed answers 304 and the last parse is reused.
The server truncates the document mid-record when incident volume is high, so
parsing salvages complete records instead of failing (see xmlutil).
"""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx

from ca_roads.cache import TTLCache
from ca_roads.feeds import USER_AGENT
from ca_roads.models import ChpIncident, FeedResult, RoadEvent
from ca_roads.xmlutil import iter_complete_records

CHP_URL = "https://media.chp.ca.gov/sa_xml/sa.xml"
SOURCE = "chp"
TIMEOUT_SECONDS = 10.0
# On a failed fetch, the last good parse may be served up to this old.
MAX_SERVE_SECONDS = 10 * 60
# Serve the last parse from memory for this long before a background refresh,
# so request latency is decoupled from CHP's per-call round-trip.
TTL_SECONDS = 60
# When the server truncates sa.xml (it cuts the file under high load),
# records recently seen in earlier fetches are carried forward this
# long instead of silently vanishing. A watch alert arriving 78
# minutes late traced back to exactly this: the incident's dispatch
# center sat past the cut for over an hour on a busy Friday night.
CARRY_SECONDS = 20 * 60

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
        # The full dispatch timeline ships in the feed: dispatcher
        # comments under <details> and unit lifecycle under <units>.
        details: list[tuple[str, str]] = []
        units: list[tuple[str, str]] = []
        log_details = log.find("LogDetails")
        if log_details is not None:
            for entry in log_details:
                if entry.tag == "details":
                    text = _clean(entry.findtext("IncidentDetail") or "")
                    if text:
                        details.append(
                            (_clean(entry.findtext("DetailTime") or ""), text))
                elif entry.tag == "units":
                    text = _clean(entry.findtext("UnitDetail") or "")
                    if text:
                        units.append(
                            (_clean(entry.findtext("UnitTime") or ""), text))
        incidents.append(
            ChpIncident(
                id=log_id,
                log_type=fields.get("LogType", ""),
                location=fields.get("Location", ""),
                area=fields.get("Area", ""),
                lat=coords[0],
                lon=coords[1],
                reported_at=parse_log_time(fields.get("LogTime", "")),
                location_desc=fields.get("LocationDesc", ""),
                details=tuple(details),
                units=tuple(units),
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
        self._carry: dict[str, tuple[float, ChpIncident]] = {}
        self._fetched_at: datetime | None = None
        self._fetched_monotonic: float = 0.0
        self._cache = TTLCache()

    async def get(self) -> FeedResult:
        # Serve the last parse from memory and refresh in the background so a
        # slow CHP round-trip never lands on the request path (SWR). Only a
        # cold instance fetches inline; the boot prewarm covers that.
        outcome = await self._cache.get(
            "chp", TTL_SECONDS, MAX_SERVE_SECONDS, self._fetch)
        if outcome.value is not None:
            return outcome.value
        return FeedResult(
            source=SOURCE, records=[], data_as_of=None, ok=False,
            error=outcome.error,
        )

    async def _fetch(self) -> FeedResult:
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
        if truncated:
            # One immediate cache-busted retry: when the cut came from an
            # intermediary rather than CHP's generator, a refetch often
            # returns the whole file.
            try:
                retry = await self._client.get(
                    CHP_URL, params={"_": int(time.time())},
                    headers={"User-Agent": USER_AGENT},
                    timeout=TIMEOUT_SECONDS)
                if retry.status_code == 200:
                    incidents2, truncated2 = parse_chp_xml(retry.content)
                    if len(incidents2) > len(incidents):
                        incidents, truncated = incidents2, truncated2
            except Exception:  # noqa: BLE001 - retry is best-effort
                pass
        notes = []
        now_mono = time.monotonic()
        if truncated:
            # Union with recently-seen records: a truncated file proves
            # nothing about the records behind the cut, so they stay
            # current for CARRY_SECONDS instead of flapping out.
            parsed_ids = {i.id for i in incidents}
            carried = [inc for seen_at, inc in self._carry.values()
                       if inc.id not in parsed_ids
                       and now_mono - seen_at < CARRY_SECONDS]
            incidents = [*incidents, *carried]
            notes.append(
                "CHP feed was truncated by the server; "
                f"{len(carried)} recently seen incident(s) carried forward"
            )
            print(f"WARNING chp feed truncated: parsed={len(parsed_ids)} "
                  f"carried={len(carried)}", flush=True)
            for inc in incidents:
                if inc.id in parsed_ids:
                    self._carry[inc.id] = (now_mono, inc)
        else:
            self._carry = {i.id: (now_mono, i) for i in incidents}
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
