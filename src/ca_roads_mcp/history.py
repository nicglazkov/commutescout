"""What usually happens on a road: the event archive, read back.

The watch checker has written every incident and closure it saw,
nationwide, to BigQuery since 2026-07-12 (ca_roads_demo/archive.py).
This module turns that log into patterns for one place or one route:
how many incidents start in each local hour and weekday, which kinds
are common, and how long they usually last. It is the "typical day"
that sits next to the live picture and next to TomTom's travel-time
profiles in the trip tools.

One query per question, scanning only the requested window, capped in
bytes and per day, and cached for hours: history does not change
quickly. Any failure (no permission, no client library, a timeout)
answers ``{"available": False, ...}`` and the tools carry on without
it.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import statistics
import time
from collections import Counter
from datetime import UTC, datetime, timedelta

from ca_roads.budget import UPSTREAM

log = logging.getLogger(__name__)

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "ca-roads-mcp")
TABLE = f"{PROJECT}.{os.environ.get('ARCHIVE_DATASET', 'events')}." + \
    os.environ.get("ARCHIVE_TABLE", "event_log")
ARCHIVE_START = datetime(2026, 7, 12, tzinfo=UTC)
HISTORY_DAILY = int(os.environ.get("MCP_HISTORY_DAILY", "300"))
MAX_BYTES = 3 * 1024**3
QUERY_TIMEOUT_SECONDS = 25.0
TTL_SECONDS = 6 * 3600.0
MAX_ROWS = 20_000
_CACHE_MAX = 300
_cache: dict[tuple, tuple[float, dict]] = {}
_client = None
_warned = False

WEEKDAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday")

SQL = f"""
WITH ev AS (
  SELECT event_id, ANY_VALUE(kind) AS kind, ANY_VALUE(title) AS title,
         MIN(first_seen) AS t0, MAX(seen_at) AS t1
  FROM `{TABLE}`
  WHERE seen_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
    AND kind IN ('incident', 'closure')
    AND lat BETWEEN @s AND @n AND lon BETWEEN @w AND @e
    AND ST_DWITHIN(ST_GEOGPOINT(lon, lat), ST_GEOGFROMTEXT(@shape), @meters)
  GROUP BY event_id
)
SELECT kind, title,
       EXTRACT(DAYOFWEEK FROM t0 AT TIME ZONE @tz) AS dow,
       EXTRACT(HOUR FROM t0 AT TIME ZONE @tz) AS hr,
       TIMESTAMP_DIFF(t1, t0, MINUTE) AS minutes
FROM ev
WHERE t0 >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
LIMIT {MAX_ROWS}
"""


def _bq():
    global _client
    if _client is None:
        from google.cloud import bigquery

        _client = bigquery.Client(project=PROJECT)
    return _client


def _wkt(points: list[tuple[float, float]]) -> str:
    if len(points) == 1:
        lat, lon = points[0]
        return f"POINT({lon:.5f} {lat:.5f})"
    return "LINESTRING(" + ", ".join(f"{lon:.5f} {lat:.5f}"
                                     for lat, lon in points) + ")"


def _thin(points: list, keep: int = 80) -> list[tuple[float, float]]:
    if len(points) <= keep:
        return [(float(p[0]), float(p[1])) for p in points]
    step = (len(points) - 1) / (keep - 1)
    return [(float(points[round(i * step)][0]), float(points[round(i * step)][1]))
            for i in range(keep)]


def _run(points: list[tuple[float, float]], meters: float, days: int,
         tz: str) -> list[dict]:
    from google.cloud import bigquery

    pad = meters / 111_000 + 0.01
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    lon_pad = pad / max(0.2, abs(math.cos(math.radians(sum(lats) / len(lats)))))
    params = [
        bigquery.ScalarQueryParameter("days", "INT64", days),
        bigquery.ScalarQueryParameter("s", "FLOAT64", min(lats) - pad),
        bigquery.ScalarQueryParameter("n", "FLOAT64", max(lats) + pad),
        bigquery.ScalarQueryParameter("w", "FLOAT64", min(lons) - lon_pad),
        bigquery.ScalarQueryParameter("e", "FLOAT64", max(lons) + lon_pad),
        bigquery.ScalarQueryParameter("shape", "STRING", _wkt(points)),
        bigquery.ScalarQueryParameter("meters", "FLOAT64", meters),
        bigquery.ScalarQueryParameter("tz", "STRING", tz),
    ]
    job = _bq().query(SQL, job_config=bigquery.QueryJobConfig(
        query_parameters=params, maximum_bytes_billed=MAX_BYTES,
        use_query_cache=True))
    return [dict(r) for r in job.result(timeout=QUERY_TIMEOUT_SECONDS)]


def summarize(rows: list[dict], days: int) -> dict:
    """Patterns from per-event rows (kind, title, dow 1-7, hr 0-23,
    minutes). Pure, so tests feed it rows directly."""
    weeks = max(days / 7.0, 1.0)
    inc = [r for r in rows if r.get("kind") == "incident"]
    clo = [r for r in rows if r.get("kind") == "closure"]
    by_hour = [{"hour": h, "incidents": 0, "closures": 0} for h in range(24)]
    weekday_hours = [0] * 24
    weekend_hours = [0] * 24
    by_dow = Counter()
    for r in inc:
        hr, dow = int(r["hr"]), int(r["dow"])
        by_hour[hr]["incidents"] += 1
        by_dow[dow] += 1
        (weekend_hours if dow in (1, 7) else weekday_hours)[hr] += 1
    for r in clo:
        by_hour[int(r["hr"])]["closures"] += 1
    durations = [r["minutes"] for r in inc
                 if isinstance(r.get("minutes"), int) and 0 < r["minutes"] < 24 * 60]
    ranked = sorted(range(24), key=lambda h: -by_hour[h]["incidents"])
    daytime = [h for h in range(6, 22)]
    quiet = sorted(daytime, key=lambda h: by_hour[h]["incidents"])
    return {
        "available": True,
        "window_days": days,
        "incidents": len(inc),
        "closures_started": len(clo),
        "incidents_per_week": round(len(inc) / weeks, 1),
        "busiest_hours": [h for h in ranked[:3] if by_hour[h]["incidents"]],
        "quietest_daytime_hours": quiet[:3],
        "by_hour": by_hour,
        # Incidents per hour on an average weekday and weekend day.
        "weekday_rate_by_hour": [round(n / (weeks * 5), 2) for n in weekday_hours],
        "weekend_rate_by_hour": [round(n / (weeks * 2), 2) for n in weekend_hours],
        "by_weekday": [{"day": WEEKDAYS[d - 1], "incidents": by_dow.get(d, 0)}
                       for d in range(1, 8)],
        "common_incident_types": [
            {"type": t, "count": n}
            for t, n in Counter(r.get("title") or "Other" for r in inc).most_common(5)
        ],
        "median_incident_minutes": (round(statistics.median(durations))
                                    if durations else None),
    }


def unavailable(reason: str) -> dict:
    return {"available": False, "reason": reason}


async def history(points: list, meters: float, days: int, tz: str) -> dict:
    """Patterns within ``meters`` of a point or a route polyline over
    the last ``days`` (local hours in ``tz``)."""
    global _warned
    days = max(7, min(int(days), 365))
    now = datetime.now(UTC)
    days = min(days, max(7, (now - ARCHIVE_START).days))
    pts = _thin(points)
    key = (tuple((round(a, 3), round(b, 3)) for a, b in pts),
           round(meters), days, tz)
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < TTL_SECONDS:
        return hit[1]
    if not UPSTREAM.allow("bq-history", HISTORY_DAILY):
        return unavailable("history queries are spent for today")
    try:
        rows = await asyncio.wait_for(
            asyncio.to_thread(_run, pts, meters, days, tz),
            QUERY_TIMEOUT_SECONDS + 5)
    except Exception as exc:  # noqa: BLE001 - history enriches, never breaks
        if not _warned:
            _warned = True
            log.warning("history: query failed (%s)", type(exc).__name__)
        return unavailable("the event history is not reachable right now")
    out = summarize(rows, days)
    out["since"] = (now - timedelta(days=days)).date().isoformat()
    if len(_cache) >= _CACHE_MAX:
        _cache.pop(next(iter(_cache)))
    _cache[key] = (time.monotonic(), out)
    return out
