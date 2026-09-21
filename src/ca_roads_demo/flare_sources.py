"""Flare sources: the registry of plugins and the mediated read path.

A source is a Flare manifest (docs/flare.md) an admin added. The poller
reads each enabled source's handshake, then its alerts one grid cell at
a time across the plugin's coverage box, validates every record with
the same rules the conformance check applies, caps them, and keeps the
result in memory. The map and the snapshots read ``markers_for_bbox``
like any other feed; a plugin's alerts ride along as ``kind: "plugin"``
markers. No user position or identity ever reaches a plugin: the
poller asks for cell centers under CommuteScout's own identity.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import math
import os
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from starlette.requests import Request
from starlette.responses import JSONResponse

from ca_roads import flare
from ca_roads.budget import DailyCounter

log = logging.getLogger("ca_roads_demo.flare")

COLLECTION = "flare_sources"
CELL_DEG = 1.0
CELL_RADIUS_M = 80_000       # covers a one-degree cell's half diagonal
MAX_CELLS = 200
# Demand-driven polling: cells people looked at in the last VIEW_TTL_S are
# asked for every cycle; the rest of a plugin's coverage is swept a few
# cells at a time, and a cell's alerts are kept for CELL_KEEP_S.
VIEW_TTL_S = 600
SWEEP_PER_POLL = 12
CELL_KEEP_S = 900
POLL_FLOOR_S = 60
HANDSHAKE_TTL_S = 3600
STATUS_WRITE_EVERY_S = 600
# A source that keeps failing is backed off instead of being asked every
# cycle forever, and one slow source cannot hold up the whole sweep.
FAILS_BEFORE_BACKOFF = 3
MAX_BACKOFF_S = 3600
CYCLE_DEADLINE_S = 120
# A plugin is usually a small service that scales to zero, and a cold
# container can take a minute to answer its first request. Giving up
# before that deadlocks the pair: the plugin only stays warm because we
# poll it, and we only poll it if it answers. The first contact of a
# cycle gets a long timeout and one retry; by the time alerts are
# fetched the instance is up and the usual timeout applies.
COLD_START_TIMEOUT_S = 75.0
# Cells that have produced alerts before are asked again ahead of the
# blind sweep. A plugin's coverage is a rectangle, and a rectangle over
# the United States is mostly ocean and empty country, so a purely
# rotating sweep spends most of its turns on water.
PRODUCTIVE_PER_POLL = 6
PRODUCTIVE_KEEP_S = 21_600
# The catalog shows a plugin's last good count for this long after its
# cells expire or a poll fails, so a quiet map or one bad poll does not
# flash "0 alerts" on the marketplace.
COUNT_HOLD_S = 3600
STALE_AFTER_S = 900
CONCURRENCY = 4
USER_AGENT = "commutescout.com flare poller (https://commutescout.com/developers)"


class MemorySourceStore:
    """In-memory registry; the Firestore one matches this surface."""

    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}

    async def list(self) -> list[dict]:
        return [{"id": k, **v} for k, v in self.docs.items()]

    async def get(self, sid: str) -> dict | None:
        return dict(self.docs[sid]) if sid in self.docs else None

    async def put(self, sid: str, data: dict) -> None:
        self.docs.setdefault(sid, {}).update(data)

    async def delete(self, sid: str) -> None:
        self.docs.pop(sid, None)


class FirestoreSourceStore:
    def __init__(self, project: str | None = None, collection: str = COLLECTION) -> None:
        from google.cloud import firestore

        self.db = firestore.AsyncClient(
            project=project or os.environ.get("GOOGLE_CLOUD_PROJECT") or "ca-roads-mcp")
        self.collection = collection

    def _col(self):
        return self.db.collection(self.collection)

    async def list(self) -> list[dict]:
        out = []
        async for snap in self._col().stream():
            d = snap.to_dict()
            d["id"] = snap.id
            out.append(d)
        return out

    async def get(self, sid: str) -> dict | None:
        snap = await self._col().document(sid).get()
        return snap.to_dict() if snap.exists else None

    async def put(self, sid: str, data: dict) -> None:
        await self._col().document(sid).set(data, merge=True)

    async def delete(self, sid: str) -> None:
        await self._col().document(sid).delete()


_store = None


def get_source_store():
    global _store
    if _store is None:
        _store = FirestoreSourceStore()
    return _store


def set_source_store(store) -> None:
    global _store
    _store = store


def lattice(bbox: list) -> list[tuple[float, float]]:
    """Centers of every one-degree cell, on the whole-degree grid, that
    touches ``[s, w, n, e]``: the same cells whatever box asks for them."""
    s, w, n, e = bbox
    la0, la1 = math.floor(s / CELL_DEG), math.ceil(n / CELL_DEG)
    lo0, lo1 = math.floor(w / CELL_DEG), math.ceil(e / CELL_DEG)
    lats = [(la0 + i) * CELL_DEG + CELL_DEG / 2 for i in range(max(1, la1 - la0))]
    lons = [(lo0 + j) * CELL_DEG + CELL_DEG / 2 for j in range(max(1, lo1 - lo0))]
    return [(round(la, 3), round(lo, 3)) for la in lats for lo in lons]


def cell_of(lat: float, lon: float) -> tuple[float, float]:
    """The one-degree cell center that contains a point."""
    return (round(math.floor(lat / CELL_DEG) * CELL_DEG + CELL_DEG / 2, 3),
            round(math.floor(lon / CELL_DEG) * CELL_DEG + CELL_DEG / 2, 3))


def cells_for(bbox: list) -> list[tuple[float, float]]:
    """Centers of the one-degree cells that tile ``[s, w, n, e]``,
    capped at MAX_CELLS (a nationwide plugin gets its middle first)."""
    s, w, n, e = bbox
    cells = lattice(bbox)
    if len(cells) > MAX_CELLS:
        cy, cx = (s + n) / 2, (w + e) / 2
        cells.sort(key=lambda c: (c[0] - cy) ** 2 + (c[1] - cx) ** 2)
        cells = cells[:MAX_CELLS]
    return cells


def _https_only(url) -> str | None:
    """A link is shown only when it is an https URL; anything else (a
    javascript: scheme, a bare path) is dropped before it reaches a page."""
    return url if isinstance(url, str) and url.startswith("https://") else None


def alert_marker(src: dict, a: dict) -> dict:
    """The map marker for one accepted alert."""
    attribution = src.get("attribution") or {}
    m = {
        "kind": "plugin",
        "id": f"{src['id']}:{a['id']}",
        "unlisted": src.get("visibility") == "unlisted",
        "lat": a["lat"], "lon": a["lon"],
        "flare_kind": a["kind"],
        "label": a.get("description") or None,
        "road": (a.get("road_names") or [None])[0],
        "heading": a.get("heading_deg"),
        "reported": a.get("report_ts"),
        "confirmed": a.get("confirm_ts"),
        "confirmations": a.get("n_confirmations") or 0,
        "reliability": a.get("reliability", 0.5),
        "notify": bool(a.get("notify")),
        "ttl_s": a["ttl_s"],
        "source": src.get("name") or src["id"],
        "source_id": src["id"],
        "source_url": _https_only(a.get("source_url")) or _https_only(attribution.get("url")),
        "trust": src.get("trust") or "community",
        "tier": flare.tier_of(src),
    }
    geom = a.get("geometry")
    if isinstance(geom, dict) and geom.get("type") == "LineString":
        m["path"] = [[c[1], c[0]] for c in geom["coordinates"]]
    return {k: v for k, v in m.items() if v is not None}


class Poller:
    """Keeps every enabled source's alerts fresh in memory."""

    def __init__(self, store=None, *, now=None) -> None:
        self._store = store
        self._now = now or (lambda: datetime.now(UTC))
        self.sources: dict[str, dict] = {}
        self.alerts: dict[str, list[dict]] = {}
        self.handshakes: dict[str, tuple[float, dict]] = {}
        self.status: dict[str, dict] = {}
        self._last_poll: dict[str, float] = {}
        self.viewed: dict[tuple[float, float], float] = {}
        self.cells: dict[str, dict[tuple[float, float], tuple[float, list]]] = {}
        self._sweep_pos: dict[str, int] = {}
        self._last_status_write: dict[str, float] = {}
        self._fails: dict[str, int] = {}
        self.productive: dict[str, dict[tuple[float, float], float]] = {}
        self._sources_loaded = 0.0

    @property
    def store(self):
        if self._store is None:
            self._store = get_source_store()
        return self._store

    async def refresh_sources(self) -> None:
        docs = await self.store.list()
        # A private source belongs to one person's own device and is
        # polled there; the mediated poller never fetches it and it never
        # reaches the shared map.
        self.sources = {d["id"]: d for d in docs if d.get("enabled", True)
                        and d.get("visibility") != "private"
                        and not flare.validate_manifest(d)}
        for sid in list(self.alerts):
            if sid not in self.sources:
                self.alerts.pop(sid, None)
                self.status.pop(sid, None)
        self._sources_loaded = time.monotonic()

    def _headers(self, src: dict) -> dict:
        h = {"Accept": "application/json", "User-Agent": USER_AGENT}
        if src.get("token"):
            h["Authorization"] = f"Bearer {src['token']}"
        return h

    async def fetch_json(self, client, url: str, *, src: dict, params: dict | None = None,
                         timeout: float = 15.0) -> tuple[int, Any]:
        """One capped GET to a plugin.

        Redirects are refused: a base that passed the address guard at
        registration could otherwise send the poller anywhere on a later
        poll. The body is read in chunks and abandoned past MAX_BYTES, so
        a hostile source cannot exhaust the instance's memory.
        """
        if not flare.fetchable_base(url):
            raise ValueError("base is not fetchable")
        async with client.stream("GET", url, params=params, headers=self._headers(src),
                                 timeout=timeout, follow_redirects=False) as r:
            if r.status_code >= 300:
                await r.aclose()
                return r.status_code, None
            body = bytearray()
            async for chunk in r.aiter_bytes():
                body.extend(chunk)
                if len(body) > flare.MAX_BYTES:
                    raise ValueError(f"body over {flare.MAX_BYTES} bytes")
        try:
            return r.status_code, json.loads(bytes(body))
        except ValueError as exc:
            raise ValueError(f"body is not JSON: {exc}") from exc

    async def handshake(self, src: dict, client) -> dict:
        sid = src["id"]
        hit = self.handshakes.get(sid)
        if hit and time.monotonic() - hit[0] < HANDSHAKE_TTL_S:
            return hit[1]
        url = f"{src['base'].rstrip('/')}/flare/v1/handshake"
        try:
            status, hs = await self.fetch_json(client, url, src=src,
                                               timeout=COLD_START_TIMEOUT_S)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
            # One retry: a container that was starting on the first
            # attempt is usually serving by the second.
            status, hs = await self.fetch_json(client, url, src=src,
                                               timeout=COLD_START_TIMEOUT_S)
        if status != 200:
            raise ValueError(f"handshake: HTTP {status}")
        errs = flare.validate_handshake(hs)
        if errs:
            raise ValueError("handshake: " + "; ".join(errs))
        self.handshakes[sid] = (time.monotonic(), hs)
        return hs

    def note_view(self, box) -> None:
        """A map request looked at ``box``: its cells are hot for a while, so
        every plugin covering them is asked for them on the next cycle."""
        lat_min, lon_min, lat_max, lon_max = box
        cells = lattice([lat_min, lon_min, lat_max, lon_max])
        if len(cells) > 64:   # a continent-sized view is not a place anyone is driving
            return
        t = time.monotonic()
        for c in cells:
            self.viewed[c] = t

    def cells_to_poll(self, sid: str, coverage: list) -> list[tuple[float, float]]:
        """Hot cells inside the coverage, plus a rotating slice of the rest."""
        s, w, n, e = coverage
        cutoff = time.monotonic() - VIEW_TTL_S
        def inside(c):
            return s - CELL_DEG <= c[0] <= n + CELL_DEG and w - CELL_DEG <= c[1] <= e + CELL_DEG
        hot = [c for c, t in self.viewed.items() if t >= cutoff and inside(c)]
        # Somewhere this source has had something to say before.
        seen = self.productive.get(sid, {})
        live = time.monotonic() - PRODUCTIVE_KEEP_S
        good = sorted((c for c, t in seen.items() if t >= live and inside(c)),
                      key=lambda c: -seen[c])[:PRODUCTIVE_PER_POLL]
        grid = lattice(coverage)
        pos = self._sweep_pos.get(sid, 0) % max(1, len(grid))
        sweep = [grid[(pos + i) % len(grid)] for i in range(min(SWEEP_PER_POLL, len(grid)))]
        self._sweep_pos[sid] = pos + SWEEP_PER_POLL
        out: list[tuple[float, float]] = []
        for c in hot + good + sweep:
            if c not in out:
                out.append(c)
        return out[:MAX_CELLS]

    async def poll_source(self, src: dict, client) -> int:
        """Fetch the cells that matter for one source; returns the count served."""
        sid = src["id"]
        now = self._now()
        try:
            hs = await self.handshake(src, client)
            base = src["base"].rstrip("/")
            sem = asyncio.Semaphore(CONCURRENCY)
            problems: list[str] = []
            kept_by_cell: dict[tuple[float, float], list[dict]] = {}

            # The handshake is cached for an hour, so most cycles never
            # make it and the first thing to touch a cold container is a
            # cell. Exactly one cell per cycle is allowed to wait out a
            # cold start; once it answers the instance is up and the
            # rest run at the normal timeout, so a dead plugin still
            # costs one wait rather than one per cell.
            warmed = {"done": False}

            async def fetch_cell(cell, timeout):
                return await self.fetch_json(
                    client, f"{base}/flare/v1/alerts", src=src,
                    params={"lat": cell[0], "lon": cell[1], "r": CELL_RADIUS_M},
                    timeout=timeout)

            async def one(cell):
                async with sem:
                    try:
                        try:
                            status, payload = await fetch_cell(cell, 20.0)
                        except (httpx.ConnectError, httpx.ConnectTimeout,
                                httpx.ReadTimeout, httpx.ReadError) as exc:
                            if warmed["done"]:
                                raise
                            warmed["done"] = True
                            log.info("flare source %s: waiting out a cold start (%s)",
                                     sid, type(exc).__name__)
                            status, payload = await fetch_cell(cell, COLD_START_TIMEOUT_S)
                    except ValueError as exc:
                        problems.append(f"cell {cell}: {exc}")
                        return
                    except httpx.HTTPError as exc:
                        problems.append(f"cell {cell}: {type(exc).__name__}")
                        return
                    if status != 200:
                        problems.append(f"cell {cell}: HTTP {status}")
                        return
                    kept, probs = flare.accept_alerts(payload, now=now)
                    problems.extend(probs[:3])
                    kept_by_cell[cell] = kept[: flare.MAX_PER_CELL]

            await asyncio.gather(*(one(c) for c in self.cells_to_poll(sid, hs["coverage"]["bbox"])))
            if problems and not kept_by_cell:
                raise RuntimeError(problems[0])  # every cell failed: the poll failed
            # Cells not polled this cycle keep what they had, for a while.
            t = time.monotonic()
            cells = self.cells.setdefault(sid, {})
            seen = self.productive.setdefault(sid, {})
            for c, kept in kept_by_cell.items():
                cells[c] = (t, kept)
                if kept:
                    seen[c] = t
            for c in [c for c, when in seen.items() if t - when > PRODUCTIVE_KEEP_S]:
                del seen[c]
            for c in [c for c, (ts, _) in cells.items() if t - ts > CELL_KEEP_S]:
                del cells[c]
            declared = set(hs.get("kinds") or [])
            seen: dict[str, dict] = {}
            for _, kept in cells.values():
                for a in kept:
                    if a["kind"] in declared:
                        seen.setdefault(a["id"], a)
            alerts = list(seen.values())[: flare.MAX_ALERTS]
            self.alerts[sid] = alerts
            held = self.status.get(sid, {})
            if alerts or now.timestamp() - held.get("held_at", 0) > COUNT_HOLD_S:
                held_count, held_at = len(alerts), now.timestamp()
            else:
                held_count, held_at = held.get("held_count", 0), held.get("held_at", 0)
            self.status[sid] = {"ok": True, "count": len(alerts), "last_ok": now.isoformat(),
                                "held_count": held_count, "held_at": held_at,
                                "problems": problems[:5], "name": hs.get("name")}
            self._fails.pop(sid, None)
        except Exception as exc:  # noqa: BLE001 - one bad source never stops the rest
            self.status[sid] = {**self.status.get(sid, {}), "ok": False,
                                "last_error": f"{type(exc).__name__}: {str(exc)[:160]}",
                                "last_error_at": now.isoformat()}
            if not (self.status[sid].get("held_at") or 0):  # never polled well
                self.status[sid].setdefault("held_count", 0)
            self._fails[sid] = self._fails.get(sid, 0) + 1
            self.status[sid]["fails"] = self._fails[sid]
            log.warning("flare source %s failed: %s", sid, self.status[sid]["last_error"])
        self._last_poll[sid] = time.monotonic()
        await self._write_status(sid)
        return len(self.alerts.get(sid, []))

    async def _write_status(self, sid: str) -> None:
        if time.monotonic() - self._last_status_write.get(sid, 0.0) < STATUS_WRITE_EVERY_S:
            return
        self._last_status_write[sid] = time.monotonic()
        with contextlib.suppress(Exception):
            st = self.status.get(sid, {})
            await self.store.put(sid, {k: st.get(k) for k in
                                       ("ok", "count", "last_ok", "last_error")})

    def due(self, src: dict) -> bool:
        # A source never polled is due now. (Comparing the monotonic clock
        # against 0 skipped the first poll on a machine booted less than a
        # poll period ago, which is what a fresh CI runner is.)
        last = self._last_poll.get(src["id"])
        if last is None:
            return True
        hs = self.handshakes.get(src["id"])
        period = max(POLL_FLOOR_S, int((hs[1].get("refresh_s") if hs else 0) or 0))
        # A source that keeps failing waits longer each time, up to an
        # hour, so a dead plugin costs one request an hour rather than
        # one a minute for weeks.
        fails = self._fails.get(src["id"], 0)
        if fails >= FAILS_BEFORE_BACKOFF:
            period = min(MAX_BACKOFF_S, period * 2 ** (fails - FAILS_BEFORE_BACKOFF + 1))
        return time.monotonic() - last >= period

    async def run_once(self, client) -> None:
        if time.monotonic() - self._sources_loaded > 60 or not self._sources_loaded:
            with contextlib.suppress(Exception):
                await self.refresh_sources()
        deadline = time.monotonic() + CYCLE_DEADLINE_S
        for src in list(self.sources.values()):
            if time.monotonic() > deadline:
                log.warning("flare poll cycle out of time; the rest wait for the next one")
                break
            if self.due(src):
                await self.poll_source(src, client)

    async def run(self, client_factory) -> None:
        """Background task for the demo's lifespan."""
        while True:
            try:
                await self.run_once(client_factory())
            except Exception:  # noqa: BLE001
                log.exception("flare poll cycle failed")
            await asyncio.sleep(15)

    def markers_for_bbox(self, box) -> list[dict]:
        lat_min, lon_min, lat_max, lon_max = box
        now = self._now()
        out = []
        for sid, alerts in self.alerts.items():
            src = self.sources.get(sid)
            if not src:
                continue
            for a in alerts:
                if not (lat_min <= a["lat"] <= lat_max and lon_min <= a["lon"] <= lon_max):
                    continue
                if flare.validate_alert(a, now=now):  # stale since the poll
                    continue
                out.append(alert_marker(src, a))
        return out

    def catalog_count(self, sid: str) -> tuple[int, bool]:
        """(count, stale): the alerts held now, or the last good count while
        it is recent; stale when the last good poll is old or the last poll
        failed."""
        st = self.status.get(sid, {})
        now = self._now().timestamp()
        count = st.get("count", 0)
        if not count and now - (st.get("held_at") or 0) <= COUNT_HOLD_S:
            count = st.get("held_count", 0)
        last_ok = st.get("last_ok")
        try:
            age = now - datetime.fromisoformat(last_ok).timestamp() if last_ok else None
        except ValueError:
            age = None
        stale = st.get("ok") is False or age is None or age > STALE_AFTER_S
        return count, stale

    def card(self, sid: str) -> dict | None:
        """One catalog entry: what the marketplace tile and the app's
        plugin screen show. None for a private source (never shown
        outside its owner's own devices) or an unknown id."""
        src = self.sources.get(sid)
        if not src or src.get("visibility") not in ("public", "unlisted"):
            return None
        st = self.status.get(sid, {})
        hs = (self.handshakes.get(sid) or (0, {}))[1]
        count, stale = self.catalog_count(sid)
        return {"id": sid, "name": src.get("name") or sid,
                "attribution": src.get("attribution"), "trust": src.get("trust"),
                "tier": flare.tier_of(src), "visibility": src.get("visibility"),
                "count": count, "stale": stale, "ok": st.get("ok"),
                "last_ok": st.get("last_ok"),
                # For the marketplace cards.
                "description": hs.get("description"),
                "coverage": (hs.get("coverage") or {}).get("bbox"),
                "kinds": hs.get("kinds") or [],
                "capabilities": hs.get("capabilities") or {},
                "base": _https_only(src.get("base"))}

    def public_sources(self) -> list[dict]:
        cards = (self.card(sid) for sid, src in self.sources.items()
                 if src.get("visibility") == "public")
        return [c for c in cards if c]


poller = Poller()


# ------------------------------------------------------------- reports
# CommuteScout's own community source: what signed-in people report on
# the map (and, later, in the app). Reports live in memory with a
# Firestore copy so a restart keeps them, expire by kind, and are
# forwarded to every plugin that accepts reports under a per-plugin
# pseudonym. Three "not there" votes hide a report.

REPORTS_COLLECTION = "flare_reports"
REPORTS_SOURCE = {
    "id": "commutescout", "name": "CommuteScout community", "trust": "verified",
    "visibility": "public", "base": "https://commutescout.com", "protocol": "flare/1",
    "attribution": {"name": "CommuteScout community reports",
                    "url": "https://commutescout.com/map"},
}
REPORT_TTL_S: dict[str, int] = {
    "POLICE": 1800, "CRASH": 2700, "HAZARD": 3600, "WEATHER": 3600,
    "ROAD_CLOSED": 7200, "LANE_CLOSED": 5400, "RAMP_CLOSED": 5400, "JAM": 1200,
    "CHAINS": 7200, "CAMERA": 86400, "MAP_ISSUE": 86400, "OTHER": 1800,
}
REPORT_PER_DAY = 20
REPORT_GAP_S = 60
GONE_VOTES_TO_HIDE = 3
FORWARD_TIMEOUT_S = 8.0


def report_ttl(kind: str) -> int:
    for prefix, ttl in REPORT_TTL_S.items():
        if kind.startswith(prefix):
            return ttl
    return REPORT_TTL_S["OTHER"]


def _salt() -> str:
    return os.environ.get("REPORT_SALT") or os.environ.get("TELEMETRY_SALT") or "dev"


class Reports:
    """The community source's records and votes."""

    def __init__(self, store=None, *, now=None) -> None:
        self._store = store
        self._now = now or (lambda: datetime.now(UTC))
        self.records: dict[str, dict] = {}   # alert id -> alert record (+ private fields)
        self.daily = DailyCounter()
        self._last: dict[str, float] = {}

    @property
    def store(self):
        if self._store is None:
            self._store = FirestoreSourceStore(collection=REPORTS_COLLECTION)
        return self._store

    async def load(self) -> int:
        now = self._now()
        n = 0
        for d in await self.store.list():
            rec = {k: v for k, v in d.items() if k != "id"}
            rec["id"] = d["id"]
            if not flare.validate_alert(_public(rec), now=now):
                self.records[rec["id"]] = rec
                n += 1
        return n

    def allow(self, uid: str) -> str | None:
        """None when the account may report now, else why not."""
        t = time.monotonic()
        if t - self._last.get(uid, -1e9) < REPORT_GAP_S:
            return "one report a minute; try again shortly"
        if not self.daily.allow(uid, REPORT_PER_DAY):
            return f"{REPORT_PER_DAY} reports a day is the limit"
        self._last[uid] = t
        return None

    async def add(self, uid: str, kind: str, lat: float, lon: float, *,
                  heading: float | None = None, description: str = "") -> dict:
        now = self._now()
        rec = {
            "id": secrets.token_hex(6), "kind": kind, "lat": round(lat, 6), "lon": round(lon, 6),
            "report_ts": now.isoformat(), "n_confirmations": 0, "reliability": 0.5,
            "ttl_s": report_ttl(kind), "notify": False,
            "_uid": uid, "_gone": 0, "_voters": [],
        }
        if heading is not None:
            rec["heading_deg"] = heading
        if description:
            rec["description"] = description[: flare.MAX_DESCRIPTION]
        self.records[rec["id"]] = rec
        with contextlib.suppress(Exception):
            await self.store.put(rec["id"], {**rec, "expire_at": now + timedelta(days=2)})
        return _public(rec)

    async def confirm(self, alert_id: str, vote: str, uid: str) -> dict | None:
        rec = self.records.get(alert_id)
        if not rec or vote not in flare.VOTES:
            return None
        if uid in rec["_voters"] or uid == rec["_uid"]:
            return _public(rec)
        rec["_voters"].append(uid)
        if vote == "up":
            rec["n_confirmations"] += 1
            rec["confirm_ts"] = self._now().isoformat()
            rec["reliability"] = min(1.0, 0.5 + 0.15 * rec["n_confirmations"])
        else:
            rec["_gone"] += 1
            rec["reliability"] = max(0.0, rec["reliability"] - 0.2)
        if rec["_gone"] >= GONE_VOTES_TO_HIDE:
            self.records.pop(alert_id, None)
            with contextlib.suppress(Exception):
                await self.store.delete(alert_id)
            return None
        with contextlib.suppress(Exception):
            await self.store.put(alert_id, {k: v for k, v in rec.items() if k != "id"})
        return _public(rec)

    def markers_for_bbox(self, box) -> list[dict]:
        lat_min, lon_min, lat_max, lon_max = box
        now = self._now()
        out = []
        for rid, rec in list(self.records.items()):
            pub = _public(rec)
            if flare.validate_alert(pub, now=now):
                self.records.pop(rid, None)
                continue
            if lat_min <= pub["lat"] <= lat_max and lon_min <= pub["lon"] <= lon_max:
                out.append(alert_marker(REPORTS_SOURCE, pub))
        return out


def _public(rec: dict) -> dict:
    return {k: v for k, v in rec.items() if not k.startswith("_") and k != "expire_at"}


reports = Reports()


def _all_markers_for_bbox(box) -> list[dict]:
    return poller.markers_for_bbox(box) + reports.markers_for_bbox(box)


async def _forward_report(src: dict, pub: dict, uid: str, client) -> str | None:
    """Send a report to one plugin under a per-plugin pseudonym."""
    try:
        hs = await poller.handshake(src, client)
        if not (hs.get("capabilities") or {}).get("report"):
            return None
        if pub["kind"] not in set(hs.get("kinds") or []):
            return None
        body = {"kind": pub["kind"], "lat": pub["lat"], "lon": pub["lon"],
                "ts": pub["report_ts"], "description": pub.get("description", ""),
                "reporter": flare.reporter_pseudonym(src["id"], uid, _salt()),
                "client": "commutescout-web/1"}
        if "heading_deg" in pub:
            body["heading_deg"] = pub["heading_deg"]
        if not flare.fetchable_base(src.get("base")):
            return None
        r = await client.post(f"{src['base'].rstrip('/')}/flare/v1/report", json=body,
                              headers=poller._headers(src), timeout=FORWARD_TIMEOUT_S,
                              follow_redirects=False)
        return src["id"] if r.status_code in (201, 202) else None
    except Exception:  # noqa: BLE001 - a slow plugin never blocks the reporter
        return None


async def api_flare_report(request: Request) -> JSONResponse:
    """A signed-in person reports something at a point on the map."""
    from ca_roads_demo import watch

    claims = await watch.verify_user(request)
    if not claims:
        return JSONResponse({"error": "sign in required"}, status_code=401)
    body = await watch._read_json(request) or {}
    kind = body.get("kind")
    if kind not in flare.KINDS:
        return JSONResponse({"error": "kind: not in the Flare vocabulary"}, status_code=400)
    try:
        lat, lon = float(body.get("lat")), float(body.get("lon"))
    except (TypeError, ValueError):
        return JSONResponse({"error": "lat and lon required"}, status_code=400)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return JSONResponse({"error": "lat and lon out of range"}, status_code=400)
    heading = body.get("heading_deg")
    if heading is not None:
        try:
            heading = float(heading) % 360
        except (TypeError, ValueError):
            return JSONResponse({"error": "heading_deg: number"}, status_code=400)
    description = watch.clean_text(str(body.get("description") or ""), flare.MAX_DESCRIPTION)
    uid = claims["sub"]
    why = reports.allow(uid)
    if why:
        return JSONResponse({"error": why}, status_code=429, headers={"Retry-After": "60"})
    pub = await reports.add(uid, kind, lat, lon, heading=heading, description=description)
    forwarded: list[str] = []
    with contextlib.suppress(Exception):
        from ca_roads_mcp import server as tools

        client = tools.get_road().client
        results = await asyncio.gather(*(
            _forward_report(src, pub, uid, client) for src in poller.sources.values()))
        forwarded = [r for r in results if r]
    return JSONResponse({"id": f"{REPORTS_SOURCE['id']}:{pub['id']}", "alert": pub,
                         "forwarded": forwarded}, status_code=201)


async def api_flare_confirm(request: Request) -> JSONResponse:
    """A signed-in person says an alert is still there, or gone."""
    from ca_roads_demo import watch

    claims = await watch.verify_user(request)
    if not claims:
        return JSONResponse({"error": "sign in required"}, status_code=401)
    body = await watch._read_json(request) or {}
    alert_id = str(body.get("alert_id") or "")
    vote = body.get("vote")
    if vote not in flare.VOTES or ":" not in alert_id:
        return JSONResponse({"error": "alert_id and vote up|gone required"}, status_code=400)
    sid, _, local_id = alert_id.partition(":")
    uid = claims["sub"]
    if sid == REPORTS_SOURCE["id"]:
        if local_id not in reports.records:
            return JSONResponse({"error": "no such alert"}, status_code=404)
        rec = await reports.confirm(local_id, vote, uid)
        return JSONResponse({"id": alert_id, "vote": vote, "hidden": rec is None,
                             "alert": rec})
    src = poller.sources.get(sid)
    if not src:
        return JSONResponse({"error": "no such source"}, status_code=404)
    try:
        from ca_roads_mcp import server as tools

        client = tools.get_road().client
        if not flare.fetchable_base(src.get("base")):
            return JSONResponse({"error": "no such source"}, status_code=404)
        r = await client.post(f"{src['base'].rstrip('/')}/flare/v1/confirm", json={
            "alert_id": local_id, "vote": vote, "ts": datetime.now(UTC).isoformat(),
            "reporter": flare.reporter_pseudonym(sid, uid, _salt())},
            headers=poller._headers(src), timeout=FORWARD_TIMEOUT_S,
            follow_redirects=False)
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": "the source did not answer"}, status_code=502)
    if r.status_code == 404:
        return JSONResponse({"error": "no such alert"}, status_code=404)
    if r.status_code != 200:
        return JSONResponse({"error": f"the source answered {r.status_code}"}, status_code=502)
    return JSONResponse({"id": alert_id, "vote": vote, "forwarded": True})


# ---------------------------------------------------------------- HTTP

async def api_flare_sources(request: Request) -> JSONResponse:
    """Public: the enabled public sources, for attribution in the
    Layers pane and the app's Sources screen. `?id=` fetches one
    plugin by id, which is how an unlisted plugin is shared: by link,
    never on the catalog."""
    spec = "https://github.com/nicglazkov/commutescout/blob/main/docs/flare.md"
    sid = (request.query_params.get("id") or "").strip()[:80]
    if sid:
        card = poller.card(sid)
        if not card:
            return JSONResponse({"error": "no such plugin"}, status_code=404)
        return JSONResponse({"sources": [card], "spec": spec})
    return JSONResponse({"sources": poller.public_sources(), "spec": spec})


async def api_admin_flare(request: Request) -> JSONResponse:
    """Admin: list sources with status, or add, enable, disable, remove.

    ``add`` takes a manifest (docs/flare.md), validates it, fetches the
    handshake once so a typo fails here and not silently in the poller,
    and stores it enabled. A ``token`` in the manifest is kept server
    side and never returned.
    """
    from ca_roads_demo import watch

    if not await watch._require_admin(request):
        return JSONResponse({"error": "admin only"}, status_code=403)
    store = get_source_store()
    if request.method == "GET":
        docs = await store.list()
        for d in docs:
            d.pop("token", None)
            d["status"] = poller.status.get(d["id"], {})
        return JSONResponse({"sources": docs})
    body = await watch._read_json(request) or {}
    action = body.get("action") or "add"
    if action == "add":
        manifest = body.get("manifest") or {}
        if not manifest and isinstance(body.get("base"), str):
            # Add by URL: the plugin's own handshake supplies id, name and
            # attribution; the tier is public and unreviewed unless said.
            base = body["base"].strip().rstrip("/")
            if not base.startswith("https://"):
                return JSONResponse({"error": "base: https URL"}, status_code=400)
            try:
                from ca_roads_mcp import server as tools

                hs = await poller.handshake({"id": "probe", "base": base}, tools.get_road().client)
            except Exception as exc:  # noqa: BLE001
                return JSONResponse({"error": f"handshake failed: {str(exc)[:160]}"},
                                    status_code=422)
            manifest = {"id": hs.get("id"), "name": hs.get("name"), "base": base,
                        "protocol": "flare/1",
                        "visibility": body.get("visibility") or "public",
                        "trust": body.get("trust") or "community",
                        "attribution": hs.get("attribution")
                        or {"name": hs.get("name"), "url": base}}
        errs = flare.validate_manifest(manifest)
        if errs:
            return JSONResponse({"error": "manifest: " + "; ".join(errs)}, status_code=400)
        sid = manifest["id"]
        doc = {k: manifest[k] for k in ("id", "name", "base", "protocol", "visibility",
                                        "trust", "attribution", "token") if k in manifest}
        doc.update({"enabled": True, "added_at": datetime.now(UTC).isoformat()})
        try:
            from ca_roads_mcp import server as tools

            hs = await poller.handshake(doc, tools.get_road().client)
            doc["name"] = doc.get("name") or hs.get("name")
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"error": f"handshake failed: {str(exc)[:160]}"},
                                status_code=422)
        await store.put(sid, doc)
        poller._sources_loaded = 0.0  # pick it up on the next cycle
        doc.pop("token", None)
        return JSONResponse({"source": doc})
    sid = watch._safe_id(str(body.get("id") or ""))
    if not sid or not await store.get(sid):
        return JSONResponse({"error": "no such source"}, status_code=404)
    if action in ("enable", "disable"):
        await store.put(sid, {"enabled": action == "enable"})
    elif action == "remove":
        await store.delete(sid)
        poller.alerts.pop(sid, None)
    else:
        return JSONResponse({"error": "action must be add, enable, disable or remove"},
                            status_code=400)
    poller._sources_loaded = 0.0
    return JSONResponse({"id": sid, "action": action})
