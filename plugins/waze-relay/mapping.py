"""Waze alert types to Flare kinds, and back again for reports.

The table in docs/plugins-waze-google-plan.md is the approved one; where it
and the mapping in highway-radar-sabre-plus's ``AlertMapper.java`` disagree,
this follows the sabre-plus reading, because it is the one written against
the live feed. The three places that differ, and the two places this follows
neither, are listed in the plugin README.

The Flare vocabulary is the one in docs/flare.md. Anything with no sensible
home lands on ``OTHER``; chit-chat and parking reports are dropped, because
they are not road conditions.
"""

from __future__ import annotations

# Waze subtype to Flare kind. The subtype is the specific one, so it wins
# whenever the alert carries one.
SUBTYPE_TO_KIND = {
    "POLICE_VISIBLE": "POLICE_VISIBLE",
    "POLICE_HIDING": "POLICE_HIDING",
    # Covert enforcement, hidden rather than visible, as sabre-plus reads it.
    "POLICE_WITH_MOBILE_CAMERA": "POLICE_HIDING",
    "ACCIDENT_MINOR": "CRASH_MINOR",
    "ACCIDENT_MAJOR": "CRASH_MAJOR",
    "JAM_LIGHT_TRAFFIC": "JAM_MODERATE",
    "JAM_MODERATE_TRAFFIC": "JAM_MODERATE",
    "JAM_HEAVY_TRAFFIC": "JAM_HEAVY",
    "JAM_STAND_STILL_TRAFFIC": "JAM_STANDSTILL",
    "HAZARD_ON_ROAD": "HAZARD_ON_ROAD",
    "HAZARD_ON_ROAD_OBJECT": "HAZARD_OBJECT",
    "HAZARD_ON_ROAD_POT_HOLE": "HAZARD_POTHOLE",
    "HAZARD_ON_ROAD_ROAD_KILL": "HAZARD_ANIMAL",
    "HAZARD_ON_ROAD_LANE_CLOSED": "LANE_CLOSED",
    "HAZARD_ON_ROAD_OIL": "HAZARD_ON_ROAD",
    "HAZARD_ON_ROAD_ICE": "WEATHER_ICE",
    "HAZARD_ON_ROAD_CONSTRUCTION": "HAZARD_CONSTRUCTION",
    "HAZARD_ON_ROAD_CAR_STOPPED": "HAZARD_ON_ROAD",
    "HAZARD_ON_ROAD_TRAFFIC_LIGHT_FAULT": "HAZARD_ON_ROAD",
    "HAZARD_ON_ROAD_EMERGENCY_VEHICLE": "HAZARD_ON_ROAD",
    "HAZARD_ON_SHOULDER": "HAZARD_SHOULDER",
    "HAZARD_ON_SHOULDER_CAR_STOPPED": "HAZARD_SHOULDER_CAR",
    "HAZARD_ON_SHOULDER_ANIMALS": "HAZARD_SHOULDER_ANIMAL",
    "HAZARD_ON_SHOULDER_MISSING_SIGN": "HAZARD_SHOULDER",
    "HAZARD_WEATHER": "OTHER",
    "HAZARD_WEATHER_FOG": "WEATHER_FOG",
    "HAZARD_WEATHER_HAIL": "WEATHER_HAIL",
    "HAZARD_WEATHER_HEAVY_RAIN": "OTHER",
    "HAZARD_WEATHER_HEAVY_SNOW": "WEATHER_SNOW",
    "HAZARD_WEATHER_FLOOD": "WEATHER_FLOOD",
    "HAZARD_WEATHER_MONSOON": "WEATHER_FLOOD",
    "HAZARD_WEATHER_FREEZING_RAIN": "WEATHER_ICE",
    "HAZARD_WEATHER_TORNADO": "OTHER",
    "HAZARD_WEATHER_HEAT_WAVE": "OTHER",
    "HAZARD_WEATHER_HURRICANE": "OTHER",
    "ROAD_CLOSED_HAZARD": "ROAD_CLOSED",
    "ROAD_CLOSED_CONSTRUCTION": "ROAD_CLOSED",
    "ROAD_CLOSED_EVENT": "ROAD_CLOSED",
    "TURN_CLOSED_EVENT": "ROAD_CLOSED",
    "LANE_CLOSURE_BLOCKED_LANES": "LANE_CLOSED",
    "LANE_CLOSURE_LEFT_LANE": "LANE_CLOSED",
    "LANE_CLOSURE_RIGHT_LANE": "LANE_CLOSED",
    "LANE_CLOSURE_CENTER_LANE": "LANE_CLOSED",
    "BAD_WEATHER_SLIPPERY_ROAD": "WEATHER_ICE",
    "BAD_WEATHER_DEFAULT": "OTHER",
    "DEFAULT_CAMERA": "CAMERA_SPEED",
}

# Waze type to Flare kind, for an alert with no subtype or an unknown one.
TYPE_TO_KIND = {
    "POLICE": "POLICE_VISIBLE",
    "ACCIDENT": "CRASH_MINOR",
    "JAM": "JAM_MODERATE",
    "HAZARD": "HAZARD_ON_ROAD",
    "ROAD_CLOSED": "ROAD_CLOSED",
    "SYSTEM_ROAD_CLOSED": "ROAD_CLOSED",
    "TURN_CLOSED": "ROAD_CLOSED",
    "CONSTRUCTION": "HAZARD_CONSTRUCTION",
    "NEW_LANE_CLOSED": "LANE_CLOSED",
    "NEW_BAD_WEATHER": "OTHER",
    "CAMERA": "CAMERA_SPEED",
    "SOS": "OTHER",
    "CRASH_PRONE": "OTHER",
    "PERMANENT_HAZARD": "OTHER",
    "PERSONAL_SAFETY": "OTHER",
    "TRAFFIC_INFO": "OTHER",
    "MISC": "OTHER",
    "DYNAMIC": "OTHER",
    "UNKNOWN_ALERT": "OTHER",
    "UNKNOWN": "OTHER",
}

# Not road conditions, so they are never served.
DROPPED_TYPES = frozenset({"CHIT_CHAT", "PARKING"})

KINDS = sorted(set(SUBTYPE_TO_KIND.values()) | set(TYPE_TO_KIND.values()))

# Seconds after the report (or the last confirmation) an alert goes stale,
# from the plan: twenty minutes for police and hazards, forty-five for
# crashes, an hour for closures, five minutes for a jam.
TTL_S = {
    "POLICE": 1200, "CRASH": 2700, "HAZARD": 1200, "WEATHER": 1200,
    "ROAD_CLOSED": 3600, "LANE_CLOSED": 3600, "RAMP_CLOSED": 3600,
    "JAM": 300, "CAMERA": 1200, "OTHER": 1200,
}

BASE_RELIABILITY = 0.5
PER_THUMB = 0.1

# The AlertDetails members of a report, from waze/report_codec.py.
TRAFFIC, POLICE, CRASH, HAZARD = 1, 2, 3, 4

# Flare kind to the Waze report member and its subtype number. A kind that is
# not here cannot be reported to Waze.
REPORT_SUBTYPE = {
    "POLICE_VISIBLE": (POLICE, 1),
    "POLICE_OTHER": (POLICE, 1),
    "POLICE_HIDING": (POLICE, 2),
    "CRASH_MAJOR": (CRASH, 3),
    "CRASH_MINOR": (CRASH, 4),
    "JAM_STANDSTILL": (TRAFFIC, 2),
    "JAM_MODERATE": (TRAFFIC, 4),
    "JAM_HEAVY": (TRAFFIC, 5),
    "HAZARD_ON_ROAD": (HAZARD, 1),
    "HAZARD_CONSTRUCTION": (HAZARD, 2),
    "HAZARD_OBJECT": (HAZARD, 4),
    "HAZARD_POTHOLE": (HAZARD, 5),
    "HAZARD_ANIMAL": (HAZARD, 8),
    "HAZARD_SHOULDER": (HAZARD, 11),
    "HAZARD_SHOULDER_CAR": (HAZARD, 12),
    "HAZARD_SHOULDER_ANIMAL": (HAZARD, 8),
}

REPORTABLE_KINDS = sorted(REPORT_SUBTYPE)


def flare_kind(waze_type: str, subtype: str) -> str | None:
    """The Flare kind for one Waze alert, or None when it is not a road
    condition."""
    if waze_type in DROPPED_TYPES:
        return None
    if subtype and subtype in SUBTYPE_TO_KIND:
        return SUBTYPE_TO_KIND[subtype]
    return TYPE_TO_KIND.get(waze_type, "OTHER")


def ttl_for(kind: str) -> int:
    """How long a kind stays fresh, in seconds."""
    for prefix, ttl in TTL_S.items():
        if kind.startswith(prefix):
            return ttl
    return TTL_S["OTHER"]


def reliability(n_confirmations: int) -> float:
    """The plugin's own confidence, 0 to 1.

    The plan reads this off the feed's ``reliability`` field, which the
    GeoRSS feed had and the RT protocol does not, so it is derived from the
    confirmation count instead: half by default, rising with every thumbs-up.
    """
    return min(1.0, BASE_RELIABILITY + PER_THUMB * max(0, n_confirmations))


def report_subtype(kind: str) -> tuple[int, int] | None:
    """The Waze report member and subtype number for a Flare kind, or None
    when Waze takes no report of that kind."""
    return REPORT_SUBTYPE.get(kind)
