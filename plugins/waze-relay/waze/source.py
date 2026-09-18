"""The account, the session and the merged alert cache in one place.

Ported from ``WazeProtocolSource.java``, minus the parts that only make sense
on a phone (the foreground refresh thread, the cache-moved-too-far discard,
Android preferences). What is kept is the part that keeps the relay polite:
one anonymous account reused for as long as Waze accepts it, an exponential
backoff after a rejection, a hard cap on how many accounts a day may be
minted, and the shrinking-box query series that stops the server from
thinning out the smaller alerts.

State (the account and the device profile) is held in memory and, when
``state_path`` is set, mirrored to a JSON file so a restart does not mint a
new account.
"""

from __future__ import annotations

import contextlib
import json
import logging
import time
from collections.abc import Callable
from pathlib import Path

import httpx

from .cache import AlertCache, AlertQueryResult
from .constants import MAX_ACCOUNTS_PER_DAY, MAX_CONSECUTIVE_REJECTIONS
from .device import DeviceIdentity
from .errors import AccountRejected, SessionExpired
from .geoboxes import shrink, shrinking_boxes
from .rt_codec import parse_alerts, parse_removed_alert_ids
from .session import Credentials, WazeSession

log = logging.getLogger("waze_relay.waze")

BACKOFF_BASE_S = 30.0
BACKOFF_MAX_S = 600.0
GENERIC_FAIL_BACKOFF_S = 15.0
DAY_S = 24 * 3600.0
QUERY_BUDGET_S = 10.0
SHRINK_STEPS = 5
PRIMARY_VIEWPORT = 0.75


class RegistrationBudget:
    """How many anonymous accounts may be minted in a rolling day.

    The upstream caps anonymous accounts per day, and that cap is on whoever
    is doing the minting, not on each object that does it. So one of these is
    shared by every session in a process: a relay holding several user
    sessions must not hand each of them its own allowance.
    """

    def __init__(self, limit: int = MAX_ACCOUNTS_PER_DAY) -> None:
        self.limit = limit
        self.minted = 0
        self.window_start = 0.0

    def allowed(self, now: float) -> bool:
        return now - self.window_start > DAY_S or self.minted < self.limit

    def record(self, now: float) -> None:
        if now - self.window_start > DAY_S:
            self.window_start = now
            self.minted = 0
        self.minted += 1


class WazeSource:
    """One account, one session, one merged cache."""

    def __init__(self, client: httpx.AsyncClient, *, region: str = "na",
                 shrink_steps: int = SHRINK_STEPS, query_budget_s: float = QUERY_BUDGET_S,
                 state_path: str | None = None,
                 credentials: Credentials | None = None,
                 device: DeviceIdentity | None = None,
                 budget: RegistrationBudget | None = None,
                 now: Callable[[], float] | None = None,
                 wall_clock: Callable[[], float] | None = None) -> None:
        self._client = client
        self.region = region
        self.shrink_steps = shrink_steps
        self.query_budget_s = query_budget_s
        self._state_path = Path(state_path) if state_path else None
        self._now = now or time.monotonic
        self._wall = wall_clock or time.time
        self.cache = AlertCache(now=self._wall)
        self._session: WazeSession | None = None
        # An account handed in by the pool. Two sessions cannot share one,
        # because the upstream logs the other out, so the pool only ever
        # lends an account that nothing else is holding.
        self._credentials: Credentials | None = credentials
        self._device: DeviceIdentity | None = device
        self._consecutive_rejections = 0
        self._backoff_until = 0.0
        self.budget = budget or RegistrationBudget()
        self.last_ok: float | None = None
        self.last_error: str | None = None
        self._load_state()

    # ------------------------------------------------------------- state

    @property
    def registered(self) -> bool:
        return self._credentials is not None

    def backoff_remaining_s(self) -> float:
        return max(0.0, self._backoff_until - self._now())

    def account(self) -> tuple[Credentials | None, DeviceIdentity | None]:
        """The account and device this source holds, for the pool to lend on
        to the next session once this one retires."""
        return self._credentials, self._device

    def _load_state(self) -> None:
        if self._state_path is None or not self._state_path.exists():
            return
        if self._credentials is not None:
            return                      # an account was handed in; keep it
        with contextlib.suppress(Exception):
            state = json.loads(self._state_path.read_text("utf-8"))
            if state.get("community") and state.get("secret"):
                self._credentials = Credentials(state["community"], state["secret"])
            if state.get("device"):
                self._device = DeviceIdentity.from_dict(state["device"])
            self.budget.minted = int(state.get("registrations", 0))
            self.budget.window_start = float(state.get("registration_window_start", 0.0))

    def _save_state(self) -> None:
        if self._state_path is None:
            return
        with contextlib.suppress(Exception):
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(json.dumps({
                "community": self._credentials.community if self._credentials else None,
                "secret": self._credentials.secret if self._credentials else None,
                "device": self._device.as_dict() if self._device else None,
                "registrations": self.budget.minted,
                "registration_window_start": self.budget.window_start,
            }), "utf-8")

    # ------------------------------------------------------------ refresh

    async def refresh(self, lat: float, lon: float, radius_m: float) -> int:
        """Prepare the session, query the shrinking box series around the
        point, and merge every answer into the cache. Returns the number of
        alerts cached."""
        try:
            await self._query_area(self._ensure_session(), lat, lon, radius_m)
        except AccountRejected as exc:
            await self._handle_account_rejected(exc, lat, lon, radius_m)
        except SessionExpired as exc:
            log.warning("session expired, logging in again: %s", exc)
            if self._session is not None:
                self._session.invalidate_session()
            await self._query_area(self._ensure_session(), lat, lon, radius_m)
        # Reached only on a fully successful refresh.
        self._consecutive_rejections = 0
        self._backoff_until = 0.0
        self.last_ok = self._now()
        self.last_error = None
        return len(self.cache)

    def note_failure(self, exc: BaseException) -> None:
        """Record a failed refresh and hold off long enough that a flapping
        network or a server outage is not retried at poll cadence."""
        self.last_error = f"{type(exc).__name__}: {str(exc)[:160]}"
        now = self._now()
        if self._backoff_until <= now:
            self._backoff_until = now + GENERIC_FAIL_BACKOFF_S

    async def submit_report(self, *, lat: float, lon: float, heading_deg: float,
                            member: int, subtype_number: int):
        """Send one report to Waze over the shared account, logging in again
        once when the session turns out to be stale."""
        session = self._ensure_session()
        try:
            result = await session.submit_report(
                lat=lat, lon=lon, heading_deg=heading_deg,
                member=member, subtype_number=subtype_number)
        except SessionExpired:
            session.invalidate_session()
            result = await session.submit_report(
                lat=lat, lon=lon, heading_deg=heading_deg,
                member=member, subtype_number=subtype_number)
        self._adopt(session)
        return result

    def _adopt(self, session: WazeSession) -> None:
        """Keep an account the session just minted, so the next start does
        not register another one."""
        if session.credentials is not None and session.credentials != self._credentials:
            self._credentials = session.credentials
            self._device = session.device
            self._save_state()

    def _ensure_session(self) -> WazeSession:
        if self._session is None:
            self._device = self._device or DeviceIdentity.random()
            self._session = WazeSession(self.region, self._client, device=self._device,
                                        credentials=self._credentials, now=self._now)
        return self._session

    async def _query_area(self, session: WazeSession, lat: float, lon: float,
                          radius_m: float) -> None:
        session_before = session.server_session_id
        # Non-null only when a fresh login ran the handshake: its MapDisplayed
        # box is a real viewport query whose alerts the server will not send
        # again this session, so it is merged rather than discarded.
        handshake = await session.prepare_for_area(lat, lon)
        # The account exists now, so save it before the box loop can fail and
        # lose a freshly minted one.
        self._adopt(session)

        # A new server session re-sends every active alert for the area but
        # sends no removal for the ones that cleared while we were logged out,
        # so the old cache has to go. That is deferred until the first box
        # query succeeds: if the loop fails right after a re-login, the old
        # cache keeps serving instead of blanking out.
        session_changed = session.server_session_id != session_before
        cleared = False
        deadline = self._now() + self.query_budget_s
        for box in shrinking_boxes(lon, lat, radius_m, self.shrink_steps):
            if self._now() >= deadline:
                break
            elements = await session.query_box(shrink(box, PRIMARY_VIEWPORT))
            if session_changed and not cleared:
                self.cache.clear()
                cleared = True
            if handshake is not None:
                self.cache.submit(AlertQueryResult(parse_alerts(handshake),
                                                   parse_removed_alert_ids(handshake)))
                handshake = None
            self.cache.submit(AlertQueryResult(parse_alerts(elements),
                                               parse_removed_alert_ids(elements)))

    async def _handle_account_rejected(self, exc: Exception, lat: float, lon: float,
                                       radius_m: float) -> None:
        """Replace a rejected account, but only while under the per-day cap,
        so a persistent rejection cannot burn the quota."""
        if self._registration_window_rolled_over():
            self._consecutive_rejections = 0
        self._consecutive_rejections += 1
        self._set_backoff()
        if (not self._can_register_today()
                or self._consecutive_rejections > MAX_CONSECUTIVE_REJECTIONS):
            log.warning("account rejected and the registration cap is reached (%s in a row): %s",
                        self._consecutive_rejections, exc)
            raise exc
        log.warning("account rejected, registering again (attempt %s): %s",
                    self._consecutive_rejections, exc)
        self._session = None
        self._credentials = None
        self._record_registration()
        await self._query_area(self._ensure_session(), lat, lon, radius_m)

    def _set_backoff(self) -> None:
        step = min(max(self._consecutive_rejections, 1), 5)
        delay = min(BACKOFF_MAX_S, BACKOFF_BASE_S * (1 << (step - 1)))
        self._backoff_until = self._now() + delay
        log.warning("holding off for %ss", int(delay))

    def _registration_window_rolled_over(self) -> bool:
        return self._wall() - self.budget.window_start > DAY_S

    def _can_register_today(self) -> bool:
        return self.budget.allowed(self._wall())

    def _record_registration(self) -> None:
        self.budget.record(self._wall())
        self._save_state()

    # ------------------------------------------------------------ reading

    def snapshot(self) -> list:
        return self.cache.snapshot()
