"""The alert record, the merged cache, and the confirmation tracker.

Ported from ``WazeAlert.java``, ``AlertQueryResult.java``,
``WazeAlertCache.java`` and ``WazeConfirmTracker.java``.

The cache exists because the RT ``/command`` endpoint is session-stateful: it
sends each alert as an ``AddAlertAction`` only once per session, then an
``"RmAlert,<uuid>"`` line when the alert clears. A consumer that replaced its
view with every response would go near-empty after the first query. Each
query's result is therefore merged in, and removals are soft-deleted for five
minutes before the record is dropped.

That per-session, not per-box, delivery is also why the relay keeps one cache
for the whole service rather than one per grid cell: an alert first delivered
to a query for one cell is never re-sent for the neighbouring cell that
overlaps it.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

SOFT_DELETE_S = 5 * 60.0
CONFIRM_TTL_S = 60 * 60.0


@dataclass(frozen=True)
class WazeAlert:
    """One alert decoded from a RealtimeAlert message (the fields the relay
    serves; the rest of the message is skipped)."""

    uuid: str
    id: int
    type: str
    subtype: str
    lon: float
    lat: float
    magvar: int
    pub_millis: int
    n_thumbs_up: int | None
    street: str | None
    city: str | None


@dataclass(frozen=True)
class AlertQueryResult:
    """One query's deltas: the alerts the server added and the uuids it
    removed."""

    new_alerts: list[WazeAlert]
    removed_ids: list[str]


class AlertCache:
    """A uuid-keyed cache with soft-delete, merging one query at a time."""

    def __init__(self, now: Callable[[], float] | None = None) -> None:
        self._now = now or time.time
        self._alerts: dict[str, WazeAlert] = {}
        self._soft_deleted: dict[str, float] = {}

    def submit(self, result: AlertQueryResult) -> None:
        """Apply one query's deltas: upsert adds, soft-delete removals."""
        for alert in result.new_alerts:
            if alert.uuid:
                self._alerts[alert.uuid] = alert
                self._soft_deleted.pop(alert.uuid, None)
        now = self._now()
        for uuid_ in result.removed_ids:
            if uuid_ in self._alerts and uuid_ not in self._soft_deleted:
                self._soft_deleted[uuid_] = now

    def snapshot(self) -> list[WazeAlert]:
        """Every cached alert that is not currently soft-deleted, after
        purging the soft-deletes that have run out their grace."""
        now = self._now()
        for uuid_ in [u for u, t in self._soft_deleted.items() if now - t >= SOFT_DELETE_S]:
            self._alerts.pop(uuid_, None)
            self._soft_deleted.pop(uuid_, None)
        return [a for u, a in self._alerts.items() if u not in self._soft_deleted]

    def clear(self) -> None:
        self._alerts.clear()
        self._soft_deleted.clear()

    def __len__(self) -> int:
        return len(self._alerts)


@dataclass
class _Sighting:
    confirm_s: float | None
    thumbs: int
    expiry: float


class ConfirmTracker:
    """Derives an alert's confirmation time.

    The RT feed carries no confirmation timestamp, so it is inferred as the
    moment the thumbs-up count was last seen to increase. Entries expire an
    hour after they were last touched, so the map self-trims.
    """

    def __init__(self, now: Callable[[], float] | None = None) -> None:
        self._now = now or time.time
        self._seen: dict[str, _Sighting] = {}

    def confirm_ts(self, alert_id: str, n_thumbs_up: int | None) -> float | None:
        """Record this sighting and return the confirmation time in epoch
        seconds, or None when the count has never been seen to rise."""
        now = self._now()
        self._purge(now)
        thumbs = n_thumbs_up or 0
        seen = self._seen.get(alert_id)
        if seen is None:
            self._seen[alert_id] = _Sighting(None, thumbs, now + CONFIRM_TTL_S)
            return None
        seen.expiry = now + CONFIRM_TTL_S
        if thumbs > seen.thumbs:
            seen.confirm_s = now
            seen.thumbs = thumbs
        return seen.confirm_s

    def _purge(self, now: float) -> None:
        for alert_id in [k for k, v in self._seen.items() if v.expiry <= now]:
            self._seen.pop(alert_id, None)
