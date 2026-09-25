"""Feed freshness on a timer: a source that stops updating says so.

Every feed is served stale-while-revalidate, which is what keeps the map
up when an agency has a bad hour, and also what hides a feed that has
quietly stopped: the last good copy goes on being served, flagged stale,
and nothing looks broken. The publisher and the budgets already had
alerts; a single source going dark had none.

So this checks every source on a timer. A source that has not
refreshed within its own limit on GRACE_CHECKS consecutive checks is
reported: ``feed stale:`` at ERROR once, then at WARNING every hour it
stays that way, then ``feed recovered:`` when it comes back. A
log-based alert policy matches the ERROR line, so one outage is one
notification rather than one an hour: the first night this ran, three
short blips and one long outage produced fourteen emails.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import UTC, datetime

log = logging.getLogger("ca_roads_demo.freshness")

CHECK_EVERY_S = 300
REPEAT_S = 3600
# Consecutive checks a source must fail before it is reported. One
# check is one failed read, and a single failed read is Tuesday: the
# first night every California feed was reported and recovered inside
# six minutes at least once.
GRACE_CHECKS = 2
# California feeds: (RoadData method, seconds of age that count as stale).
# Each is several times its refresh interval, so one failed refresh, or
# even a few, never trips it. Cameras are an inventory served for hours
# on purpose (see roaddata.py), so their limit is the longest.
CALIFORNIA = {
    "California incidents (CHP)": ("incidents", 20 * 60),
    "California lane closures (Caltrans)": ("lane_closures", 30 * 60),
    "California chain controls (Caltrans)": ("chain_controls", 30 * 60),
    "Wildfires (WFIGS and CAL FIRE)": ("wildfires", 60 * 60),
    "California cameras (Caltrans)": ("cameras", 7 * 3600),
    "California message signs (Caltrans)": ("message_signs", 30 * 60),
    "California road weather (Caltrans)": ("road_weather", 60 * 60),
}
# Every other state's feeds share one cache; an entry that has not been
# refreshed in this long has been failing for most of it. Ninety
# minutes rather than forty-five: several state feeds go away for
# fifty minutes a few times a day and come back on their own, and a
# report that recovers before anyone could act on it is noise.
STATE_STALE_S = 90 * 60
# Camera inventories are served for hours on purpose (see
# CAM_MAX_SERVE in states.py), so their limit matches.
CAMERA_STALE_S = 7 * 3600

# Upstream errors can quote the request URL, and several state feeds put
# their API key in the query string. Nothing after a "?" is logged.
_QUERY = re.compile(r"\?[^\s'\"]*")

_stale_since: dict[str, float] = {}
_last_logged: dict[str, float] = {}
# Consecutive checks each source has failed; see GRACE_CHECKS.
_strikes: dict[str, int] = {}


def _clean(error: str | None) -> str:
    return f" ({_QUERY.sub('?...', error)[:160]})" if error else ""


def _state_limit(key: str) -> float:
    """How old one state cache entry may get. Toll feeds refresh on their
    own intervals, up to once a day, so theirs scales with that."""
    from ca_roads_demo import states

    if isinstance(key, str) and key.startswith("toll:"):
        spec = states.TOLL_SOURCES.get(key[len("toll:"):])
        if spec:
            return max(STATE_STALE_S, 3 * float(spec[-1]))
    if isinstance(key, str) and key.startswith("neccam:"):
        return CAMERA_STALE_S
    return STATE_STALE_S


async def find_stale() -> dict[str, str]:
    """Every source that is stale right now, with why."""
    from ca_roads_demo import states
    from ca_roads_mcp import server as tools

    stale: dict[str, str] = {}
    road = tools.get_road()
    now = datetime.now(UTC)
    for label, (method, limit) in CALIFORNIA.items():
        try:
            result = await getattr(road, method)()
        except Exception as exc:  # noqa: BLE001 - a raising feed is a stale feed
            stale[label] = f"the read raised {type(exc).__name__}"
            continue
        if result.data_as_of is None:
            stale[label] = "nothing served" + _clean(result.error or "no data")
            continue
        age = (now - result.data_as_of).total_seconds()
        if age > limit:
            stale[label] = f"last good data {age / 60:.0f} min old" + _clean(result.error)
    mono = time.monotonic()
    cache = states._cache
    for key, entry in list(cache._entries.items()):
        age = mono - entry.fetched_monotonic
        if age > _state_limit(key):
            stale[f"state feed {key}"] = (f"last good data {age / 60:.0f} min old"
                                          + _clean(cache._errors.get(key)))
    return stale


def report(stale: dict[str, str], now: float | None = None) -> None:
    """Log what changed: a source going stale, one still stale an hour
    later, and one that recovered.

    ERROR is the alert. It is written once, when a source has failed
    GRACE_CHECKS checks in a row; the hourly reminder while it stays
    stale is WARNING, which the alert policy does not match.
    """
    now = time.monotonic() if now is None else now
    for label in [k for k in _strikes if k not in stale]:
        _strikes.pop(label, None)
    for label, why in stale.items():
        _strikes[label] = _strikes.get(label, 0) + 1
        if _strikes[label] < GRACE_CHECKS:
            continue
        first = label not in _stale_since
        _stale_since.setdefault(label, now)
        if first:
            log.error("feed stale: %s: %s", label, why)
            _last_logged[label] = now
        elif now - _last_logged.get(label, -1e18) >= REPEAT_S:
            minutes = (now - _stale_since[label]) / 60
            log.warning("feed still stale: %s: %s (for %.0f min)", label, why, minutes)
            _last_logged[label] = now
    for label in [k for k in _stale_since if k not in stale]:
        log.info("feed recovered: %s", label)
        _stale_since.pop(label, None)
        _last_logged.pop(label, None)


async def run() -> None:
    """Check forever; started from the app lifespan."""
    while True:
        await asyncio.sleep(CHECK_EVERY_S)
        try:
            report(await find_stale())
        except Exception as exc:  # noqa: BLE001 - never let the checker kill itself
            log.warning("freshness check failed: %s", type(exc).__name__)
