"""Constants and host resolution for the Waze mobile-app "RT" protocol.

Ported from ``WazeConstants.java`` in highway-radar-sabre-plus. The values are
what the Waze client itself sends; changing them changes how the server
answers, so they are kept as they are there.
"""

from __future__ import annotations

import math

PROTOCOL_VERSION = 234
APP_VERSION = "5.17.1.0"

PATH_LOGIN = "/rtserver/distrib/login"
PATH_STATIC = "/rtserver/distrib/static"
PATH_COMMAND = "/rtserver/distrib/command"

WAIT_TIMEOUT_LOGIN = "8500"
WAIT_TIMEOUT_COMMAND = "10500"

SESSION_IDLE_TIMEOUT_S = 100.0
MAX_CONSECUTIVE_REJECTIONS = 10
MAX_ACCOUNTS_PER_DAY = 10
TILE_NUM_ROWS = 18000
M_PER_DEG_LAT = 110574.0


def m_per_deg_lon(lat: float) -> float:
    return math.cos(math.radians(lat)) * 111320.0


def rt_host(region: str) -> str:
    """RT server host for a region ("na" covers all of California)."""
    if region == "na":
        return "rt-xlb-am.waze.com"
    if region == "il":
        return "rt-xlb-il.waze.com"
    return "rt-xlb-row.waze.com"


def tile_host(region: str) -> str:
    if region == "na":
        return "ctilesgcs-am.waze.com"
    if region == "il":
        return "ctilesgcs-il.waze.com"
    return "ctilesgcs-row.waze.com"


def region_for(lat: float, lon: float) -> str:
    """Which RT region serves a point."""
    if -170.0 <= lon <= -52.0 and -15.0 <= lat <= 73.0:
        return "na"
    if 34.0 <= lon <= 36.0 and 29.5 <= lat <= 33.5:
        return "il"
    return "row"
