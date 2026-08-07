"""Event lifecycle archive: the raw material for every future
historical feature (route history counts, day playback, trend
heatmaps, dispatch-log analytics).

History cannot be backfilled - CHP incidents vanish from the feed when
they clear - so recording starts long before the features that read it
exist. The watch checker already collects every event statewide every
five minutes; this module diffs consecutive cycles and appends
append-only lifecycle rows to BigQuery:

- phase "appear": first time an event id shows up, with the full
  structured payload (dispatch timeline, closure fields, fire size)
- phase "update": an already-seen event changed - new dispatch-log
  entries, a problem-type change, fire growth. The payload carries only
  what is new since the last row, so rows stay small and the full
  history is the concatenation of appear + updates.
- phase "clear":  the cycle it stops showing up (first_seen carried
  along so durations are one subtraction away)

Instance restarts lose the in-process seen-set, which produces a
duplicate "appear" after each restart; readers dedupe with
MIN(first_seen) GROUP BY event_id. Archive failures never break the
alert cycle."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from datetime import UTC, datetime

log = logging.getLogger(__name__)

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "ca-roads-mcp")
DATASET = os.environ.get("ARCHIVE_DATASET", "events")
TABLE = os.environ.get("ARCHIVE_TABLE", "event_log")
ENABLED = os.environ.get("ARCHIVE_ENABLED", "1").lower() not in ("0", "false")

# event_id -> {"first": iso, "kind": str, "nd": n details seen,
#              "nu": n units seen, "sig": scalar-state signature}
_seen: dict[str, dict] = {}
_started = False
_client = None

# Rows a previous cycle built but could not write. The diff that
# produced them is not reproducible: _seen is advanced while the rows
# are built, so by the next cycle the events look unchanged and would
# never generate a row again. Dropping a failed batch is therefore
# permanent data loss in an archive that cannot be backfilled, so
# failures are carried forward and retried on the next cycle instead.
_pending: list[dict] = []
# Roughly two hours of a busy cycle. Past this the backlog is a symptom
# of a sustained outage, not a blip; the oldest rows go and say so.
PENDING_MAX = 20_000


def _retain(rows: list[dict]) -> None:
    """Hold rows for the next cycle's insert, oldest dropped past the cap."""
    if not rows:
        return
    _pending.extend(rows)
    if len(_pending) > PENDING_MAX:
        dropped = len(_pending) - PENDING_MAX
        del _pending[:dropped]
        log.error("archive: dropped %d buffered rows, backlog over %d",
                  dropped, PENDING_MAX)
    log.warning("archive: %d rows buffered for retry", len(_pending))


def _bq():
    global _client
    if _client is None:
        from google.cloud import bigquery

        _client = bigquery.Client(project=PROJECT)
    return _client


def _scalar_sig(e: dict) -> str:
    """Signature of everything except the append-only timeline lists:
    the title (problem-type changes) plus scalar payload fields (fire
    acres, closure lanes). A change means an 'update' row."""
    payload = e.get("payload") or {}
    scalars = {k: v for k, v in payload.items() if k not in ("details", "units")}
    return json.dumps([e.get("title") or "", scalars], sort_keys=True)


def _payload_json(e: dict, nd_from: int = 0, nu_from: int = 0) -> str | None:
    """Payload for a row: timeline entries from the given offsets (all of
    them for appear rows, only the new tail for update rows) plus the
    current scalar state."""
    payload = e.get("payload") or {}
    out: dict = {}
    details = payload.get("details") or []
    units = payload.get("units") or []
    if details[nd_from:]:
        out["details"] = details[nd_from:]
    if units[nu_from:]:
        out["units"] = units[nu_from:]
    scalars = {k: v for k, v in payload.items()
               if k not in ("details", "units") and v not in (None, "")}
    if scalars:
        out["state"] = scalars
    if not out:
        return None
    return json.dumps(out, ensure_ascii=False)[:200_000]


def _row(e: dict, phase: str, now_iso: str, first_seen: str,
         payload_json: str | None) -> dict:
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
        "payload": payload_json,
    }


def _counts(e: dict) -> tuple[int, int]:
    payload = e.get("payload") or {}
    return (len(payload.get("details") or []), len(payload.get("units") or []))


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
        nd, nu = _counts(e)
        sig = _scalar_sig(e)
        state = _seen.get(eid)
        if state is None:
            _seen[eid] = {"first": now_iso, "kind": e.get("kind", ""),
                          "nd": nd, "nu": nu, "sig": sig}
            rows.append(_row(e, "appear", now_iso, now_iso,
                             _payload_json(e)))
        elif nd > state["nd"] or nu > state["nu"] or sig != state["sig"]:
            rows.append(_row(e, "update", now_iso, state["first"],
                             _payload_json(e, state["nd"], state["nu"])))
            state.update(nd=nd, nu=nu, sig=sig)
    for eid in list(_seen):
        if eid not in current:
            # Reuse the kind recorded at appear time: the id prefix is a
            # different vocabulary (chp:/lcs: vs incident/closure), and
            # deriving kind from it split one event across two kinds.
            state = _seen.pop(eid)
            rows.append({
                "event_id": eid, "kind": state["kind"],
                "phase": "clear", "lat": None, "lon": None,
                "title": None, "detail": None,
                "first_seen": state["first"], "seen_at": now_iso,
                "payload": None,
            })
    _started = True
    # Anything a previous cycle failed to write goes first, so the
    # archive stays in event order across a transient outage.
    batch = _pending + rows
    _pending.clear()
    if not batch:
        return {"archived": 0}
    try:
        errors = _bq().insert_rows_json(f"{PROJECT}.{DATASET}.{TABLE}", batch)
    except Exception:
        # The whole insert failed. Keep every row: observe() logs and
        # resets the client, and the next cycle tries again.
        _retain(batch)
        raise
    if errors:
        # Partial failure: BigQuery reports the offending rows by index.
        bad = {e["index"] for e in errors if isinstance(e, dict)
               and "index" in e}
        _retain([r for i, r in enumerate(batch) if i in bad])
        log.warning("archive: %d of %d rows rejected by BigQuery",
                    len(errors), len(batch))
    return {"archived": len(batch) - len(errors), "failed": len(errors),
            "pending": len(_pending)}


async def observe(events: list[dict]) -> dict:
    """Async wrapper; never raises into the caller's alert cycle."""
    if not ENABLED:
        return {"archived": 0, "disabled": True}
    try:
        return await asyncio.to_thread(observe_sync, events)
    except Exception:  # noqa: BLE001 - archive must never break alerts
        # Logged, not swallowed silently: a stalled archive is invisible
        # in every other signal, and the rows are already buffered.
        log.exception("archive: insert failed, %d rows buffered", len(_pending))
        with contextlib.suppress(Exception):
            global _client
            _client = None  # a poisoned client gets rebuilt next cycle
        return {"archived": 0, "failed": len(events),
                "pending": len(_pending)}
