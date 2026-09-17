"""One Waze RT session: register an anonymous account, log in, query, report.

Ported from ``WazeSession.java``. The sequence, the headers, the endpoints and
the error classification are the ones the Java version sends; the only change
is that the calls are awaited instead of blocking a worker thread.

No pre-shared credentials exist anywhere: ``register`` asks Waze itself for a
username and password. Credentials and the device profile are kept so the
relay does not register again on every refresh, because anonymous accounts are
capped per day.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from . import proto, report_codec, rt_codec, tiles, wire
from .constants import (
    APP_VERSION,
    M_PER_DEG_LAT,
    PATH_COMMAND,
    PATH_LOGIN,
    PATH_STATIC,
    SESSION_IDLE_TIMEOUT_S,
    WAIT_TIMEOUT_COMMAND,
    WAIT_TIMEOUT_LOGIN,
    m_per_deg_lon,
    region_for,
    rt_host,
    tile_host,
)
from .device import DeviceIdentity
from .errors import AccountRejected, SessionExpired, WazeOperationError
from .report_codec import ReportResult
from .roadgeo import LatLon, find_matching_segment

log = logging.getLogger("waze_relay.waze")

OCTET = "binary/octet-stream"
SIMULATED_SPEED_MS = 13.4
RETRIES = 3


@dataclass(frozen=True)
class Credentials:
    """An anonymous account minted by the register endpoint: ``community``
    is the username and ``secret`` the password."""

    community: str
    secret: str


@dataclass(frozen=True)
class SessionInfo:
    """Authenticated state returned by a successful login."""

    server_session_id: int
    secret_key: str
    global_user_id: str


class WazeSession:
    """Single-slot and serialized: the caller holds one at a time."""

    def __init__(self, region: str, client: httpx.AsyncClient, *,
                 device: DeviceIdentity | None = None,
                 credentials: Credentials | None = None,
                 now: Callable[[], float] | None = None) -> None:
        self.region = region
        self.device = device or DeviceIdentity.random()
        self.credentials = credentials
        self._client = client
        self._now = now or time.monotonic
        self._session: SessionInfo | None = None
        self._seq_count = 1
        self._last_request = 0.0
        self._handshaked_session_id = 0

    @property
    def server_session_id(self) -> int:
        """0 when not logged in, so the caller can spot a re-login."""
        return self._session.server_session_id if self._session else 0

    def invalidate_session(self) -> None:
        """Drop the login but keep the account, so the next call logs in
        again instead of registering a new one."""
        self._session = None

    # ------------------------------------------------------------ errors

    @staticmethod
    def check_errors(elements: list[dict[int, list]]) -> None:
        """Raise for the in-band errors the server returns with an HTTP 200.

        Without this a server that invalidates the session but answers 200
        looks like success, and the session zombies: it never idles out and
        no alert is ever merged again.
        """
        for el in elements:
            error = wire.sub(el, proto.EL_ERROR)
            if error is not None:
                code = wire.first(error, 10101, 0)
                description = wire.text(error, 10102)
                lowered = description.lower()
                if any(s in lowered for s in ("relogin", "unknown userid",
                                              "secretkey missing", "secret key missing")):
                    raise SessionExpired(f"server error: {description}")
                if 400 <= code < 500:
                    raise AccountRejected(f"server error {code}: {description}")
                if code >= 500:
                    raise WazeOperationError(f"server error {code}: {description}")
                # Informational or unknown, including the proto default code
                # 0: a normal batch can carry one, so it must not fail the
                # whole refresh.
                log.warning("ignoring non-fatal server error %s: %s", code, description)
            login_error = wire.sub(el, proto.EL_LOGIN_ERROR)
            if login_error is not None:
                _raise_for_login_error(wire.first(login_error, 2, 0))

    # -------------------------------------------------------------- http

    def _url(self, path: str) -> str:
        return f"https://{rt_host(self.region)}{path}"

    def _next_seq(self) -> str:
        seq = self._seq_count
        self._seq_count += 1
        return str(seq)

    def _session_valid(self) -> bool:
        return (self._session is not None
                and self._now() - self._last_request < SESSION_IDLE_TIMEOUT_S)

    async def _post(self, url: str, body: str, headers: dict) -> httpx.Response:
        """POST with the couple of retries the Java client does for transient
        network failures."""
        last: Exception | None = None
        for attempt in range(1, RETRIES + 1):
            try:
                return await self._client.post(
                    url, content=body.encode("utf-8"),
                    headers={"Content-Type": OCTET, **headers})
            except httpx.HTTPError as exc:
                last = exc
                if attempt == RETRIES:
                    break
                await asyncio.sleep(0.4 * attempt)
        raise WazeOperationError(f"{type(last).__name__}: {last}")

    # ---------------------------------------------------------- register

    async def register(self, lon: float, lat: float) -> None:
        body = (rt_codec.build_client_info_line(self.device, lon, lat)
                + "\n" + rt_codec.build_register_line())
        headers = {
            "User-Agent": APP_VERSION,           # bare "5.17.1.0"
            "x-waze-network-version": "3",
            "sequence-number": self._next_seq(),
        }
        response = await self._post(self._url(PATH_STATIC), body, headers)
        if response.status_code >= 400:
            raise WazeOperationError(f"register HTTP {response.status_code}")
        if not response.content:
            raise WazeOperationError("empty register response")
        elements = proto.elements(response.content)
        self.check_errors(elements)
        for el in elements:
            successful = wire.sub(el, proto.EL_REGISTER_SUCCESSFUL)
            if successful is None:
                continue
            username = wire.text(successful, 1)
            password = wire.text(successful, 2)
            if not username:
                raise WazeOperationError("empty community from register")
            if not password:
                raise WazeOperationError("empty secret from register")
            self.credentials = Credentials(username, password)
            log.info("registered an anonymous account")
            return
        raise WazeOperationError(
            f"register: no RegisterSuccessful element ({len(response.content)}B)")

    # ------------------------------------------------------------- login

    async def login(self, lon: float, lat: float) -> None:
        if self.credentials is None:
            raise WazeOperationError("login before register")
        self._client.cookies.clear()
        body = "\n".join([
            rt_codec.build_client_info_line(self.device, lon, lat),
            rt_codec.build_login_line(self.credentials.community, self.credentials.secret),
            rt_codec.build_ads_line(),
        ])
        headers = {
            "User-Agent": f"waze/{APP_VERSION}",   # login uses the "waze/" prefix
            "cache-control": "no-cache",
            "sequence-number": self._next_seq(),
            "x-waze-network-version": "3",
            "x-waze-wait-timeout": WAIT_TIMEOUT_LOGIN,
        }
        response = await self._post(self._url(PATH_LOGIN), body, headers)
        # A 4xx means Waze no longer accepts these credentials (anonymous
        # accounts get purged), so the caller replaces the account instead of
        # failing forever.
        if 400 <= response.status_code < 500:
            raise AccountRejected(f"login HTTP {response.status_code}")
        if response.status_code >= 500:
            raise WazeOperationError(f"login HTTP {response.status_code}")
        if not response.content:
            raise WazeOperationError("empty login response")
        elements = proto.elements(response.content)
        self.check_errors(elements)
        for el in elements:
            login_response = wire.sub(el, proto.EL_LOGIN_RESPONSE)
            if login_response is None:
                continue
            # A failure can arrive nested in the LoginResponse as well as at
            # the top level; classify it here too, so a transient
            # INTERNAL_ISSUES does not needlessly re-register.
            nested_error = wire.sub(login_response, 2)
            if nested_error is not None:
                _raise_for_login_error(wire.first(nested_error, 2, 0))
            success = wire.sub(login_response, 1)
            if success is None:
                continue
            server_session_id = wire.as_int64(wire.first(success, 1, 0))
            secret_key = wire.text(success, 3)
            if server_session_id == 0:
                raise WazeOperationError("zero serverSessionId")
            if not secret_key:
                raise WazeOperationError("empty secretKey")
            self._session = SessionInfo(server_session_id, secret_key, wire.text(success, 2))
            self._seq_count = 2
            self._last_request = self._now()
            log.info("login ok")
            return
        raise AccountRejected(f"login: no LoginSuccess element ({len(response.content)}B)")

    # -------------------------------------------------------- command

    async def command(self, payload: str) -> list[dict[int, list]]:
        if self._session is None:
            raise SessionExpired("command before login")
        headers = {
            "User-Agent": APP_VERSION,           # bare "5.17.1.0"
            "cache-control": "no-cache",
            "sequence-number": self._next_seq(),
            "x-waze-network-version": "3",
            "x-waze-wait-timeout": WAIT_TIMEOUT_COMMAND,
            "uid": rt_codec.build_uid_header(self._session.server_session_id,
                                             self._session.secret_key),
        }
        response = await self._post(self._url(PATH_COMMAND), payload, headers)
        # A 4xx on a command means the server no longer honors this session.
        if 400 <= response.status_code < 500:
            self._session = None
            raise SessionExpired(f"command HTTP {response.status_code}")
        if response.status_code >= 500:
            raise WazeOperationError(f"command HTTP {response.status_code}")
        if not response.content:
            raise WazeOperationError("empty command response")
        elements = proto.elements(response.content)
        # Check for an in-band error before marking the session healthy, so a
        # zombie session (200 plus "please relogin") cannot keep itself alive.
        try:
            self.check_errors(elements)
        except SessionExpired:
            self._session = None
            raise
        self._last_request = self._now()
        return elements

    async def ensure_ready(self, lon: float, lat: float) -> None:
        """Register when there is no account, log in when there is no valid
        session."""
        if self.credentials is None:
            await self.register(lon, lat)
        if not self._session_valid():
            await self.login(lon, lat)

    async def prepare_for_area(self, lat: float, lon: float) -> list[dict[int, list]] | None:
        """Register, log in, and run the handshake once per login.

        The handshake's MapDisplayed box is a real viewport query and the
        server sends each alert once per session, so its answer is returned
        for the caller to merge rather than discarded. None means the session
        was already handshaken and no request went out.
        """
        await self.ensure_ready(lon, lat)
        if self._session is not None and self._session.server_session_id == \
                self._handshaked_session_id:
            return None
        elements = await self.command(rt_codec.handshake_payload(lon, lat))
        self._handshaked_session_id = self.server_session_id
        return elements

    async def query_box(self, bbox: list[float]) -> list[dict[int, list]]:
        """One MapDisplayed query for ``[lon_min, lat_min, lon_max, lat_max]``.
        The batch carries both the added alerts and the removed ids."""
        return await self.command(
            rt_codec.map_displayed_command(bbox[0], bbox[1], bbox[2], bbox[3]))

    # --------------------------------------------------------- reporting

    async def fetch_tile_segments(self, lat: float, lon: float) -> list:
        """The road graph around a point, for the report snap.

        Best effort: no session, an HTTP error, an empty body or a decode
        failure all return an empty list, so a failed snap degrades to a
        position-only report instead of losing the report.
        """
        if self._session is None:
            log.warning("fetch_tile_segments: no live session")
            return []
        try:
            url = tiles.build_tile_url(
                tile_host(region_for(lat, lon)), self._session.server_session_id,
                self._session.secret_key, tiles.coord_to_tile_id(lon, lat))
            response = await self._client.get(url, headers={
                "User-Agent": APP_VERSION,
                "if-modified-since": "Thu, 01 Jan 1970 00:00:00 GMT",
            })
            if response.status_code >= 400 or not response.content:
                log.warning("fetch_tile_segments: tile GET HTTP %s (%sB)",
                            response.status_code, len(response.content))
                return []
            return tiles.parse(response.content)
        except Exception as exc:  # noqa: BLE001 - a snap failure never loses the report
            log.warning("fetch_tile_segments failed: %s: %s", type(exc).__name__, exc)
            return []

    async def submit_report(self, *, lat: float, lon: float, heading_deg: float,
                            member: int, subtype_number: int, altitude_m: float = 0.0,
                            is_opposite: bool = False, time_delta_s: int = 0,
                            now_ms: int | None = None) -> ReportResult:
        """Submit a report through the same command sequence the Waze client
        uses: handshake, a first SeeMe plus Location plus MapDisplayed, a tile
        fetch and nearest-segment snap, an At update carrying the directional
        nodes, a short simulated-driving sequence when a segment matched, the
        report itself, and a trailing SeeMe. Only the report's answer is read;
        the rest are best effort, as they are in the client."""
        now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
        await self.prepare_for_area(lat, lon)

        box_a = rt_codec.circle_to_box(lon, lat)
        await self.command(
            rt_codec.see_me_command(1) + "\n" + rt_codec.location_command(lon, lat)
            + "\n" + rt_codec.map_displayed_command(*box_a))

        segments = await self.fetch_tile_segments(lat, lon)
        heading = rt_codec.normalize_angle_360(heading_deg)
        match = find_matching_segment(LatLon(lat, lon), heading_deg, segments, 15.0, 50.0)
        from_node = match.from_node_directional if match else -1
        to_node = match.to_node_directional if match else -1
        log.info("report snap: %s (%s candidates)",
                 "matched" if match else "no road match", len(segments))

        box_b = rt_codec.circle_to_box(lon, lat)
        await self.command(
            rt_codec.at_command(lon, lat, heading, from_node, to_node) + "\n"
            + rt_codec.map_displayed_command(*box_b))

        if match is not None:
            await self._simulate_driving(lat, lon, heading, from_node, to_node)

        request = report_codec.build_request(
            lat=lat, lon=lon, altitude_m=altitude_m, heading_deg=heading_deg,
            member=member, subtype_number=subtype_number, is_opposite=is_opposite,
            time_delta_s=time_delta_s, now_ms=now_ms,
            from_node=from_node if match else 0, to_node=to_node if match else 0)
        elements = await self.command(rt_codec.report_payload(request))

        # The trailing close-out is camouflage; a failure here must not turn
        # an accepted report into a failed one.
        try:
            await self.command(rt_codec.see_me_command(2))
        except Exception:  # noqa: BLE001
            log.debug("report close-out failed", exc_info=True)

        if report_codec.report_accepted(elements):
            return ReportResult(True, report_codec.report_uuid_from(elements),
                                report_codec.report_points_from(elements))
        return ReportResult(False, error="no report response")

    async def _simulate_driving(self, lat: float, lon: float, heading: int,
                                from_node: int, to_node: int) -> None:
        """Three one-second steps along the heading at the client's simulated
        driving speed, each an At plus MapDisplayed for the stepped position.
        Anti-abuse camouflage, so it runs whenever a segment matched, and a
        failed step never aborts the report."""
        radians = math.radians(heading)
        for step in range(3):
            lat += (math.cos(radians) * SIMULATED_SPEED_MS) / M_PER_DEG_LAT
            lon += (math.sin(radians) * SIMULATED_SPEED_MS) / m_per_deg_lon(lat)
            try:
                box = rt_codec.circle_to_box(lon, lat)
                await self.command(
                    rt_codec.at_command(lon, lat, heading, from_node, to_node) + "\n"
                    + rt_codec.map_displayed_command(*box))
            except Exception as exc:  # noqa: BLE001
                log.warning("simulate_driving step %s failed: %s: %s",
                            step, type(exc).__name__, exc)
            await asyncio.sleep(0.3)

    async def confirm_alert(self, alert_id: int) -> None:
        """Thumbs-up an existing alert by its numeric id."""
        await self.command(f"ThumbsUp,{alert_id}")

    async def discard_alert(self, alert_id: int) -> None:
        """Say an existing alert is not there, by its numeric id."""
        await self.command(f"ReportRmAlert,{alert_id}")


def _raise_for_login_error(error_type: int) -> None:
    """Transient server-side problems are operational and must not cost a
    good account; only a real credential failure does."""
    name = proto.AUTH_ERROR_TYPES.get(error_type, str(error_type))
    if name in ("INTERNAL_ISSUES", "UNKNOWN_ERROR"):
        raise WazeOperationError(f"login error: {name}")
    raise AccountRejected(f"login error: {name}")
