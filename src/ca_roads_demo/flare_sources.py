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
import logging
import math
import os
import time
from datetime import UTC, datetime

from starlette.requests import Request
from starlette.responses import JSONResponse

from ca_roads import flare

log = logging.getLogger("ca_roads_demo.flare")

COLLECTION = "flare_sources"
CELL_DEG = 1.0
CELL_RADIUS_M = 80_000       # covers a one-degree cell's half diagonal
MAX_CELLS = 200
POLL_FLOOR_S = 60
HANDSHAKE_TTL_S = 3600
STATUS_WRITE_EVERY_S = 600
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
    def __init__(self, project: str | None = None) -> None:
        from google.cloud import firestore

        self.db = firestore.AsyncClient(
            project=project or os.environ.get("GOOGLE_CLOUD_PROJECT") or "ca-roads-mcp")

    def _col(self):
        return self.db.collection(COLLECTION)

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


def cells_for(bbox: list) -> list[tuple[float, float]]:
    """Centers of the one-degree cells that tile ``[s, w, n, e]``,
    capped at MAX_CELLS (a nationwide plugin gets its middle first)."""
    s, w, n, e = bbox
    lats = [s + CELL_DEG / 2 + i * CELL_DEG for i in range(int(math.ceil((n - s) / CELL_DEG)))]
    lons = [w + CELL_DEG / 2 + j * CELL_DEG for j in range(int(math.ceil((e - w) / CELL_DEG)))]
    cells = [(round(la, 3), round(lo, 3)) for la in lats for lo in lons]
    if len(cells) > MAX_CELLS:
        cy, cx = (s + n) / 2, (w + e) / 2
        cells.sort(key=lambda c: (c[0] - cy) ** 2 + (c[1] - cx) ** 2)
        cells = cells[:MAX_CELLS]
    return cells


def alert_marker(src: dict, a: dict) -> dict:
    """The map marker for one accepted alert."""
    attribution = src.get("attribution") or {}
    m = {
        "kind": "plugin",
        "id": f"{src['id']}:{a['id']}",
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
        "source_url": a.get("source_url") or attribution.get("url"),
        "trust": src.get("trust") or "community",
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
        self._last_status_write: dict[str, float] = {}
        self._sources_loaded = 0.0

    @property
    def store(self):
        if self._store is None:
            self._store = get_source_store()
        return self._store

    async def refresh_sources(self) -> None:
        docs = await self.store.list()
        self.sources = {d["id"]: d for d in docs if d.get("enabled", True)
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

    async def handshake(self, src: dict, client) -> dict:
        sid = src["id"]
        hit = self.handshakes.get(sid)
        if hit and time.monotonic() - hit[0] < HANDSHAKE_TTL_S:
            return hit[1]
        r = await client.get(f"{src['base'].rstrip('/')}/flare/v1/handshake",
                             headers=self._headers(src), timeout=15.0)
        r.raise_for_status()
        hs = r.json()
        errs = flare.validate_handshake(hs)
        if errs:
            raise ValueError("handshake: " + "; ".join(errs))
        self.handshakes[sid] = (time.monotonic(), hs)
        return hs

    async def poll_source(self, src: dict, client) -> int:
        """Fetch every cell of one source; returns the accepted count."""
        sid = src["id"]
        now = self._now()
        try:
            hs = await self.handshake(src, client)
            base = src["base"].rstrip("/")
            sem = asyncio.Semaphore(CONCURRENCY)
            seen: dict[str, dict] = {}
            problems: list[str] = []

            async def one(cell):
                async with sem:
                    r = await client.get(f"{base}/flare/v1/alerts",
                                         params={"lat": cell[0], "lon": cell[1],
                                                 "r": CELL_RADIUS_M},
                                         headers=self._headers(src), timeout=20.0)
                    if r.status_code != 200 or len(r.content) > flare.MAX_BYTES:
                        problems.append(f"cell {cell}: HTTP {r.status_code}")
                        return
                    kept, probs = flare.accept_alerts(r.json(), now=now)
                    problems.extend(probs[:3])
                    for a in kept[: flare.MAX_PER_CELL]:
                        seen.setdefault(a["id"], a)

            await asyncio.gather(*(one(c) for c in cells_for(hs["coverage"]["bbox"])))
            declared = set(hs.get("kinds") or [])
            alerts = [a for a in seen.values() if a["kind"] in declared][: flare.MAX_ALERTS]
            self.alerts[sid] = alerts
            self.status[sid] = {"ok": True, "count": len(alerts), "last_ok": now.isoformat(),
                                "problems": problems[:5], "name": hs.get("name")}
        except Exception as exc:  # noqa: BLE001 - one bad source never stops the rest
            self.status[sid] = {**self.status.get(sid, {}), "ok": False,
                                "last_error": f"{type(exc).__name__}: {str(exc)[:160]}",
                                "last_error_at": now.isoformat()}
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
        hs = self.handshakes.get(src["id"])
        period = max(POLL_FLOOR_S, int((hs[1].get("refresh_s") if hs else 0) or 0))
        return time.monotonic() - self._last_poll.get(src["id"], 0.0) >= period

    async def run_once(self, client) -> None:
        if time.monotonic() - self._sources_loaded > 60 or not self._sources_loaded:
            with contextlib.suppress(Exception):
                await self.refresh_sources()
        for src in list(self.sources.values()):
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

    def public_sources(self) -> list[dict]:
        out = []
        for sid, src in self.sources.items():
            if src.get("visibility") != "public":
                continue
            st = self.status.get(sid, {})
            out.append({"id": sid, "name": src.get("name") or sid,
                        "attribution": src.get("attribution"), "trust": src.get("trust"),
                        "count": st.get("count", 0), "ok": st.get("ok"),
                        "last_ok": st.get("last_ok")})
        return out


poller = Poller()


# ---------------------------------------------------------------- HTTP

async def api_flare_sources(_: Request) -> JSONResponse:
    """Public: the enabled public sources, for attribution in the
    Layers pane and the app's Sources screen."""
    return JSONResponse({"sources": poller.public_sources(),
                         "spec": "https://github.com/nicglazkov/commutescout/blob/main/docs/flare.md"})


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
