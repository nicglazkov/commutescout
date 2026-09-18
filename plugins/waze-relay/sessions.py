"""Per-user upstream sessions: one signed-in person, one stream.

The shared relay holds one upstream session for everybody, which is right for
the web and for signed-out phones. A signed-in phone can do better, because
the upstream protocol sends each alert once per SESSION: with a session of its
own, a phone gets a stream shaped by where that phone is, and the alerts
follow the driver instead of arriving mixed with everyone else's.

This is the sabre-plus model moved one step in from the device, and the step
costs something worth naming. sabre-plus runs on the phone, with the phone's
own address and its own account, so its traffic looks like one more phone.
Run the same thing here and every user's session leaves from ONE address on
ONE container. An account per user from a single address is how a single
address stops being served, and it would take the shared relay with it.

So the sessions are pooled, not per-user-forever:

* At most ``max_concurrent`` sessions exist at once. A signed-in person who
  arrives when they are all taken is served by the shared relay instead:
  correct data, just not a private stream.
* Accounts are lent out and handed back, never minted per person, and a
  single day's minting budget is shared with the relay.
* An idle session is retired and its account returned to the pool.

Two sessions cannot share one account: the upstream login logs the other
device out, so concurrency is a hard limit rather than a tuning knob.

Refresh behaviour is ported from ``WazeProtocolSource``: the answer is served
from the caller's own cache at once and never waits on the upstream, a
refresh is triggered in the background when the cache is stale or the person
has moved, a long jump throws the old city away, and a cache nobody could
refresh for ten minutes stops being served at all.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
from store import MAX_ALERTS, meters
from waze.device import DeviceIdentity
from waze.session import Credentials
from waze.source import RegistrationBudget, WazeSource

log = logging.getLogger("waze_relay.sessions")

CACHE_TTL_S = 12.0            # refresh once the caller's cache is older
REFRESH_MOVE_KM = 4.0         # ...or once they have moved this far
CACHE_DISCARD_KM = 25.0       # a jump this long is a new place, not a drive
CACHE_MAX_SERVE_AGE_S = 600.0  # a cache nobody could refresh stops being served
MIN_RADIUS_M = 8_000
IDLE_S = 600.0
MAX_CONCURRENT = 5
SNAP_DP = 2                   # about 1.1 km, the same rounding as telemetry


def snap(value: float) -> float:
    """A position rounded to the grid the upstream is asked about. Callers
    are told to send a snapped tile centre; this makes sure of it."""
    return round(value, SNAP_DP)


class AccountPool:
    """Anonymous accounts, lent out one at a time.

    An account in the pool is one no session is holding. Handing the same
    account to two sessions would log the first one out, so the pool is the
    thing that makes the concurrency limit real.
    """

    def __init__(self, budget: RegistrationBudget | None = None) -> None:
        self.budget = budget or RegistrationBudget()
        self._free: list[tuple[Credentials, DeviceIdentity]] = []

    def take(self) -> tuple[Credentials | None, DeviceIdentity | None]:
        """A free account, or nothing, in which case the session mints one
        against the shared daily budget."""
        return self._free.pop() if self._free else (None, None)

    def give_back(self, credentials, device) -> None:
        if credentials is not None and device is not None:
            self._free.append((credentials, device))

    @property
    def free(self) -> int:
        return len(self._free)


class UserSession:
    """One signed-in person's upstream session and cache."""

    def __init__(self, key: str, source: WazeSource, client: httpx.AsyncClient, *,
                 now: Callable[[], float] | None = None) -> None:
        self.key = key
        self.source = source
        self.client = client
        self._now = now or time.monotonic
        self.created = self._now()
        self.last_seen = self._now()
        self.cache_time = 0.0
        self.cache_wall = 0.0
        self.cache_lat = 0.0
        self.cache_lon = 0.0
        self._refreshing = False
        self._task: asyncio.Task | None = None

    @property
    def as_of(self) -> str:
        """When this person's own data was last refreshed."""
        stamp = self.cache_wall or time.time()
        return datetime.fromtimestamp(stamp, UTC).isoformat()

    def touch(self) -> None:
        self.last_seen = self._now()

    def idle_s(self) -> float:
        return self._now() - self.last_seen

    def moved_km(self, lat: float, lon: float) -> float:
        if self.cache_time == 0.0:
            return 0.0
        return meters(lat, lon, self.cache_lat, self.cache_lon) / 1000.0

    def servable(self, lat: float, lon: float) -> bool:
        """Whether this cache may still be shown to the person it belongs to."""
        if self.cache_time == 0.0:
            return False
        if self._now() - self.cache_time > CACHE_MAX_SERVE_AGE_S:
            return False
        return self.moved_km(lat, lon) <= CACHE_DISCARD_KM

    def trigger_refresh_if_stale(self, lat: float, lon: float, radius_m: float) -> bool:
        """Start a background refresh when one is due. True when one started.

        Never awaited by the caller: an upstream query long-polls for up to
        ten and a half seconds and a person waiting on a map will not wear
        that.
        """
        if self.source.backoff_remaining_s() > 0 or self._refreshing:
            return False
        moved = self.moved_km(lat, lon) > REFRESH_MOVE_KM
        stale = (self.cache_time == 0.0
                 or self._now() - self.cache_time > CACHE_TTL_S
                 or moved)
        if not stale:
            return False
        discard = self.moved_km(lat, lon) > CACHE_DISCARD_KM
        self._refreshing = True
        self._task = asyncio.create_task(
            self._refresh(lat, lon, max(radius_m, MIN_RADIUS_M), discard))
        return True

    async def _refresh(self, lat: float, lon: float, radius_m: float,
                       discard: bool) -> None:
        try:
            if discard:
                # They are somewhere else now. Showing the old city's alerts
                # would be worse than showing none.
                self.source.cache.clear()
            await self.source.refresh(lat, lon, radius_m)
            self.cache_time = self._now()
            self.cache_wall = time.time()
            self.cache_lat, self.cache_lon = lat, lon
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - one session never breaks the rest
            self.source.note_failure(exc)
            log.warning("user session refresh failed: %s: %s", type(exc).__name__, exc)
        finally:
            self._refreshing = False

    def alerts(self, lat: float, lon: float, radius_m: float, to_record) -> list[dict]:
        """This person's alerts near a point, nearest first."""
        if not self.servable(lat, lon):
            return []
        now = time.time()
        hits = []
        for alert in self.source.snapshot():
            distance = meters(lat, lon, alert.lat, alert.lon)
            if distance > radius_m:
                continue
            record = to_record(alert, now)
            if record is not None:
                hits.append((distance, record))
        hits.sort(key=lambda pair: pair[0])
        return [record for _, record in hits[:MAX_ALERTS]]

    async def close(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task
        with contextlib.suppress(Exception):
            await self.client.aclose()


class UserSessions:
    """The registry: who has a session, and who has to wait."""

    def __init__(self, *, max_concurrent: int = MAX_CONCURRENT, idle_s: float = IDLE_S,
                 budget: RegistrationBudget | None = None,
                 shrink_steps: int = 2, query_budget_s: float = 10.0,
                 client_factory: Callable[[], httpx.AsyncClient] | None = None,
                 now: Callable[[], float] | None = None) -> None:
        self.max_concurrent = max(1, max_concurrent)
        self.idle_s = idle_s
        self.pool = AccountPool(budget)
        self.shrink_steps = shrink_steps
        self.query_budget_s = query_budget_s
        self._client_factory = client_factory or (lambda: httpx.AsyncClient(timeout=30.0))
        self._now = now or time.monotonic
        self._sessions: dict[str, UserSession] = {}

    def __len__(self) -> int:
        return len(self._sessions)

    async def get(self, key: str) -> UserSession | None:
        """This person's session, made if they have none and there is room.
        None means the relay is full and the caller falls back to the shared
        feed."""
        await self.expire_idle()
        session = self._sessions.get(key)
        if session is not None:
            session.touch()
            return session
        if len(self._sessions) >= self.max_concurrent:
            return None
        credentials, device = self.pool.take()
        client = self._client_factory()
        source = WazeSource(client, shrink_steps=self.shrink_steps,
                            query_budget_s=self.query_budget_s,
                            credentials=credentials, device=device,
                            budget=self.pool.budget, now=self._now)
        session = UserSession(key, source, client, now=self._now)
        self._sessions[key] = session
        log.info("user session opened, %s of %s in use",
                 len(self._sessions), self.max_concurrent)
        return session

    async def expire_idle(self) -> list[str]:
        """Retire sessions nobody has asked for lately, handing their
        accounts back so the next person gets one without minting."""
        gone = []
        for key, session in list(self._sessions.items()):
            if session.idle_s() < self.idle_s:
                continue
            self._sessions.pop(key, None)
            self.pool.give_back(*session.source.account())
            await session.close()
            gone.append(key)
        if gone:
            log.info("retired %s idle user session(s), %s accounts free",
                     len(gone), self.pool.free)
        return gone

    async def close_all(self) -> None:
        for key, session in list(self._sessions.items()):
            self._sessions.pop(key, None)
            await session.close()

    def status(self) -> dict:
        """Counts only. Nothing here identifies anybody."""
        return {
            "in_use": len(self._sessions),
            "max_concurrent": self.max_concurrent,
            "accounts_free": self.pool.free,
            "accounts_minted_today": self.pool.budget.minted,
            "idle_s": self.idle_s,
        }
