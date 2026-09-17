"""Building a Waze report and reading the answer.

Ported from ``WazeReportCodec.java``. Which AlertDetails member and subtype
number a report carries is decided in ``mapping.py``, the same split the Java
version has between ``WazeReportCodec`` and ``AlertMapper``.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import proto, wire
from .rt_codec import normalize_angle_360

# The AlertDetails oneof members.
TRAFFIC = 1
POLICE = 2
CRASH = 3
HAZARD = 4


@dataclass(frozen=True)
class ReportResult:
    accepted: bool
    uuid: str | None = None
    points: int = -1
    error: str | None = None


def build_request(*, lat: float, lon: float, altitude_m: float, heading_deg: float,
                  member: int, subtype_number: int, is_opposite: bool,
                  time_delta_s: int, now_ms: int,
                  from_node: int, to_node: int) -> bytes:
    """The AddUserReportedAlertRequest body.

    ``from_node`` and ``to_node`` are 0 when the report could not be snapped
    to a road, and the SegmentNodes are then left out entirely.
    """
    coord = proto.coordinate_with_alt(lon, lat, altitude_m)
    gps = proto.gps_position(coord, 10.0, now_ms)
    nodes = (proto.segment_nodes(from_node, to_node)
             if from_node != 0 or to_node != 0 else None)
    return proto.add_user_reported_alert_request(
        position=proto.user_position(gps, nodes),
        azymuth=normalize_angle_360(heading_deg),
        details=proto.alert_details(member, subtype_number),
        segment_direction=(proto.SEGMENT_DIRECTION_BACKWARD if is_opposite
                           else proto.SEGMENT_DIRECTION_FORWARD),
        report_time_s=(now_ms // 1000) - time_delta_s,
    )


def report_accepted(elements: list[dict[int, list]]) -> bool:
    """Whether the batch says the report was taken.

    A snapped report comes back with points, the default status and an empty
    uuid on an anonymous account, while a position-only report gets no
    response element at all. So the acceptance signal is a response element
    that is not an explicit failure, not a non-empty uuid.
    """
    for el in elements:
        response = wire.sub(el, proto.EL_ADD_USER_REPORTED_ALERT_RESPONSE)
        if response is not None and wire.first(
                response, 1, 0) != proto.ADD_ALERT_STATUS_FAILURE:
            return True
    return False


def report_uuid_from(elements: list[dict[int, list]]) -> str | None:
    for el in elements:
        response = wire.sub(el, proto.EL_ADD_USER_REPORTED_ALERT_RESPONSE)
        if response is not None and wire.text(response, 5):
            return wire.text(response, 5)
    return None


def report_points_from(elements: list[dict[int, list]]) -> int:
    for el in elements:
        response = wire.sub(el, proto.EL_ADD_USER_REPORTED_ALERT_RESPONSE)
        if response is not None:
            return wire.first(response, 2, 0)
    return -1
