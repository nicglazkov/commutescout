"""The map's published snapshots, read back by the MCP tools.

The demo service builds every live marker in the country on a timer and
publishes three objects behind Cloudflare (ca_roads_demo/snapshot.py):
live events every 30 s, signs and road weather every 5 min, cameras
hourly. They are built by the exact code /api/mapdata uses, from every
state feed whose key the demo holds.

Reading them here means the MCP server answers from the same picture
the map shows, at the cost of one edge-cached download, instead of
fetching dozens of state feeds into a small instance that scales to
zero. Each object is revalidated by ETag, so a warm answer usually
costs a 304. A snapshot that cannot be fetched, or has gone stale,
answers None and the caller builds the markers itself.

``MCP_SNAPSHOT_BASE`` overrides the host; an empty value turns this
off (the tests run that way).
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import UTC, datetime

import httpx

DEFAULT_BASE = "https://data.commutescout.com"
BUNDLES = {
    "live.json.gz": ({"incident", "closure", "chain", "fire", "toll",
                      "enforcement"}, 20.0),
    "signs.json.gz": ({"sign", "rwis"}, 120.0),
    "cameras.json.gz": ({"camera"}, 1800.0),
}
# Past this, a bundle is not "a little old" but a stalled publisher;
# the caller builds its own rather than serve it.
MAX_AGE_S = {"live.json.gz": 15 * 60, "signs.json.gz": 45 * 60,
             "cameras.json.gz": 8 * 3600}
TIMEOUT_SECONDS = 15.0
# Marker kind -> the tool-facing group a caller asks for.
GROUP = {"incident": "incident", "lane_closure": "closure",
         "chain_control": "chain", "wildfire": "fire", "toll": "toll",
         "sign": "sign", "rwis": "rwis", "camera": "camera"}
# The only plugin source a snapshot may contribute: public OpenStreetMap
# enforcement cameras from the first-party osm-cameras plugin. Plugin
# data in general is per-user and never leaves the person it belongs to;
# this one is published to everyone on the map already.
PUBLIC_PLUGIN = "osm-cameras"

_state: dict[str, dict] = {}
_locks: dict[str, asyncio.Lock] = {}


def base() -> str:
    return os.environ.get("MCP_SNAPSHOT_BASE", DEFAULT_BASE).rstrip("/")


def group_of(m: dict) -> str | None:
    kind = m.get("kind")
    if kind == "plugin":
        return "enforcement" if m.get("source_id") == PUBLIC_PLUGIN else None
    return GROUP.get(kind)


async def _bundle(client: httpx.AsyncClient, name: str) -> dict | None:
    """One snapshot object, cached and revalidated, or None."""
    root = base()
    if not root:
        return None
    _kinds, ttl = BUNDLES[name]
    st = _state.get(name)
    now = time.monotonic()
    if st and now - st["checked"] < ttl:
        return st["payload"]
    lock = _locks.setdefault(name, asyncio.Lock())
    async with lock:
        st = _state.get(name)
        if st and time.monotonic() - st["checked"] < ttl:
            return st["payload"]
        headers = {"User-Agent": "commutescout-mcp (snapshot reader)"}
        if st and st.get("etag"):
            headers["If-None-Match"] = st["etag"]
        try:
            resp = await client.get(f"{root}/{name}", headers=headers,
                                    timeout=TIMEOUT_SECONDS)
            if resp.status_code == 304 and st:
                st["checked"] = time.monotonic()
                return st["payload"]
            resp.raise_for_status()
            payload = resp.json()
        except Exception:  # noqa: BLE001 - the caller falls back to feeds
            return st["payload"] if st and _fresh(name, st["payload"]) else None
        if not isinstance(payload, dict) or not isinstance(
                payload.get("markers"), list):
            return None
        _state[name] = {"checked": time.monotonic(), "payload": payload,
                        "etag": resp.headers.get("etag")}
        return payload


def _fresh(name: str, payload: dict | None) -> bool:
    if not payload:
        return False
    try:
        published = datetime.fromisoformat(payload["published"])
    except (KeyError, TypeError, ValueError):
        return False
    return (datetime.now(UTC) - published).total_seconds() <= MAX_AGE_S[name]


async def markers(client: httpx.AsyncClient, box, kinds: set[str]
                  ) -> tuple[list[dict], str] | None:
    """Markers inside ``box`` (lat_min, lon_min, lat_max, lon_max) for
    the requested groups, with the oldest ``published`` time among the
    bundles used; None if any needed bundle is unavailable or stale."""
    names = [n for n, (k, _) in BUNDLES.items() if k & kinds]
    if not names:
        return [], datetime.now(UTC).isoformat(timespec="seconds")
    payloads = await asyncio.gather(*(_bundle(client, n) for n in names))
    if any(not _fresh(n, p) for n, p in zip(names, payloads, strict=True)):
        return None
    lat0, lon0, lat1, lon1 = box
    out = []
    for p in payloads:
        for m in p["markers"]:
            lat, lon = m.get("lat"), m.get("lon")
            if not isinstance(lat, int | float) or not isinstance(lon, int | float):
                continue
            if not (lat0 <= lat <= lat1 and lon0 <= lon <= lon1):
                continue
            if group_of(m) in kinds:
                out.append(m)
    oldest = min(p["published"] for p in payloads)
    return out, oldest
