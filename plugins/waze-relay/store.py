"""The tile poller and the Flare records it serves.

Coverage is demand-driven, not a fixed box. The plugin answers for anywhere
in its coverage, but it only fetches tiles somebody actually asked about in
the last ten minutes: an unasked tile costs Waze nothing, however wide the
coverage box is. There is no background sweep of the box.

A tile is a tenth of a degree, about 11 km on a side, and each one is
fetched with a single query at city zoom. That size is the point. The
upstream thins what it returns for a wide viewport the same way the app
shows fewer pins zoomed out, and the previous design, which queried
one-degree cells from four points with boxes 70 km wide, held 43 alerts for
the whole Los Angeles basin on a weekday afternoon. A caller asks for a
disc around a person or a point along a route, the disc becomes the few
tiles it touches, and every tile is fetched at a zoom where the upstream
sends everything it has.

One session runs one query at a time, so the tiles take turns, stalest
first, and no tile is fetched more often than once per refresh window.
The wanted set is capped; past the cap the tiles nobody has asked about
for longest drop out, so a flood of asks degrades to slower laps rather
than to nothing.

Alerts themselves are kept in one cache for the whole service rather than
one per tile, because the RT protocol sends each alert once per session and
not once per query: an alert first delivered to one tile's query is never
re-sent for the neighbouring tile that overlaps it. See waze/cache.py.
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

TILE_DEG = 0.1                # a city-zoom tile, about 11 km on a side
CELL_RADIUS_M = 80_000        # the radius a caller gets when it names none
MAX_TILES = 400               # about forty people's neighbourhoods at once
WANTED_TTL_S = 600.0          # a tile is fetched only if it was asked about this recently
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


def tile_of(lat: float, lon: float, tile_deg: float = TILE_DEG) -> tuple[int, int]:
    return math.floor(lat / tile_deg), math.floor(lon / tile_deg)


def tile_center(tile: tuple[int, int], tile_deg: float = TILE_DEG) -> tuple[float, float]:
    return (tile[0] + 0.5) * tile_deg, (tile[1] + 0.5) * tile_deg


def tiles_for_disc(lat: float, lon: float, radius_m: float,
                   tile_deg: float = TILE_DEG) -> list[tuple[int, int]]:
    """Every tile a disc touches: the tile under the point for a zero
    radius, and otherwise each tile whose nearest edge is inside it."""
    if radius_m <= 0:
        return [tile_of(lat, lon, tile_deg)]
    d_lat = radius_m / M_PER_DEG_LAT
    d_lon = radius_m / max(m_per_deg_lon(lat), 1.0)
    rows = range(math.floor((lat - d_lat) / tile_deg), math.floor((lat + d_lat) / tile_deg) + 1)
    cols = range(math.floor((lon - d_lon) / tile_deg), math.floor((lon + d_lon) / tile_deg) + 1)
    out = []
    for row in rows:
        for col in cols:
            south, west = row * tile_deg, col * tile_deg
            near_lat = min(max(lat, south), south + tile_deg)
            near_lon = min(max(lon, west), west + tile_deg)
            if meters(lat, lon, near_lat, near_lon) <= radius_m:
                out.append((row, col))
    return out


def tile_query_radius_m(lat: float, tile_deg: float = TILE_DEG) -> float:
    """A radius that still covers a tile after the client shrinks its
    primary viewport to three quarters."""
    half = tile_deg / 2
    return math.hypot(half * M_PER_DEG_LAT, half * m_per_deg_lon(lat)) / PRIMARY_VIEWPORT


class Votes:
    """The confirmations this plugin collected, kept in memory.

    Waze itself gets nothing from them: they raise the confirmation count and
    the confidence the plugin reports, and enough "not there" votes hide the
    alert.

    Hiding an alert is the one destructive thing a caller can ask for, and
    these alerts are drawn on a map people drive by, so who is allowed to ask
    matters. A vote used to be counted once per ``reporter`` string taken
    straight from the request body. On a listing that advertises no
    authentication that is not an identity, it is a field: three requests
    with three invented strings hid any alert the plugin served.

    So a vote is counted once per VOTER, and a voter is:

    * ``t:<reporter>`` when the caller presented the configured confirm
      token. A mediated backend forwarding many people's votes is one
      address but many reporters, and its reporter strings are pseudonyms it
      derived, so they can be trusted once the caller has been.
    * ``a:<address>`` otherwise. An unauthenticated caller counts once per
      address however many strings it invents, so hiding an alert costs
      three distinct addresses rather than three lines of shell.

    The two namespaces never collide, so an unauthenticated caller cannot
    dress its votes up as trusted ones.

    The trust split is not only about hiding. An "up" vote raises the
    published ``n_confirmations``, and a caller downstream may read a well
    confirmed closure as a reason to send every driver somewhere else, so a
    forgeable count is a way to close a road rather than a cosmetic one.
    Untrusted votes therefore count towards hiding and nothing else: they
    can weaken what this plugin says, never strengthen it, and never extend
    an alert's life.
    """

    def __init__(self, now: Callable[[], float] | None = None) -> None:
        self._now = now or time.time
        self._up: dict[str, set[str]] = {}
        self._gone: dict[str, set[str]] = {}
        self._confirmed_at: dict[str, float] = {}
        self._touched: dict[str, float] = {}

    @staticmethod
    def voter(reporter: str, address: str, *, trusted: bool) -> str:
        """Who a vote counts as. See the class docstring for why."""
        return f"t:{reporter}" if trusted else f"a:{address}"

    def add(self, alert_id: str, vote: str, voter: str) -> None:
        now = self._now()
        self._prune(now)
        self._touched[alert_id] = now
        bucket = self._up if vote == "up" else self._gone
        if voter in bucket.setdefault(alert_id, set()):
            return
        bucket[alert_id].add(voter)
        if vote == "up" and voter.startswith("t:"):
            self._confirmed_at[alert_id] = now

    def ups(self, alert_id: str) -> int:
        """Confirmations this plugin will put its name to.

        Only trusted voters count. An "up" vote does not merely decorate a
        record: the count is published as ``n_confirmations``, and a caller
        downstream may treat a well confirmed alert as a reason to act, so an
        anonymous caller able to run that number up can manufacture an alert
        that everybody believes. Anonymous input may weaken this plugin's
        confidence, and at enough distinct addresses hide an alert, but it
        may never strengthen one.
        """
        return sum(1 for voter in self._up.get(alert_id, ()) if voter.startswith("t:"))

    def confirmed_at(self, alert_id: str) -> float | None:
        """When a trusted voter last confirmed it.

        Trusted for the same reason, and one more: an alert's life is
        anchored on this, so an untrusted caller that could move it would
        keep a cleared report on the map for as long as it kept voting.
        """
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
                 tile_deg: float = TILE_DEG, max_tiles: int = MAX_TILES,
                 now: Callable[[], float] | None = None,
                 wall_clock: Callable[[], float] | None = None) -> None:
        self.source = source
        self.bbox = bbox
        self.refresh_s = refresh_s
        self.tile_deg = tile_deg
        self.max_tiles = max(1, max_tiles)
        self._now = now or time.monotonic
        self._wall = wall_clock or time.time
        self.votes = Votes(now=self._wall)
        self.confirmations = ConfirmTracker(now=self._wall)
        # tile -> when it was last asked about, and when it was last fetched.
        self._asks: dict[tuple[int, int], float] = {}
        self._tile_ok: dict[tuple[int, int], float] = {}
        self._lock = asyncio.Lock()

    # -------------------------------------------------------------- asks

    def want(self, lat: float, lon: float, radius_m: float = 0.0) -> None:
        """Remember that someone asked about a disc. Every tile it touches
        joins the rotation, and asking again is what keeps it there."""
        now = self._now()
        for tile in tiles_for_disc(lat, lon, radius_m, self.tile_deg):
            self._asks[tile] = now
        if len(self._asks) > self.max_tiles:
            # The tiles nobody has asked about for longest go first.
            for tile, _ in sorted(self._asks.items(), key=lambda kv: kv[1])[
                    : len(self._asks) - self.max_tiles]:
                self._asks.pop(tile, None)
                self._tile_ok.pop(tile, None)

    def wanted_tiles(self) -> list[tuple[int, int]]:
        """Every tile asked about inside the window, stalest fetch first
        and most recently asked within that."""
        now = self._now()
        for tile, asked in list(self._asks.items()):
            if now - asked > WANTED_TTL_S:
                self._asks.pop(tile, None)
                self._tile_ok.pop(tile, None)
        return sorted(self._asks, key=lambda t: (self._tile_ok.get(t, 0.0), -self._asks[t]))

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
        """Refresh the stalest wanted tile that is due. True when one was
        fetched."""
        tiles = self.wanted_tiles()
        if not tiles or self.source.backoff_remaining_s() > 0:
            return False
        # The stalest tile goes first, and no tile is fetched more often
        # than once per refresh window. When there are more wanted tiles
        # than the window fits, the stalest one is always overdue and the
        # loop simply keeps going round.
        tile = tiles[0]
        if self._now() - self._tile_ok.get(tile, 0.0) < self.refresh_s:
            return False
        lat, lon = tile_center(tile, self.tile_deg)
        async with self._lock:
            before = len(self.source.cache)
            try:
                count = await self.source.refresh(lat, lon, tile_query_radius_m(lat, self.tile_deg))
                self._tile_ok[tile] = self._now()
                log.info("tile %d,%d (%.2f,%.2f) refreshed: %d new, %d cached, %d tiles wanted",
                         tile[0], tile[1], lat, lon, count - before, count, len(self._asks))
            except Exception as exc:  # noqa: BLE001 - one bad tile never stops the rest
                self.source.note_failure(exc)
                log.warning("tile %d,%d (%.2f,%.2f) failed: %s: %s",
                            tile[0], tile[1], lat, lon, type(exc).__name__, exc)
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
        now = self._now()
        tiles = self.wanted_tiles()
        ages = [now - self._tile_ok[t] for t in tiles if t in self._tile_ok]
        return {
            "alerts": len(self.source.cache),
            "served": len(self.records()),
            "tiles_wanted": len(tiles),
            "tiles_fetched": len(ages),
            "tiles_fresh": sum(1 for a in ages if a <= self.refresh_s),
            # How long ago the most neglected wanted tile was fetched: the
            # lap time, measured rather than estimated.
            "stalest_s": round(max(ages)) if ages else None,
            "fresh": self.fresh,
            "registered": self.source.registered,
            "backoff_s": round(self.source.backoff_remaining_s()),
            "last_error": self.source.last_error,
            "as_of": self.as_of,
        }


def _iso(epoch_s: float) -> str:
    return datetime.fromtimestamp(epoch_s, UTC).isoformat()
