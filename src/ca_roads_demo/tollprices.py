"""Toll price history: append-only BigQuery rows, written on change.

Express-lane rates move minute to minute and vanish without a trace;
like the event archive, history cannot be backfilled, so recording
starts long before the features that read it (typical-price coloring,
price-by-time-of-day charts). Every checker cycle peeks the already
cached toll markers (never fetches) and appends one row per
(corridor, entry, destination) whose price changed since the last row,
plus everything on the first cycle after boot. Readers treat a price
as valid until the next row for the same key.

Table: events.toll_prices, day-partitioned on seen_at, clustered by
corridor. Restarts re-emit the current board once (same dedupe
tolerance as the event archive)."""

from __future__ import annotations

import asyncio
import contextlib
import os
import re
from datetime import UTC, datetime

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "ca-roads-mcp")
DATASET = os.environ.get("ARCHIVE_DATASET", "events")
TABLE = os.environ.get("TOLL_TABLE", "toll_prices")
ENABLED = os.environ.get("ARCHIVE_ENABLED", "1").lower() not in ("0", "false")

# (src, corridor, entry, dest) -> last recorded price
_last: dict[tuple, float] = {}
_client = None

_DIRS = {"NB", "SB", "EB", "WB", "INSIDE", "OUTSIDE",
         "NORTH", "SOUTH", "EAST", "WEST"}
_SEQ_RE = re.compile(r" - \d+$")
_PLAZA_CODE_RE = re.compile(r"\s*\([A-Z0-9]+\)$")
_LINE_RE = re.compile(r"to (.+?): \$([\d.]+)$")
_ENTRY_RE = re.compile(r".*? - (.+?) - (\d+)$")


def corridor_key(m: dict) -> str:
    """Corridor+direction a toll marker belongs to ("I-880 NB",
    "Sam Houston", "PGBT OUTSIDE"). The same parse drives the map's
    corridor grouping, so history and display share one vocabulary."""
    name = m.get("name") or ""
    prefix = name.split(":", 1)[0].strip()
    if m.get("src") == "NTTA":
        toks = prefix.split()
        key = toks[0] if toks else prefix
        if len(toks) > 1 and toks[1] in _DIRS:
            key += " " + toks[1]
        return key
    return prefix


def entry_label(m: dict) -> str:
    """Human entry-point label: sign sequence numbers and plaza codes
    stripped."""
    name = m.get("name") or ""
    rest = name.split(":", 1)[1].strip() if ":" in name else name
    if m.get("src") == "511.org":
        got = _ENTRY_RE.match(rest)
        if got:
            return got.group(1)
    return _SEQ_RE.sub("", _PLAZA_CODE_RE.sub("", rest))


def entry_seq(m: dict) -> int | None:
    """Sign sequence number when the source embeds one (511.org names
    end in " - N"); orders gantries along the corridor."""
    name = m.get("name") or ""
    rest = name.split(":", 1)[1].strip() if ":" in name else name
    got = _ENTRY_RE.match(rest)
    return int(got.group(2)) if got else None


def price_rows(m: dict) -> list[tuple[str, float]]:
    """(destination, price) pairs for one marker. Explicit rate tables
    (bridge payment tiers) win; then per-destination sign lines; then
    the single posted price with an empty dest."""
    if m.get("rates"):
        return [(str(lbl), float(p)) for lbl, p in m["rates"]]
    rows = []
    for ln in m.get("lines") or []:
        got = _LINE_RE.match(ln)
        if got:
            rows.append((_SEQ_RE.sub("", got.group(1)), float(got.group(2))))
    if not rows and m.get("price") is not None:
        rows.append(("", float(m["price"])))
    return rows


def _bq():
    global _client
    if _client is None:
        from google.cloud import bigquery

        _client = bigquery.Client(project=PROJECT)
    return _client


def observe_sync(markers: list[dict]) -> dict:
    now_iso = datetime.now(UTC).isoformat()
    out = []

    def note(src, corridor, entry, dest, price, pricing):
        key = (src or "", corridor, entry, dest)
        if _last.get(key) == price:
            return
        _last[key] = price
        out.append({
            "seen_at": now_iso, "src": key[0], "corridor": corridor,
            "entry": entry, "dest": dest, "price": price,
            "pricing": pricing or "",
        })

    for m in markers:
        if m.get("kind") != "toll":
            continue
        if m.get("entries") is not None:
            # Corridor marker (states.toll_corridors output): entries
            # already carry parsed labels and destination rows.
            for e in m["entries"]:
                for dest, price in e.get("rows") or []:
                    note(m.get("src"), m.get("corridor") or "",
                         e.get("label") or "", dest or "", price,
                         m.get("pricing"))
            continue
        corridor = corridor_key(m)
        entry = entry_label(m)
        for dest, price in price_rows(m):
            note(m.get("src"), corridor, entry, dest, price,
                 m.get("pricing"))
    if not out:
        return {"archived": 0}
    errors = _bq().insert_rows_json(f"{PROJECT}.{DATASET}.{TABLE}", out)
    return {"archived": len(out) - len(errors), "failed": len(errors)}


def cached_toll_markers() -> list[dict]:
    """Every toll marker currently in the states feed cache. Read-only
    peek: the logger must never trigger upstream fetches."""
    from ca_roads_demo import states

    out = []
    for key, entry in list(states._cache._entries.items()):  # noqa: SLF001
        if not (isinstance(key, str) and key.startswith("toll:")):
            continue
        with contextlib.suppress(Exception):
            out.extend(entry.value["markers"])
    return out


async def observe() -> dict:
    """Snapshot cached toll prices into BigQuery; never raises."""
    if not ENABLED:
        return {"archived": 0, "disabled": True}
    try:
        markers = cached_toll_markers()
        return await asyncio.to_thread(observe_sync, markers)
    except Exception:  # noqa: BLE001 - history must never break alerts
        with contextlib.suppress(Exception):
            global _client
            _client = None
        return {"archived": 0, "failed": 1}
