"""The cell poller and the Flare records it serves.

One degree cells, and only the cells someone asked about in the last ten
minutes are ever fetched: an idle cell costs Waze nothing.

A one-degree cell is about 110 km across, and the upstream thins a wide
viewport down hard, so a cell is not fetched from its center. It is swept:
each cell holds a lattice of sub-cell points, the points take turns stalest
first, and each turn runs the shrinking-box series around its own point. That
way the far corner of a cell gets the same attention as the middle, and the
request rate stays at a few queries every few seconds however wide the
coverage box is.

Alerts themselves are kept in one cache for the whole service rather than one
per cell, because the RT protocol sends each alert once per session and not
once per query: an alert first delivered to one cell's query is never re-sent
for the neighbouring cell that overlaps it. See waze/cache.py.
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime

import mapping
from waze.cache import ConfirmTracker
from waze.constants import M_PER_DEG_LAT, m_per_deg_lon
from waze.source import PRIMARY_VIEWPORT, WazeSource

log = logging.getLogger("waze_relay.store")

CELL_DEG = 1.0
CELL_RADIUS_M = 80_000        # what a mediated caller asks for at a cell center
SUB_CELLS = 2                 # the lattice inside one cell, per side
WANTED_TTL_S = 600.0          # a cell is fetched only if it was asked about this recently
STALE_GRACE_S = 300.0         # serve on after a failure for this long, then serve nothing
GONE_VOTES_TO_HIDE = 3
VOTE_TTL_S = 2 * 3600.0
PACE_S = 0.5
IDLE_TICK_S = 2.0
MAX_ALERTS = 500
ID_OK = re.compile(r"^[A-Za-z0-9_.:@-]{1,128}$")


def meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    kx = 111_320 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot((lat2 - lat1) * 111_320, (lon2 - lon1) * kx)


def cell_of(lat: float, lon: float) -> tuple[int, int]:
    return math.floor(lat / CELL_DEG), math.floor(lon / CELL_DEG)


def cell_center(cell: tuple[int, int]) -> tuple[float, float]:
    return (cell[0] + 0.5) * CELL_DEG, (cell[1] + 0.5) * CELL_DEG


def sub_cell_center(cell: tuple[int, int], row: int, col: int, per_side: int) -> tuple:
    """The middle of one square of a cell's lattice."""
    step = CELL_DEG / per_side
    return (cell[0] * CELL_DEG + (row + 0.5) * step,
            cell[1] * CELL_DEG + (col + 0.5) * step)


def sub_cell_radius_m(lat: float, per_side: int) -> float:
    """A radius that still covers a lattice square after the client shrinks
    its primary viewport to three quarters."""
    half = CELL_DEG / per_side / 2
    return math.hypot(half * M_PER_DEG_LAT, half * m_per_deg_lon(lat)) / PRIMARY_VIEWPORT


class Votes:
    """The confirmations this plugin collected, kept in memory.

    Waze itself gets nothing from them on the public deployment: they raise
    the confirmation count and the confidence the plugin reports, and enough
    "not there" votes hide the alert.
    """

    def __init__(self, now: Callable[[], float] | None = None) -> None:
        self._now = now or time.time
        self._up: dict[str, set[str]] = {}
        self._gone: dict[str, set[str]] = {}
        self._confirmed_at: dict[str, float] = {}
        self._touched: dict[str, float] = {}

    def add(self, alert_id: str, vote: str, reporter: str) -> None:
        now = self._now()
        self._prune(now)
        self._touched[alert_id] = now
        bucket = self._up if vote == "up" else self._gone
        if reporter in bucket.setdefault(alert_id, set()):
            return
        bucket[alert_id].add(reporter)
        if vote == "up":
            self._confirmed_at[alert_id] = now

    def ups(self, alert_id: str) -> int:
        return len(self._up.get(alert_id, ()))

    def confirmed_at(self, alert_id: str) -> float | None:
        return self._confirmed_at.get(alert_id)

    def hidden(self, alert_id: str) -> bool:
        return len(self._gone.get(alert_id, ())) >= GONE_VOTES_TO_HIDE

    def _prune(self, now: float) -> None:
        for alert_id in [a for a, t in self._touched.items() if now - t > VOTE_TTL_S]:
            for store in (self._up, self._gone, self._confirmed_at, self._touched):
                store.pop(alert_id, None)


class Store:
    """What the HTTP layer reads, and the loop that keeps it fresh."""

    def __init__(self, source: WazeSource, *, bbox: list[float], refresh_s: int = 60,
                 sub_cells: int = SUB_CELLS,
                 now: Callable[[], float] | None = None,
                 wall_clock: Callable[[], float] | None = None) -> None:
        self.source = source
        self.bbox = bbox
        self.refresh_s = refresh_s
        self.sub_cells = max(1, sub_cells)
        self._now = now or time.monotonic
        self._wall = wall_clock or time.time
        self.votes = Votes(now=self._wall)
        self.confirmations = ConfirmTracker(now=self._wall)
        self._wanted: dict[tuple[int, int], float] = {}
        self._point_ok: dict[tuple[int, int, int, int], float] = {}
        self._lock = asyncio.Lock()

    # -------------------------------------------------------------- asks

    def want(self, lat: float, lon: float) -> None:
        """Remember that someone asked about this point, so its cell joins
        the rotation."""
        self._wanted[cell_of(lat, lon)] = self._now()

    def wanted_cells(self) -> list[tuple[int, int]]:
        now = self._now()
        for cell in [c for c, t in self._wanted.items() if now - t > WANTED_TTL_S]:
            self._wanted.pop(cell, None)
            for point in [p for p in self._point_ok if p[:2] == cell]:
                self._point_ok.pop(point, None)
        return list(self._wanted)

    def wanted_points(self) -> list[tuple[int, int, int, int]]:
        """Every lattice square of every cell still in the rotation."""
        return [(*cell, row, col)
                for cell in self.wanted_cells()
                for row in range(self.sub_cells)
                for col in range(self.sub_cells)]

    def in_coverage(self, lat: float, lon: float) -> bool:
        south, west, north, east = self.bbox
        return south - 1 <= lat <= north + 1 and west - 1 <= lon <= east + 1

    # ------------------------------------------------------------ serving

    @property
    def fresh(self) -> bool:
        """Whether the data is recent enough to serve at all: the plan allows
        five minutes of grace past the refresh window, then nothing."""
        if self.source.last_ok is None:
            return False
        return self._now() - self.source.last_ok <= self.refresh_s + STALE_GRACE_S

    @property
    def as_of(self) -> str:
        """When the plugin last refreshed its own data."""
        age = 0.0 if self.source.last_ok is None else max(
            0.0, self._now() - self.source.last_ok)
        return datetime.fromtimestamp(self._wall() - age, UTC).isoformat()

    def records(self) -> list[dict]:
        """Every cached alert as a Flare record, expired ones dropped."""
        if not self.fresh:
            return []
        now = self._wall()
        out = []
        for alert in self.source.snapshot():
            record = self.to_record(alert, now)
            if record is not None:
                out.append(record)
        return out

    def near(self, lat: float, lon: float, radius_m: float) -> list[dict]:
        """The records within ``radius_m`` of a point, nearest first."""
        hits = [(meters(lat, lon, r["lat"], r["lon"]), r) for r in self.records()]
        hits = [(d, r) for d, r in hits if d <= radius_m]
        hits.sort(key=lambda pair: pair[0])
        return [r for _, r in hits[:MAX_ALERTS]]

    def record_by_id(self, alert_id: str) -> dict | None:
        for record in self.records():
            if record["id"] == alert_id:
                return record
        return None

    def to_record(self, alert, now: float) -> dict | None:
        """One cached Waze alert as a Flare record, or None when it is not a
        road condition, has been voted away, or has gone stale."""
        kind = mapping.flare_kind(alert.type, alert.subtype)
        if kind is None or not alert.uuid:
            return None
        alert_id = f"wz:{alert.uuid}"
        # Flare spells out what an id may contain. Waze uuids fit, but an
        # upstream that ever sends something else is dropped here rather than
        # failing the caller's validation.
        if not ID_OK.match(alert_id) or self.votes.hidden(alert_id):
            return None
        thumbs = alert.n_thumbs_up or 0
        confirmations = thumbs + self.votes.ups(alert_id)
        report_ts = alert.pub_millis / 1000.0
        confirm_ts = self.confirmations.confirm_ts(alert.uuid, thumbs)
        voted_at = self.votes.confirmed_at(alert_id)
        if voted_at is not None:
            confirm_ts = max(confirm_ts or 0.0, voted_at)
        ttl_s = mapping.ttl_for(kind)
        if (confirm_ts or report_ts) + ttl_s < now:
            return None
        record = {
            "id": alert_id,
            "kind": kind,
            "lat": round(alert.lat, 6),
            "lon": round(alert.lon, 6),
            "report_ts": _iso(report_ts),
            "n_confirmations": confirmations,
            "reliability": round(mapping.reliability(confirmations), 3),
            "ttl_s": ttl_s,
        }
        if confirm_ts:
            record["confirm_ts"] = _iso(confirm_ts)
        # Waze leaves the azimuth at zero when the reporter's heading is not
        # known, and Flare reads a heading as "this direction only", so a zero
        # is left out rather than published as due north.
        if alert.magvar:
            record["heading_deg"] = alert.magvar % 360
        if alert.street:
            record["road_names"] = [alert.street]
        extra = {"waze_type": alert.type}
        if alert.subtype:
            extra["waze_subtype"] = alert.subtype
        if alert.city:
            extra["city"] = alert.city
        record["extra"] = extra
        return record

    # ------------------------------------------------------------ polling

    async def poll_once(self) -> bool:
        """Refresh the stalest lattice square that is due. True when one was
        fetched."""
        points = self.wanted_points()
        if not points or self.source.backoff_remaining_s() > 0:
            return False
        # The stalest square goes first, and no square is fetched more often
        # than once per refresh window. When the coverage box is wide enough
        # that a full sweep takes longer than that, the stalest square is
        # always overdue and the loop simply keeps sweeping.
        point = min(points, key=lambda p: self._point_ok.get(p, 0.0))
        if self._now() - self._point_ok.get(point, 0.0) < self.refresh_s:
            return False
        lat, lon = sub_cell_center(point[:2], point[2], point[3], self.sub_cells)
        async with self._lock:
            try:
                count = await self.source.refresh(
                    lat, lon, sub_cell_radius_m(lat, self.sub_cells))
                self._point_ok[point] = self._now()
                log.info("%.2f,%.2f refreshed, %s alerts cached", lat, lon, count)
            except Exception as exc:  # noqa: BLE001 - one bad square never stops the rest
                self.source.note_failure(exc)
                log.warning("%.2f,%.2f failed: %s: %s", lat, lon, type(exc).__name__, exc)
        return True

    async def run(self) -> None:
        """The background loop, started with the service."""
        while True:
            try:
                if not await self.poll_once():
                    await asyncio.sleep(IDLE_TICK_S)
                else:
                    await asyncio.sleep(PACE_S)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                log.exception("poll cycle failed")
                await asyncio.sleep(IDLE_TICK_S)

    def status(self) -> dict:
        """Counts and freshness, for a health check. Nothing identifying."""
        points = self.wanted_points()
        return {
            "alerts": len(self.source.cache),
            "served": len(self.records()),
            "cells_wanted": len(self._wanted),
            "points_wanted": len(points),
            "points_swept": sum(1 for p in points if p in self._point_ok),
            "fresh": self.fresh,
            "registered": self.source.registered,
            "backoff_s": round(self.source.backoff_remaining_s()),
            "last_error": self.source.last_error,
            "as_of": self.as_of,
        }


def _iso(epoch_s: float) -> str:
    return datetime.fromtimestamp(epoch_s, UTC).isoformat()
