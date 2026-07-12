"""Event lifecycle archive: the raw material for every future
historical feature (route history counts, day playback, trend
heatmaps).

History cannot be backfilled - CHP incidents vanish from the feed when
they clear - so recording starts long before the features that read it
exist. The watch checker already collects every event statewide every
five minutes; this module diffs consecutive cycles and appends
append-only lifecycle rows to BigQuery:

- phase "appear": first time an event id shows up
- phase "clear":  the cycle it stops showing up (first_seen carried
  along so durations are one subtraction away)

Instance restarts lose the in-process seen-set, which produces a
duplicate "appear" after each restart; readers dedupe with
MIN(first_seen) GROUP BY event_id. Archive failures never break the
alert cycle."""

from __future__ import annotations

import asyncio
import contextlib
import os
from datetime import UTC, datetime

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "ca-roads-mcp")
DATASET = os.environ.get("ARCHIVE_DATASET", "events")
TABLE = os.environ.get("ARCHIVE_TABLE", "event_log")
ENABLED = os.environ.get("ARCHIVE_ENABLED", "1").lower() not in ("0", "false")

_seen: dict[str, str] = {}  # event_id -> first_seen isoformat
_started = False
_client = None


def _bq():
    global _client
    if _client is None:
        from google.cloud import bigquery

        _client = bigquery.Client(project=PROJECT)
    return _client


def _row(e: dict, phase: str, now_iso: str, first_seen: str) -> dict:
    detail = e.get("body") or ""
    if e.get("meta"):
        detail = f"{detail} | {e['meta']}" if detail else e["meta"]
    return {
        "event_id": e["id"],
        "kind": e.get("kind", ""),
        "phase": phase,
        "lat": e.get("lat"),
        "lon": e.get("lon"),
        "title": (e.get("title") or "")[:300],
        "detail": detail[:600],
        "first_seen": first_seen,
        "seen_at": now_iso,
    }


def observe_sync(events: list[dict]) -> dict:
    """Diff this cycle against the last one and append lifecycle rows.

    The first cycle after boot seeds the seen-set without writing
    'appear' rows for the whole backlog EXCEPT on a truly fresh table -
    the very first boot ever should capture the starting state. That
    distinction is impossible to know in-process, so we always write
    the backlog on the first cycle and let readers dedupe: a restart
    costs ~1,500 duplicate 'appear' rows a day at worst, which
    MIN(first_seen) GROUP BY event_id makes invisible."""
    global _started
    now_iso = datetime.now(UTC).isoformat()
    current = {e["id"]: e for e in events if e.get("id")}
    rows = []
    for eid, e in current.items():
        if eid not in _seen:
            _seen[eid] = now_iso
            rows.append(_row(e, "appear", now_iso, now_iso))
    for eid in list(_seen):
        if eid not in current:
            first = _seen.pop(eid)
            rows.append({
                "event_id": eid, "kind": eid.split(":", 1)[0],
                "phase": "clear", "lat": None, "lon": None,
                "title": None, "detail": None,
                "first_seen": first, "seen_at": now_iso,
            })
    _started = True
    if not rows:
        return {"archived": 0}
    errors = _bq().insert_rows_json(f"{PROJECT}.{DATASET}.{TABLE}", rows)
    return {"archived": len(rows) - len(errors), "failed": len(errors)}


async def observe(events: list[dict]) -> dict:
    """Async wrapper; never raises into the caller's alert cycle."""
    if not ENABLED:
        return {"archived": 0, "disabled": True}
    try:
        return await asyncio.to_thread(observe_sync, events)
    except Exception:  # noqa: BLE001 - archive must never break alerts
        with contextlib.suppress(Exception):
            global _client
            _client = None  # a poisoned client gets rebuilt next cycle
        return {"archived": 0, "failed": len(events)}
