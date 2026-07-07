"""Structured event logging for usage analysis.

One JSON line per event to stdout; Cloud Run turns JSON lines into queryable
jsonPayload entries in Cloud Logging, so there is no analytics infrastructure
to run. scripts/usage_report.py aggregates them.

Privacy: client IPs are never written to these events. Visitors are counted
by a salted hash that rotates daily, so daily uniques are computable and
nothing links across days. Question text is logged (disclosed in the demo
footer) because it is the raw material for improving answers.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import UTC, datetime

_SALT = os.environ.get("TELEMETRY_SALT", "ca-roads")


def visitor_hash(ip: str) -> str:
    """Pseudonymous daily visitor id: same IP hashes alike within a UTC day,
    differently across days."""
    day = datetime.now(UTC).date().isoformat()
    return hashlib.sha256(f"{_SALT}:{day}:{ip}".encode()).hexdigest()[:12]


def log_event(event: str, **fields) -> None:
    payload = {"log_type": "ca_roads_event", "event": event, **fields}
    print(json.dumps(payload, default=str), file=sys.stdout, flush=True)


_PRECISE_COORD_RE = re.compile(r"(-?\d{1,3}\.\d{3,})")


def redact_coords(value):
    """Round any coordinate-looking number to 2 decimals (~1 km).

    Tool arguments can embed the user's shared location (trip origins,
    center points). The disclosed telemetry contract is a location_shared
    boolean, so anything more precise than neighborhood level is rounded
    before logging. Works recursively over dicts, lists, strings, floats.
    """
    if isinstance(value, dict):
        return {k: redact_coords(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_coords(v) for v in value]
    if isinstance(value, float) and abs(value) <= 180 and value != round(value, 2):
        return round(value, 2)
    if isinstance(value, str):
        return _PRECISE_COORD_RE.sub(
            lambda m: f"{float(m.group(1)):.2f}", value
        )
    return value
