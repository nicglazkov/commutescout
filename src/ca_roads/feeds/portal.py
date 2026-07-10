"""Caltrans CWWP portal feeds: CMS signs, CCTV cameras, RWIS road weather.

All three share the same per-district JSON layout on cwwp2.dot.ca.gov (a
"data" array of single-key wrapper objects), so one module handles the
fetching and each feed contributes a parser. Same availability rules as
the chain feed: a district answering 404 or 500 has no feed, which is an
empty result, not an error.

RWIS values arrive in NTCIP units (temperatures in tenths of a degree C,
wind in tenths of m/s, visibility in decimeters) with large sentinel
numbers meaning "not reported"; conversion and sentinel filtering happen
here so consumers see plain units or None.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime

import httpx

from ca_roads.cache import TTLCache
from ca_roads.geo import ALL_DISTRICTS
from ca_roads.models import Camera, CmsSign, FeedResult, RwisStation

USER_AGENT = "ca-roads-mcp (github.com/nicglazkov/ca-roads-mcp)"
TIMEOUT_SECONDS = 20.0
TTL_SECONDS = 150.0
MAX_SERVE_SECONDS = 900.0

_NO_FEED = "no-feed"

# NTCIP "not reported" sentinels seen across sensor fields.
_SENTINELS = {65535.0, 32767.0, 10001.0, 1001.0, -9999.0}


def feed_url(kind: str, district: int) -> str:
    return (
        f"https://cwwp2.dot.ca.gov/data/d{district}/{kind}/"
        f"{kind}StatusD{district:02d}.json"
    )


def _float(value) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if f in _SENTINELS else f


def _ntcip(value, scale: float, limit: float) -> float | None:
    """Convert a tenths-unit NTCIP value; drop sentinels and absurdities."""
    f = _float(value)
    if f is None or abs(f * scale) > limit:
        return None
    return round(f * scale, 1)


def parse_cms(payload: bytes, district: int) -> list[CmsSign]:
    # In-service signs, blank ones included with empty text: a blank sign
    # still exists on the road, and the map offers showing them.
    signs: list[CmsSign] = []
    for row in json.loads(payload).get("data", []):
        cms = row.get("cms") or {}
        message = cms.get("message") or {}
        if str(cms.get("inService")).lower() != "true":
            continue
        lines: list[str] = []
        if message.get("display", "Blank") != "Blank":
            for phase in ("phase1", "phase2"):
                block = message.get(phase) or {}
                for i in (1, 2, 3):
                    line = (block.get(f"{phase}Line{i}") or "").strip()
                    if line:
                        lines.append(line)
        loc = cms.get("location") or {}
        signs.append(CmsSign(
            index=str(cms.get("index", "")),
            district=district,
            route=loc.get("route", "") or "",
            county=loc.get("county", "") or "",
            nearby_place=loc.get("nearbyPlace", "") or "",
            direction=loc.get("direction", "") or "",
            lat=_float(loc.get("latitude")),
            lon=_float(loc.get("longitude")),
            text=" / ".join(lines),
        ))
    return signs


def parse_cctv(payload: bytes, district: int) -> list[Camera]:
    cameras: list[Camera] = []
    for row in json.loads(payload).get("data", []):
        cctv = row.get("cctv") or {}
        if str(cctv.get("inService")).lower() != "true":
            continue
        image = ((cctv.get("imageData") or {}).get("static") or {})
        image_url = image.get("currentImageURL", "") or ""
        if not image_url:
            continue
        loc = cctv.get("location") or {}
        cameras.append(Camera(
            index=str(cctv.get("index", "")),
            district=district,
            route=loc.get("route", "") or "",
            county=loc.get("county", "") or "",
            nearby_place=loc.get("nearbyPlace", "") or "",
            location_name=loc.get("locationName", "") or "",
            direction=loc.get("direction", "") or "",
            lat=_float(loc.get("latitude")),
            lon=_float(loc.get("longitude")),
            image_url=image_url,
            stream_url=(cctv.get("imageData") or {}).get("streamingVideoURL", "") or "",
        ))
    return cameras


def parse_rwis(payload: bytes, district: int) -> list[RwisStation]:
    stations: list[RwisStation] = []
    for row in json.loads(payload).get("data", []):
        rwis = row.get("rwis") or {}
        if str(rwis.get("inService")).lower() != "true":
            continue
        loc = rwis.get("location") or {}
        data = rwis.get("rwisData") or {}
        temps = data.get("temperatureData") or {}
        air = None
        for entry in temps.get("essTemperatureSensorTable") or []:
            sensor = entry.get("essTemperatureSensorEntry") or {}
            air = _ntcip(sensor.get("essAirTemperature"), 0.1, 70)
            if air is not None:
                break
        surface = None
        pave = data.get("pavementSensorData") or {}
        for entry in pave.get("essPavementSensorTable") or []:
            sensor = entry.get("essPavementSensorEntry") or {}
            surface = _ntcip(sensor.get("essSurfaceTemperature"), 0.1, 90)
            if surface is not None:
                break
        wind = data.get("windData") or {}
        vis = data.get("visibilityData") or {}
        precip = data.get("humidityPrecipData") or {}
        stations.append(RwisStation(
            index=str(rwis.get("index", "")),
            district=district,
            route=loc.get("route", "") or "",
            county=loc.get("county", "") or "",
            location_name=loc.get("locationName", "") or "",
            lat=_float(loc.get("latitude")),
            lon=_float(loc.get("longitude")),
            air_temp_c=air,
            surface_temp_c=surface,
            wind_avg_mph=_ntcip(wind.get("essAvgWindSpeed"), 0.2237, 150),
            wind_gust_mph=_ntcip(wind.get("essMaxWindGustSpeed"), 0.2237, 200),
            visibility_m=_ntcip(vis.get("essVisibility"), 0.1, 100_000),
            precip_rate=_float(precip.get("essPrecipRate")),
        ))
    return stations


class PortalSource:
    """Per-district cached fetcher for one portal feed kind."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        kind: str,
        parser: Callable[[bytes, int], list],
        source_name: str,
    ) -> None:
        self._client = client
        self._kind = kind
        self._parser = parser
        self._source_name = source_name
        self._cache = TTLCache()

    async def _fetch_district(self, district: int):
        resp = await self._client.get(
            feed_url(self._kind, district),
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_SECONDS,
        )
        if resp.status_code in (404, 500):
            return _NO_FEED
        resp.raise_for_status()
        return self._parser(resp.content, district)

    async def get(
        self, districts: tuple[int, ...] | list[int] | None = None
    ) -> FeedResult:
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
        records: list = []
        notes: list[str] = []
        errors: list[str] = []
        any_served = False
        stale = False
        for district, outcome in zip(wanted, outcomes, strict=True):
            if not outcome.served:
                errors.append(f"D{district}: {outcome.error}")
                notes.append(f"district {district} feed unavailable ({outcome.error})")
                continue
            any_served = True
            stale = stale or outcome.stale
            if outcome.value == _NO_FEED:
                continue
            records.extend(outcome.value)
        return FeedResult(
            source=self._source_name,
            records=records,
            data_as_of=datetime.now(UTC),
            ok=any_served,
            stale=stale,
            error="; ".join(errors) if not any_served and errors else None,
            notes=notes,
        )
