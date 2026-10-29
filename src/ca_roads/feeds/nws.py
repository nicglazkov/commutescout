"""National Weather Service alerts, queried by point.

Zone-based alerts cover huge areas; resolving zone polygons costs a request
per zone. Querying api.weather.gov/alerts/active?point= per sampled corridor
point is bounded (a route needs 3 points) and returns exactly the alerts a
driver there is under. Points are rounded before caching so nearby queries
share entries. Failures return empty: weather context must never break a
road report.
"""

from __future__ import annotations

import time

import httpx

USER_AGENT = "ca-roads-mcp (github.com/nicglazkov/ca-roads-mcp)"
ALERTS_URL = "https://api.weather.gov/alerts/active"
TIMEOUT_SECONDS = 10.0
TTL_SECONDS = 300.0

# Alert types that matter to a driver; everything else (beach hazards,
# air quality) is noise in a road report.
ROAD_EVENTS = (
    "winter", "snow", "blizzard", "ice", "freez", "wind", "dust", "flood",
    "fire weather", "red flag", "fog", "storm", "heat", "avalanche",
)

_cache: dict[tuple[float, float], tuple[float, list[dict]]] = {}


def _road_relevant(event: str) -> bool:
    lowered = event.lower()
    return any(k in lowered for k in ROAD_EVENTS)


async def alerts_at_points(
    client: httpx.AsyncClient, points: list[tuple[float, float]]
) -> list[dict]:
    """Active road-relevant alerts covering any of the given points,
    deduplicated by alert id."""
    seen: dict[str, dict] = {}
    now = time.monotonic()
    rounded = {(round(lat, 1), round(lon, 1)) for lat, lon in points}
    for point in sorted(rounded):
        cached = _cache.get(point)
        if cached and now - cached[0] < TTL_SECONDS:
            features = cached[1]
        else:
            try:
                resp = await client.get(
                    ALERTS_URL,
                    params={"point": f"{point[0]},{point[1]}"},
                    headers={"User-Agent": USER_AGENT},
                    timeout=TIMEOUT_SECONDS,
                )
                resp.raise_for_status()
                features = resp.json().get("features", [])
                _cache[point] = (now, features)
            except Exception:  # noqa: BLE001 - context source, never fatal
                continue
        for feature in features:
            props = feature.get("properties") or {}
            if not _road_relevant(props.get("event", "")):
                continue
            alert_id = feature.get("id") or props.get("id", "")
            if alert_id in seen:
                continue
            seen[alert_id] = {
                "event": props.get("event"),
                "severity": props.get("severity"),
                "headline": props.get("headline"),
                "areas": (props.get("areaDesc") or "")[:160],
                "ends": props.get("ends") or props.get("expires"),
            }
    return list(seen.values())


# ── Hourly forecast ──────────────────────────────────────────────────────────
# Two requests per place: /points resolves the forecast grid (and the
# local time zone, which the trip tools need to speak in local time),
# then the grid's hourly forecast. The grid for a point never moves,
# so /points caches for a day; the forecast refreshes about hourly.

POINTS_URL = "https://api.weather.gov/points/{lat:.4f},{lon:.4f}"
POINT_TTL_SECONDS = 24 * 3600.0
FORECAST_TTL_SECONDS = 30 * 60.0
_CACHE_MAX = 1000
_points: dict[tuple[float, float], tuple[float, dict | None]] = {}
_hourly: dict[str, tuple[float, list[dict]]] = {}


def _bounded_put(cache: dict, key, value) -> None:
    if len(cache) >= _CACHE_MAX:
        cache.pop(next(iter(cache)))
    cache[key] = value


async def point_info(
    client: httpx.AsyncClient, lat: float, lon: float
) -> dict | None:
    """The NWS grid for a point: time zone, place name and hourly
    forecast URL, or None outside NWS coverage or on failure."""
    key = (round(lat, 2), round(lon, 2))
    now = time.monotonic()
    hit = _points.get(key)
    if hit and now - hit[0] < POINT_TTL_SECONDS:
        return hit[1]
    try:
        resp = await client.get(
            POINTS_URL.format(lat=key[0], lon=key[1]),
            headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"},
            timeout=TIMEOUT_SECONDS,
        )
        if resp.status_code == 404:  # outside NWS coverage: definitive
            _bounded_put(_points, key, (now, None))
            return None
        resp.raise_for_status()
        props = resp.json().get("properties") or {}
    except Exception:  # noqa: BLE001 - context source, never fatal
        return None
    rel = ((props.get("relativeLocation") or {}).get("properties") or {})
    info = {
        "time_zone": props.get("timeZone"),
        "forecast_hourly": props.get("forecastHourly"),
        "place": ", ".join(x for x in (rel.get("city"), rel.get("state")) if x)
        or None,
    }
    _bounded_put(_points, key, (now, info))
    return info


def _mph(wind: str | None) -> int | None:
    """Top of a "10 to 15 mph" range, as an int."""
    if not wind:
        return None
    nums = [int(n) for n in wind.replace("mph", "").replace("to", " ").split()
            if n.isdigit()]
    return max(nums) if nums else None


async def hourly_forecast(
    client: httpx.AsyncClient, lat: float, lon: float, hours: int = 48
) -> list[dict]:
    """The next ``hours`` hourly periods for a point, normalized, or []."""
    info = await point_info(client, lat, lon)
    url = (info or {}).get("forecast_hourly")
    if not url:
        return []
    now = time.monotonic()
    hit = _hourly.get(url)
    if hit and now - hit[0] < FORECAST_TTL_SECONDS:
        periods = hit[1]
    else:
        try:
            resp = await client.get(
                url, headers={"User-Agent": USER_AGENT,
                              "Accept": "application/geo+json"},
                timeout=TIMEOUT_SECONDS)
            resp.raise_for_status()
            raw = (resp.json().get("properties") or {}).get("periods") or []
        except Exception:  # noqa: BLE001 - context source, never fatal
            return []
        periods = []
        for p in raw:
            pop = (p.get("probabilityOfPrecipitation") or {}).get("value")
            periods.append({
                "start": p.get("startTime"),
                "temp_f": p.get("temperature")
                if p.get("temperatureUnit", "F") == "F" else None,
                "precip_pct": pop,
                "wind_mph": _mph(p.get("windSpeed")),
                "forecast": p.get("shortForecast"),
                "daytime": p.get("isDaytime"),
            })
        _bounded_put(_hourly, url, (now, periods))
    return periods[:hours]


# Forecast words that change a drive, worst first.
DRIVING_HAZARDS = ("blizzard", "freezing", "ice", "sleet", "snow", "thunder",
                   "fog", "heavy rain", "rain", "showers", "drizzle", "smoke",
                   "dust", "wind")


def driving_hazard(period: dict) -> str | None:
    """The first driving-relevant word in a period's forecast, or a
    strong-wind flag, or None for an uneventful hour."""
    text = (period.get("forecast") or "").lower()
    for word in DRIVING_HAZARDS:
        if word in text:
            return word
    wind = period.get("wind_mph")
    if isinstance(wind, int) and wind >= 30:
        return "wind"
    return None
