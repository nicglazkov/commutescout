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
import logging
import os
import re
import sys
from datetime import UTC, datetime

_SALT = os.environ.get("TELEMETRY_SALT", "")
if not _SALT:
    _SALT = "ca-roads-dev"
    if os.environ.get("PORT"):
        # Deployed without a real salt: visitor hashes become brute-forceable
        # back to IPv4 addresses. Shout about it in the logs.
        print(
            json.dumps({
                "severity": "WARNING",
                "message": "TELEMETRY_SALT is not set; visitor hashes are "
                           "built from a public default. Set a random "
                           "32+ char TELEMETRY_SALT on this service.",
            }),
            flush=True,
        )


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


class RedactCoordsFilter(logging.Filter):
    """Round coordinates in uvicorn's access lines.

    The access log writes each request line with its query string, and
    /api/speedlimit, /api/suggest and /api/mapdata carry the user's
    position there. The privacy page promises about a kilometer at most.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # uvicorn.access args: (client, method, path, http_version, status)
        if isinstance(record.args, tuple) and len(record.args) >= 3:
            args = list(record.args)
            args[2] = redact_coords(str(args[2]))
            record.args = tuple(args)
        return True


def uvicorn_log_config() -> dict:
    """uvicorn's own logging setup with the access lines redacted."""
    import copy

    from uvicorn.config import LOGGING_CONFIG

    config = copy.deepcopy(LOGGING_CONFIG)
    config.setdefault("filters", {})["redact_coords"] = {"()": RedactCoordsFilter}
    config["handlers"]["access"]["filters"] = ["redact_coords"]
    return config
