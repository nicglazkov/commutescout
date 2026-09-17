"""Field numbers and enums of the Waze RT protocol, and the messages built
from them.

This is the hand-written stand-in for the classes
highway-radar-sabre-plus generates from ``app/src/main/proto/waze.proto``.
The numbers below are copied from that file; the scope is the same, too:
the area-alert fetch path, the report (write) path, and the login and
register handshakes around them. Everything else on the wire is skipped by
``wire.fields``, which is exactly what an undeclared protobuf field does.
"""

from __future__ import annotations

from . import wire

# ----------------------------------------------------------------- numbers

BATCH_ELEMENT = 1001

# Element members.
EL_OLD_COMMAND = 2001
EL_ERROR = 2003
EL_REPORT_ADS_SETTING = 2108
EL_CLIENT_INFO = 2184
EL_REGISTER = 2219
EL_REGISTER_SUCCESSFUL = 2220
EL_LOGIN_ERROR = 2224
EL_ADD_ALERT_ACTION = 2708
EL_ADD_USER_REPORTED_ALERT_REQUEST = 2737
EL_ADD_USER_REPORTED_ALERT_RESPONSE = 2738
EL_LOGIN_REQUEST = 2744
EL_LOGIN_RESPONSE = 2745

# Enum values used by the builders.
DEVICE_TYPE_ANDROID = 50
APP_TYPE_WAZE = 1
APP_FLAVOR_ALPHA = 5
DISPLAY_BUILT_IN = 2
LOGIN_REASON_NORMAL = 0
SEGMENT_DIRECTION_FORWARD = 1
SEGMENT_DIRECTION_BACKWARD = 2
REPORTING_MANNER_DEFAULT = 1
ADD_ALERT_STATUS_FAILURE = 2

ALERT_TYPES = {
    0: "UNKNOWN_TYPE", 1: "CHIT_CHAT", 2: "POLICE", 3: "ACCIDENT", 4: "JAM",
    5: "TRAFFIC_INFO", 6: "HAZARD", 7: "MISC", 8: "CONSTRUCTION", 9: "PARKING",
    10: "DYNAMIC", 11: "CAMERA", 12: "__NOT_IN_USE__PARKED", 13: "ROAD_CLOSED",
    14: "SYSTEM_ROAD_CLOSED", 15: "UNKNOWN_ALERT", 16: "SOS", 17: "CRASH_PRONE",
    19: "TURN_CLOSED", 100: "NEW_BAD_WEATHER", 101: "NEW_LANE_CLOSED",
    103: "PERMANENT_HAZARD", 104: "PERSONAL_SAFETY",
}

ALERT_SUBTYPES = {
    0: "NO_SUBTYPE",
    201: "POLICE_VISIBLE", 202: "POLICE_HIDING", 203: "POLICE_WITH_MOBILE_CAMERA",
    301: "ACCIDENT_MINOR", 302: "ACCIDENT_MAJOR",
    401: "JAM_MODERATE_TRAFFIC", 402: "JAM_HEAVY_TRAFFIC",
    403: "JAM_STAND_STILL_TRAFFIC", 404: "JAM_LIGHT_TRAFFIC",
    601: "HAZARD_ON_ROAD", 602: "HAZARD_ON_SHOULDER", 603: "HAZARD_WEATHER",
    604: "HAZARD_ON_ROAD_OBJECT", 605: "HAZARD_ON_ROAD_POT_HOLE",
    606: "HAZARD_ON_ROAD_ROAD_KILL", 607: "HAZARD_ON_SHOULDER_CAR_STOPPED",
    608: "HAZARD_ON_SHOULDER_ANIMALS", 609: "HAZARD_ON_SHOULDER_MISSING_SIGN",
    610: "HAZARD_WEATHER_FOG", 611: "HAZARD_WEATHER_HAIL",
    612: "HAZARD_WEATHER_HEAVY_RAIN", 613: "HAZARD_WEATHER_HEAVY_SNOW",
    614: "HAZARD_WEATHER_FLOOD", 615: "HAZARD_WEATHER_MONSOON",
    616: "HAZARD_WEATHER_TORNADO", 617: "HAZARD_WEATHER_HEAT_WAVE",
    618: "HAZARD_WEATHER_HURRICANE", 619: "HAZARD_WEATHER_FREEZING_RAIN",
    620: "HAZARD_ON_ROAD_LANE_CLOSED", 621: "HAZARD_ON_ROAD_OIL",
    622: "HAZARD_ON_ROAD_ICE", 623: "HAZARD_ON_ROAD_CONSTRUCTION",
    624: "HAZARD_ON_ROAD_CAR_STOPPED", 625: "HAZARD_ON_ROAD_TRAFFIC_LIGHT_FAULT",
    626: "HAZARD_ON_ROAD_EMERGENCY_VEHICLE",
    1201: "__NOT_IN_USE__PARKED_ON", 1202: "__NOT_IN_USE__PARKED_OFF",
    1301: "ROAD_CLOSED_HAZARD", 1302: "ROAD_CLOSED_CONSTRUCTION",
    1303: "ROAD_CLOSED_EVENT",
    1601: "SOS_FLAT_TIRE", 1602: "SOS_NO_FUEL", 1603: "SOS_MEDICAL_HELP",
    1604: "SOS_MECHANICAL_PROBLEM", 1605: "SOS_OTHER", 1606: "SOS_BATTERY_ISSUE",
    1701: "CRASH_PRONE_SHORT_ALERT_LENGTH", 1702: "CRASH_PRONE_LONG_ALERT_LENGTH",
    1901: "TURN_CLOSED_EVENT",
    2000: "BAD_WEATHER_DEFAULT", 2001: "BAD_WEATHER_SLIPPERY_ROAD",
    2002: "LANE_CLOSURE_BLOCKED_LANES", 2003: "LANE_CLOSURE_LEFT_LANE",
    2004: "LANE_CLOSURE_RIGHT_LANE", 2005: "LANE_CLOSURE_CENTER_LANE",
    3001: "PERMANENT_HAZARD_SPEED_BUMP", 3002: "PERMANENT_HAZARD_TOPES",
    3003: "PERMANENT_HAZARD_TOLL_BOOTH", 3004: "PERMANENT_HAZARD_DANGEROUS_CURVE",
    3005: "PERMANENT_HAZARD_DANGEROUS_INTERSECTION",
    3006: "PERMANENT_HAZARD_DANGEROUS_SPLIT",
    3007: "PERMANENT_HAZARD_DANGEROUS_MERGE", 3008: "PERMANENT_HAZARD_SCHOOL_ZONE",
    4001: "DEFAULT_PERSONAL_SAFETY", 5001: "DEFAULT_CAMERA",
}

AUTH_ERROR_TYPES = {
    0: "UNKNOWN_ERROR", 1: "WRONG_USER_PASSWORD", 2: "INTERNAL_ISSUES",
    3: "NOT_AUTHORIZED", 4: "REFRESH_TOKEN", 5: "ANOTHER_DEVICE_LOGGED_IN",
    6: "INVALID_TOKEN", 7: "UNAUTHENTICATED_TOKEN", 8: "TOKEN_QUOTA_EXCEEDED",
    9: "APP_VERSION_NOT_SUPPORTED",
}


def type_name(number: int) -> str:
    """The wire name of an alert type, as the mapping table reads it.
    The unnamed types collapse to "UNKNOWN", as they do in the Java port."""
    name = ALERT_TYPES.get(number, "UNKNOWN")
    return "UNKNOWN" if name == "UNKNOWN_TYPE" or name.startswith("__NOT_IN_USE") else name


def subtype_name(number: int) -> str:
    """The wire name of an alert subtype. ``NO_SUBTYPE`` and the reserved
    values become "", so the caller falls back to the type name."""
    name = ALERT_SUBTYPES.get(number, "")
    return "" if name == "NO_SUBTYPE" or name.startswith("__NOT_IN_USE") else name


# ---------------------------------------------------------------- builders

def batch(element: bytes) -> bytes:
    """A Batch carrying one Element."""
    return wire.message(BATCH_ELEMENT, element)


def element(field: int, body: bytes) -> bytes:
    """An Element carrying one member."""
    return wire.message(field, body)


def coordinate(lon: float, lat: float) -> bytes:
    return wire.num(101, round(lon * 1_000_000.0)) + wire.num(102, round(lat * 1_000_000.0))


def display(width: int, height: int) -> bytes:
    return wire.num(1, DISPLAY_BUILT_IN) + wire.num(2, width) + wire.num(3, height)


def client_info(*, protocol: int, client_version: str, last_position: bytes,
                manufacturer: str, model: str, os_version: str, locale: str,
                installation_id: str, device_type: int, app_type: int,
                displays: list[bytes], os_language_id: str, session_uuid: str,
                current_time_millis: int, app_flavor: int) -> bytes:
    return (
        wire.num(1, protocol)
        + wire.string(3, client_version)
        + wire.message(4, last_position)
        + wire.string(5, manufacturer)
        + wire.string(6, model)
        + wire.string(11, os_version)
        + wire.string(16, locale)
        + wire.string(17, installation_id)
        + wire.num(18, device_type)
        + wire.num(19, app_type)
        + b"".join(wire.message(24, d) for d in displays)
        + wire.string(25, os_language_id)
        + wire.string(26, session_uuid)
        + wire.num(28, current_time_millis)
        + wire.num(31, app_flavor)
    )


def password_credential(username: str, password: str) -> bytes:
    return wire.string(1, username) + wire.string(2, password)


def login_request(username: str, password: str) -> bytes:
    return wire.message(1, password_credential(username, password)) + wire.num(
        3, LOGIN_REASON_NORMAL)


def uid(server_session_id: int, secret_key: str) -> bytes:
    return wire.num(1, server_session_id) + wire.string(2, secret_key)


def coordinate_with_alt(lon: float, lat: float, alt_m: float) -> bytes:
    return (wire.num(101, round(lon * 1_000_000.0))
            + wire.num(102, round(lat * 1_000_000.0))
            + wire.num(103, round(alt_m * 1_000_000.0)))


def segment_nodes(from_node: int, to_node: int) -> bytes:
    return wire.num(1, from_node) + wire.num(2, to_node)


def gps_position(coord: bytes, accuracy_m: float, time_epoch_ms: int) -> bytes:
    return wire.message(1, coord) + wire.double(2, accuracy_m) + wire.num(3, time_epoch_ms)


def user_position(gps: bytes, nodes: bytes | None) -> bytes:
    out = wire.message(1, gps)
    if nodes is not None:
        out += wire.message(2, nodes)
    return out


def timestamp(seconds: int) -> bytes:
    return wire.num(1, seconds)


def alert_details(member: int, subtype_number: int) -> bytes:
    """An AlertDetails oneof: 1 traffic, 2 police, 3 crash, 4 hazard on road.
    Each member is a one-field message holding its own subtype enum."""
    return wire.message(member, wire.num(1, subtype_number))


def add_user_reported_alert_request(*, position: bytes, azymuth: int, details: bytes,
                                    segment_direction: int, report_time_s: int) -> bytes:
    return (
        wire.message(1, position)
        + wire.num(2, azymuth)
        + wire.message(3, details)
        + wire.num(4, segment_direction)
        + wire.message(5, timestamp(report_time_s))
        + wire.num(7, REPORTING_MANNER_DEFAULT)
    )


# ----------------------------------------------------------------- parsing

def elements(body: bytes) -> list[dict[int, list]]:
    """Every Element of a Batch, parsed."""
    return [wire.fields(el) for el in wire.fields(body).get(BATCH_ELEMENT, [])
            if isinstance(el, bytes)]
