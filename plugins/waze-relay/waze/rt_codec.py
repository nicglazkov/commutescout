"""The Waze RT wire format: request lines in, response batches out.

Ported from ``WazeRtCodec.java``.

Body framing: each protobuf "line" is ``"ProtoBase64," + base64(Batch{element})``
with no line wrapping, and several lines are joined with a newline. Raw command
lines (SeeMe, Location, MapDisplayed, At) are sent as plain text, not
protobuf-wrapped.
"""

from __future__ import annotations

import base64
import math
import random
import time
import uuid

from . import proto, wire
from .constants import APP_VERSION, M_PER_DEG_LAT, PROTOCOL_VERSION, m_per_deg_lon
from .device import DeviceIdentity


def proto_base64_line(element: bytes) -> str:
    return "ProtoBase64," + base64.b64encode(proto.batch(element)).decode("ascii")


def report_payload(request: bytes) -> str:
    """One report line: a ProtoBase64-framed AddUserReportedAlertRequest."""
    return proto_base64_line(proto.element(proto.EL_ADD_USER_REPORTED_ALERT_REQUEST, request))


# ------------------------------------------------------- request lines

def build_client_info_line(device: DeviceIdentity, lon: float, lat: float) -> str:
    """ClientInfo, with the position jittered by up to 500 m as the Waze
    client does before it sends one."""
    lon_offset = ((random.random() - 0.5) * 1000.0) / m_per_deg_lon(lat)  # noqa: S311
    lat_offset = ((random.random() - 0.5) * 1000.0) / M_PER_DEG_LAT  # noqa: S311
    body = proto.client_info(
        protocol=PROTOCOL_VERSION,
        client_version=APP_VERSION,
        last_position=proto.coordinate(lon + lon_offset, lat + lat_offset),
        manufacturer=device.manufacturer,
        model=device.model,
        os_version=device.os_version,
        locale="en",
        installation_id=device.installation_id,
        device_type=proto.DEVICE_TYPE_ANDROID,
        app_type=proto.APP_TYPE_WAZE,
        displays=[proto.display(device.screen_w, device.screen_h)],
        os_language_id="en",
        session_uuid=str(uuid.uuid4()),
        current_time_millis=int(time.time() * 1000),
        app_flavor=proto.APP_FLAVOR_ALPHA,
    )
    return proto_base64_line(proto.element(proto.EL_CLIENT_INFO, body))


def build_register_line() -> str:
    return proto_base64_line(proto.element(proto.EL_REGISTER, b""))


def build_login_line(community: str, secret: str) -> str:
    return proto_base64_line(
        proto.element(proto.EL_LOGIN_REQUEST, proto.login_request(community, secret)))


def build_ads_line() -> str:
    return proto_base64_line(proto.element(proto.EL_REPORT_ADS_SETTING, b""))


def build_uid_header(server_session_id: int, secret_key: str) -> str:
    """The ``uid`` request header: base64 of UID{id, secret_key}."""
    return base64.b64encode(proto.uid(server_session_id, secret_key)).decode("ascii")


# --------------------------------------------------- raw command lines

def _f6(value: float) -> str:
    return f"{value:.6f}"


def map_displayed_command(lon_min: float, lat_min: float,
                          lon_max: float, lat_max: float) -> str:
    mid_lon = (lon_min + lon_max) / 2.0
    mid_lat = (lat_min + lat_max) / 2.0
    corners = (f"{_f6(lon_min)},{_f6(lat_max)},{_f6(lon_max)},{_f6(lat_max)},"
               f"{_f6(lon_max)},{_f6(lat_min)},{_f6(lon_min)},{_f6(lat_min)}")
    return (f"MapDisplayed,{corners},{_f6(mid_lon)},{_f6(mid_lat)},67186,{corners}")


def see_me_command(mode: int = 1) -> str:
    """Mode 1 is the handshake SeeMe; mode 2 closes out a report."""
    return f"SeeMe,{mode},2,T,T,T,1,-1,1,7"


def set_mood_command() -> str:
    return "SetMood,1"


def _plain(value: float) -> str:
    """A coordinate formatted the way the Waze client writes it into a
    Location or At line: plain concatenation, not fixed decimals."""
    return repr(float(value))


def location_command(lon: float, lat: float) -> str:
    return f"Location,{_plain(lon)},{_plain(lat)}"


def at_command(lon: float, lat: float, heading: int, from_node: int, to_node: int) -> str:
    """An ``At`` position update carrying the road-snap result; the nodes are
    -1/-1 when nothing matched."""
    return (f"At,{_plain(lon)},{_plain(lat)},0,{heading},1,"
            f"{from_node},{to_node},T,0,-1,-1,0")


def circle_to_box(lon: float, lat: float) -> list[float]:
    """The default box the client draws around a point before a command."""
    return [lon - 0.018, lat - 0.015, lon + 0.018, lat + 0.015]


def handshake_payload(lon: float, lat: float) -> str:
    """SeeMe, SetMood, Location and MapDisplayed, newline-joined, one POST."""
    box = circle_to_box(lon, lat)
    return "\n".join([see_me_command(), set_mood_command(), location_command(lon, lat),
                      map_displayed_command(box[0], box[1], box[2], box[3])])


# ---------------------------------------------------- response parsing

def parse_removed_alert_ids(elements: list[dict[int, list]]) -> list[str]:
    """The uuids of cleared alerts.

    The server signals one with an ``old_command`` line of the form
    ``"RmAlert,<uuid>"``, not a message of its own.
    """
    out = []
    for el in elements:
        command = wire.text(el, proto.EL_OLD_COMMAND).strip()
        if command.startswith("RmAlert,"):
            out.append(command[len("RmAlert,"):].strip())
    return out


def parse_alerts(elements: list[dict[int, list]]) -> list:
    """Every alert the server added in this batch."""
    from .cache import WazeAlert

    out = []
    for el in elements:
        action = wire.sub(el, proto.EL_ADD_ALERT_ACTION)
        if action is None:
            continue
        alert = wire.sub(action, 1)
        if alert is None:
            continue
        info = wire.sub(alert, 2)
        if info is None:
            continue
        position = wire.sub(info, 3)
        if position is None:
            continue
        lon = wire.as_int32(wire.first(position, 101, 0)) / 1_000_000.0
        lat = wire.as_int32(wire.first(position, 102, 0)) / 1_000_000.0
        report_time = 0
        thumbs = None
        street = city = None
        reporting = wire.sub(alert, 3)
        if reporting is not None:
            report_time = wire.first(reporting, 4, 0)
            count = wire.first(reporting, 9, 0)
            if count > 0:
                thumbs = count
            address = wire.sub(reporting, 8)
            if address is not None:
                street = wire.text(address, 2) or None
                city = wire.text(address, 3) or None
        out.append(WazeAlert(
            uuid=wire.text(alert, 6),
            id=wire.as_int64(wire.first(alert, 1, 0)),
            type=proto.type_name(wire.first(info, 1, 0)),
            subtype=proto.subtype_name(wire.first(info, 2, 0)),
            lon=lon,
            lat=lat,
            magvar=wire.as_int32(wire.first(info, 6, 0)),
            pub_millis=report_time * 1000 if report_time > 0 else int(time.time() * 1000),
            n_thumbs_up=thumbs,
            street=street,
            city=city,
        ))
    return out


def normalize_angle_360(degrees: float) -> int:
    """A heading in degrees folded into 0..359."""
    return int(math.fmod(round(degrees), 360) + 360) % 360
