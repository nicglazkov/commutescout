"""The Waze RT client ported into plugins/waze-relay/waze.

The cases come from highway-radar-sabre-plus's own suite (WazeTileCodecTest,
WazeTileParserTest, WazeRtCodecTest, GeoBoxesTest, WazeAlertCacheTest,
WazeConfirmTrackerTest, WazeSessionErrorTest, WazeSessionHandshakeTest,
WazeReportProtoTest), so a port that drifts from the original fails here.

Fixtures are encoded by the little independent writer at the top of this file
rather than by the code under test, the same way the Java tile test
hand-derives its section directory. Nothing here talks to Waze.
"""

from __future__ import annotations

import base64
import struct
import zlib

import httpx
import pytest
from waze import geoboxes, proto, report_codec, rt_codec, tiles, wire
from waze.cache import AlertCache, AlertQueryResult, ConfirmTracker, WazeAlert
from waze.errors import AccountRejected, SessionExpired, WazeOperationError
from waze.roadgeo import LatLon, RoadSegment, angle_diff_180, find_matching_segment
from waze.session import Credentials, WazeSession

# --------------------------------------------- an independent proto writer


def _v(n: int) -> bytes:
    n &= (1 << 64) - 1
    out = bytearray()
    while True:
        chunk, n = n & 0x7F, n >> 7
        out.append(chunk | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _key(field: int, wire_type: int) -> bytes:
    return _v((field << 3) | wire_type)


def _vint(field: int, value: int) -> bytes:
    return _key(field, 0) + _v(value)


def _dbl(field: int, value: float) -> bytes:
    return _key(field, 1) + struct.pack("<d", value)


def _ld(field: int, body: bytes) -> bytes:
    return _key(field, 2) + _v(len(body)) + body


def _str(field: int, value: str) -> bytes:
    return _ld(field, value.encode("utf-8"))


def _batch(*elements: bytes) -> bytes:
    return b"".join(_ld(1001, el) for el in elements)


# ------------------------------------------------------------ wire format


def test_varint_matches_protobuf_and_negatives_sign_extend():
    assert wire.varint(0) == b"\x00"
    assert wire.varint(300) == b"\xac\x02"
    # A negative int32 is its two's complement in 64 bits, so ten bytes.
    assert len(wire.varint(-122_271_200)) == 10
    assert wire.varint(-1) == b"\xff" * 9 + b"\x01"
    assert wire.as_int32(wire.fields(wire.num(1, -122_271_200))[1][0]) == -122_271_200
    # Longitude also arrives as an unsigned 32-bit value on some builds.
    assert wire.as_int32(0xFFFFFFFF - 122_271_200 + 1) == -122_271_200


def test_fields_reads_every_wire_type_and_keeps_unknown_ones():
    body = _vint(1, 7) + _str(2, "hi") + _dbl(3, 1.5) + _vint(9999, 1)
    read = wire.fields(body)
    assert wire.first(read, 1) == 7
    assert wire.text(read, 2) == "hi"
    assert struct.unpack("<d", wire.first(read, 3).to_bytes(8, "little"))[0] == 1.5
    assert 9999 in read


# -------------------------------------------------------------- RT codec


def test_register_login_and_uid_lines_use_the_documented_field_numbers():
    register = rt_codec.build_register_line()
    assert register.startswith("ProtoBase64,")
    assert base64.b64decode(register.split(",", 1)[1]) == _batch(_ld(2219, b""))

    login = rt_codec.build_login_line("community", "secret")
    expected = _batch(_ld(2744, _ld(1, _str(1, "community") + _str(2, "secret"))
                          + _vint(3, 0)))
    assert base64.b64decode(login.split(",", 1)[1]) == expected

    assert base64.b64decode(rt_codec.build_uid_header(833, "abc")) == (
        _vint(1, 833) + _str(2, "abc"))


def test_client_info_line_carries_the_device_and_a_jittered_position():
    from waze.device import DeviceIdentity

    device = DeviceIdentity("Google", "Pixel 8", "15-SDK35", 1080, 2400, "install-1")
    line = rt_codec.build_client_info_line(device, -122.2712, 37.8044)
    elements = proto.elements(base64.b64decode(line.split(",", 1)[1]))
    info = wire.sub(elements[0], proto.EL_CLIENT_INFO)
    assert wire.first(info, 1) == 234                       # protocol
    assert wire.text(info, 3) == "5.17.1.0"                 # client version
    assert wire.text(info, 6) == "Pixel 8"
    assert wire.text(info, 17) == "install-1"
    assert wire.first(info, 18) == 50                       # ANDROID_DEVICE
    position = wire.sub(info, 4)
    lon = wire.as_int32(wire.first(position, 101)) / 1e6
    lat = wire.as_int32(wire.first(position, 102)) / 1e6
    assert abs(lon + 122.2712) < 0.01 and abs(lat - 37.8044) < 0.01
    assert (lon, lat) != (-122.2712, 37.8044)               # jittered, not exact


def test_at_and_see_me_commands_match_the_reference_strings():
    assert rt_codec.at_command(-122.2712, 37.8044, 90, 111, 222) == \
        "At,-122.2712,37.8044,0,90,1,111,222,T,0,-1,-1,0"
    assert rt_codec.at_command(-122.2712, 37.8044, 90, -1, -1) == \
        "At,-122.2712,37.8044,0,90,1,-1,-1,T,0,-1,-1,0"
    assert rt_codec.see_me_command(2) == "SeeMe,2,2,T,T,T,1,-1,1,7"
    assert rt_codec.see_me_command(1) == "SeeMe,1,2,T,T,T,1,-1,1,7"
    assert rt_codec.see_me_command() == "SeeMe,1,2,T,T,T,1,-1,1,7"
    assert rt_codec.location_command(-122.2712, 37.8044) == "Location,-122.2712,37.8044"


def test_map_displayed_command_lists_the_corners_twice_around_the_middle():
    line = rt_codec.map_displayed_command(-122.1, 37.9, -121.9, 38.1)
    assert line.startswith("MapDisplayed,")
    parts = line.split(",")[1:]
    assert len(parts) == 19                      # 8 corners, mid pair, 67186, 8 corners
    assert parts[8:11] == ["-122.000000", "38.000000", "67186"]
    assert parts[:8] == parts[11:]


def test_handshake_payload_is_the_four_client_lines():
    payload = rt_codec.handshake_payload(-122.2712, 37.8044)
    lines = payload.split("\n")
    assert lines[0].startswith("SeeMe,")
    assert lines[1] == "SetMood,1"
    assert lines[2].startswith("Location,")
    assert lines[3].startswith("MapDisplayed,")


def test_removals_arrive_as_rm_alert_lines_not_a_message():
    batch = _batch(_str(2001, "RmAlert,uuid-1"), _str(2001, "RmAlert, uuid-2 "),
                   _str(2001, "SomeOtherCmd,x"), b"")
    assert rt_codec.parse_removed_alert_ids(proto.elements(batch)) == ["uuid-1", "uuid-2"]
    assert rt_codec.parse_removed_alert_ids(proto.elements(b"")) == []


def _alert_element(*, uuid: str = "abc-123", alert_id: int = 42, type_no: int = 2,
                   sub_no: int = 201, lon_micro: int = -122_271_200,
                   lat_micro: int = 37_804_400, azymuth: int = 270,
                   report_time: int = 1_700_000_000, thumbs: int = 3,
                   street: str = "I-280 N", city: str = "San Jose") -> bytes:
    """One AddAlertAction element, the shape a live RT answer carries."""
    info = (_vint(1, type_no) + _vint(2, sub_no)
            + _ld(3, _vint(101, lon_micro) + _vint(102, lat_micro))
            + _vint(6, azymuth))
    reporting = (_vint(4, report_time)
                 + _ld(8, _str(2, street) + _str(3, city))
                 + _vint(9, thumbs))
    realtime = _vint(1, alert_id) + _ld(2, info) + _ld(3, reporting) + _str(6, uuid)
    return _ld(2708, _ld(1, realtime))


def test_parse_alerts_reads_a_captured_response_shape():
    alerts = rt_codec.parse_alerts(proto.elements(_batch(_alert_element())))
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.uuid == "abc-123"
    assert alert.id == 42
    assert alert.type == "POLICE"
    assert alert.subtype == "POLICE_VISIBLE"
    assert alert.lon == pytest.approx(-122.2712)
    assert alert.lat == pytest.approx(37.8044)
    assert alert.magvar == 270
    assert alert.pub_millis == 1_700_000_000_000
    assert alert.n_thumbs_up == 3
    assert alert.street == "I-280 N"
    assert alert.city == "San Jose"


def test_parse_alerts_handles_unnamed_types_missing_reporting_and_no_thumbs():
    element = _alert_element(type_no=0, sub_no=0, thumbs=0)
    alert = rt_codec.parse_alerts(proto.elements(_batch(element)))[0]
    assert alert.type == "UNKNOWN"
    assert alert.subtype == ""
    assert alert.n_thumbs_up is None
    # An alert with no reporting info still parses, with "now" as its time.
    bare = _ld(2708, _ld(1, _ld(2, _ld(3, _vint(101, -122_000_000)
                                       + _vint(102, 38_000_000))) + _str(6, "u")))
    only = rt_codec.parse_alerts(proto.elements(_batch(bare)))[0]
    assert only.pub_millis > 1_600_000_000_000
    assert only.street is None


def test_normalize_angle_360():
    assert rt_codec.normalize_angle_360(-720) == 0
    assert rt_codec.normalize_angle_360(450) == 90
    assert rt_codec.normalize_angle_360(-90) == 270


# ------------------------------------------------------------- geo boxes


def test_circle_to_box_is_centered_and_sized():
    from waze.constants import M_PER_DEG_LAT

    box = geoboxes.circle_to_box(-122.0, 38.0, 8000)
    assert (box[0] + box[2]) / 2 == pytest.approx(-122.0)
    assert (box[1] + box[3]) / 2 == pytest.approx(38.0)
    assert (box[3] - box[1]) / 2 == pytest.approx(8000 / M_PER_DEG_LAT)
    assert box[0] < box[2] and box[1] < box[3]


def test_shrink_halves_the_extent_around_the_same_center():
    box = [-122.1, 37.9, -121.9, 38.1]
    small = geoboxes.shrink(box, 0.5)
    assert (small[0] + small[2]) / 2 == pytest.approx(-122.0)
    assert small[2] - small[0] == pytest.approx((box[2] - box[0]) * 0.5)


def test_shrinking_boxes_step_down_around_the_driver():
    boxes = geoboxes.shrinking_boxes(-122.0, 38.0, 8000, 5)
    assert len(boxes) == 5
    widths = [b[2] - b[0] for b in boxes]
    assert widths == sorted(widths, reverse=True)
    assert widths[1] == pytest.approx(widths[0] * 0.5)
    for box in boxes:
        assert (box[0] + box[2]) / 2 == pytest.approx(-122.0)


# ----------------------------------------------------------- tile decode


def test_coord_to_tile_id_matches_the_expected_literal():
    # lon -122.2712 -> 5772, lat 37.8044 -> 12780, 5772 * 18000 + 12780.
    assert tiles.coord_to_tile_id(-122.2712, 37.8044) == 103908780


def test_build_tile_url_with_and_without_a_session():
    assert tiles.build_tile_url("ctilesgcs-am.waze.com", 833, "abc", 12345) == (
        "https://ctilesgcs-am.waze.com/TileServer/multi-get?reqtype=tileBatch&protocol=2"
        "&sessionid=833&cookie=abc&num=1&variation=PARTIAL_SIMPLIFICATION"
        "&t0=12345&v0=0&p0=42")
    assert tiles.build_tile_url("h", 0, None, 7) == (
        "https://h/TileServer/multi-get?reqtype=tileBatch&protocol=2"
        "&num=1&variation=PARTIAL_SIMPLIFICATION&t0=7&v0=0&p0=42")


def _wrap_wzdf(sections: bytes) -> bytes:
    compressed = zlib.compress(sections)
    return (tiles.MAGIC + len(compressed).to_bytes(4, "little")
            + len(sections).to_bytes(4, "little") + compressed)


def test_tile_parse_returns_empty_without_magic_or_with_too_few_sections():
    assert tiles.parse(b"\x00\x01\x02") == []
    sections = (5).to_bytes(4, "little") + (0).to_bytes(4, "little")
    assert tiles.parse(_wrap_wzdf(sections)) == []


def test_tile_parse_decodes_one_segment_between_two_nodes():
    # The directory holds a cumulative end offset per section; with alignBits
    # 0 the alignment is the identity, so the values are the running totals.
    num_sections, align_bits = 27, 0
    values = [0] * num_sections
    values[9] = 8                              # segments, one 8-byte entry
    for i in range(10, 13):
        values[i] = 8
    values[13] = 16                            # nodes, two 4-byte entries
    for i in range(14, 26):
        values[i] = 16
    values[26] = 28                            # tile header

    base = 8 + num_sections * 4
    body = bytearray(base + 28)
    body[0:4] = num_sections.to_bytes(4, "little")
    body[4:8] = align_bits.to_bytes(4, "little")
    for i, value in enumerate(values):
        body[8 + i * 4:12 + i * 4] = value.to_bytes(4, "little")

    body[base:base + 2] = (0).to_bytes(2, "little")        # from index
    body[base + 2:base + 4] = (1).to_bytes(2, "little")    # to index
    body[base + 4:base + 6] = (0xFFFF).to_bytes(2, "little")  # no polyline deltas

    nodes = base + 8
    body[nodes + 4:nodes + 6] = (20000).to_bytes(2, "little")  # node 1 lon offset

    lon_idx, lat_idx = 5772, 12780
    tile_id = lon_idx * 18000 + lat_idx
    body[base + 16:base + 20] = tile_id.to_bytes(4, "little")

    segments = tiles.parse(_wrap_wzdf(bytes(body)))
    assert len(segments) == 1
    segment = segments[0]
    assert (segment.from_node, segment.to_node) == (0, 1)
    assert segment.segment_id == tile_id * 100000
    assert len(segment.points) == 2
    assert segment.points[0].lat == pytest.approx((lat_idx * 10000 - 90000000) * 1e-6)
    assert segment.points[1].lon == pytest.approx(
        ((lon_idx * 10000 - 180000000) + 20000) * 1e-6)


# ------------------------------------------------------------- road snap


def test_angle_diff_is_symmetric_and_folds_to_180():
    assert angle_diff_180(10, 350) == pytest.approx(20)
    assert angle_diff_180(350, 10) == pytest.approx(20)
    assert angle_diff_180(0, 180) == pytest.approx(180)
    assert angle_diff_180(90, 90) == pytest.approx(0)


def test_find_matching_segment_picks_the_nearest_and_resolves_direction():
    east = RoadSegment(1, 10, 11, 90, [LatLon(37.80, -122.28), LatLon(37.80, -122.26)])
    far = RoadSegment(2, 20, 21, 90, [LatLon(37.90, -122.28), LatLon(37.90, -122.26)])
    match = find_matching_segment(LatLon(37.8001, -122.27), 90, [far, east], 15.0, 50.0)
    assert match is not None and match.segment.segment_id == 1
    assert (match.from_node_directional, match.to_node_directional) == (10, 11)

    # Driving the other way down the same segment flips the node order.
    back = find_matching_segment(LatLon(37.8001, -122.27), 270, [east], 15.0, 50.0)
    assert back is not None and back.reverse
    assert (back.from_node_directional, back.to_node_directional) == (11, 10)

    # Nothing within the distance or the angle matches.
    assert find_matching_segment(LatLon(37.8001, -122.27), 0, [east], 15.0, 50.0) is None
    assert find_matching_segment(LatLon(37.9500, -122.27), 90, [east], 15.0, 50.0) is None


# ----------------------------------------------------------- alert cache


def _alert(uuid: str, thumbs: int = 0) -> WazeAlert:
    return WazeAlert(uuid, 1, "POLICE", "POLICE_VISIBLE", -122.0, 38.0, 0,
                     1_700_000_000_000, thumbs or None, "I-80", "Vallejo")


def _adds(*alerts: WazeAlert) -> AlertQueryResult:
    return AlertQueryResult(list(alerts), [])


def _uuids(alerts) -> list[str]:
    return sorted(a.uuid for a in alerts)


def test_cache_merges_deltas_across_queries():
    cache = AlertCache()
    cache.submit(_adds(_alert("A"), _alert("B")))
    cache.submit(_adds(_alert("C")))          # a delta, not a snapshot
    assert _uuids(cache.snapshot()) == ["A", "B", "C"]


def test_cache_soft_deletes_a_removal_and_keeps_the_rest():
    cache = AlertCache()
    cache.submit(_adds(_alert("A"), _alert("B")))
    cache.submit(AlertQueryResult([], ["A"]))
    assert _uuids(cache.snapshot()) == ["B"]
    assert len(cache) == 2                    # still cached, just hidden


def test_cache_re_add_undoes_a_soft_delete_and_ignores_unknown_removals():
    cache = AlertCache()
    cache.submit(_adds(_alert("A")))
    cache.submit(AlertQueryResult([], ["A"]))
    assert cache.snapshot() == []
    cache.submit(_adds(_alert("A", 1)))
    assert _uuids(cache.snapshot()) == ["A"]
    cache.submit(AlertQueryResult([], ["ZZZ"]))
    assert _uuids(cache.snapshot()) == ["A"]


def test_cache_drops_a_soft_delete_after_its_grace_and_never_caches_an_empty_uuid():
    clock = [1000.0]
    cache = AlertCache(now=lambda: clock[0])
    cache.submit(_adds(_alert("A"), _alert("")))
    assert _uuids(cache.snapshot()) == ["A"]
    cache.submit(AlertQueryResult([], ["A"]))
    clock[0] += 301
    assert cache.snapshot() == []
    assert len(cache) == 0


# -------------------------------------------------------- confirm tracker


def test_confirm_ts_is_the_moment_the_thumbs_up_count_rose():
    clock = [1_700_000_000.0]
    tracker = ConfirmTracker(now=lambda: clock[0])
    assert tracker.confirm_ts("a", 3) is None          # first sighting
    assert tracker.confirm_ts("a", 3) is None          # unchanged
    clock[0] += 60
    risen = tracker.confirm_ts("a", 5)
    assert risen == 1_700_000_060.0
    assert tracker.confirm_ts("a", 5) == risen         # sticky


def test_confirm_ts_treats_no_thumbs_as_zero():
    tracker = ConfirmTracker()
    assert tracker.confirm_ts("a", None) is None
    assert tracker.confirm_ts("a", None) is None
    assert tracker.confirm_ts("a", 2) is not None


# ----------------------------------------------------- error classification


def _server_error(code: int, description: str) -> list[dict[int, list]]:
    return proto.elements(_batch(_ld(2003, _vint(10101, code) + _str(10102, description))))


def _login_error(error_type: int) -> list[dict[int, list]]:
    return proto.elements(_batch(_ld(2224, _vint(2, error_type))))


def test_relogin_and_unknown_userid_mean_the_session_expired():
    with pytest.raises(SessionExpired):
        WazeSession.check_errors(_server_error(500, "Session invalid, please relogin"))
    with pytest.raises(SessionExpired):
        WazeSession.check_errors(_server_error(0, "unknown userid"))


def test_a_client_error_rejects_the_account_and_a_server_error_does_not():
    with pytest.raises(AccountRejected):
        WazeSession.check_errors(_server_error(403, "forbidden"))
    with pytest.raises(WazeOperationError):
        WazeSession.check_errors(_server_error(500, "internal failure"))


def test_a_transient_login_error_must_not_cost_the_account():
    with pytest.raises(WazeOperationError):
        WazeSession.check_errors(_login_error(2))       # INTERNAL_ISSUES
    with pytest.raises(AccountRejected):
        WazeSession.check_errors(_login_error(1))       # WRONG_USER_PASSWORD


def test_an_informational_error_and_a_clean_batch_pass():
    WazeSession.check_errors(_server_error(0, "advisory: scheduled maintenance"))
    WazeSession.check_errors(_server_error(204, "no content"))
    WazeSession.check_errors(proto.elements(_batch(_str(2001, "SomeCmd,x"))))


# ------------------------------------------------------------- handshake


class FakeWaze:
    """A canned RT server: login always succeeds and every command answers
    one RmAlert line."""

    def __init__(self) -> None:
        self.urls: list[str] = []
        self.bodies: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.urls.append(str(request.url))
        self.bodies.append(request.content.decode("utf-8"))
        if request.url.path.endswith("/login"):
            body = _batch(_ld(2745, _ld(1, _vint(1, len(self.urls)) + _str(2, "7")
                                        + _str(3, "secret"))))
            return httpx.Response(200, content=body)
        if request.url.path.endswith("/static"):
            return httpx.Response(200, content=_batch(
                _ld(2220, _str(1, "minted-user") + _str(2, "minted-pass"))))
        return httpx.Response(200, content=_batch(
            _str(2001, f"RmAlert,from-handshake-{len(self.urls)}")))

    def count(self, suffix: str) -> int:
        return sum(1 for u in self.urls if u.endswith(suffix))


PERSISTED = Credentials("community", "secret")


def _session(fake: FakeWaze, *, credentials: Credentials | None = PERSISTED) -> WazeSession:
    client = httpx.AsyncClient(transport=httpx.MockTransport(fake.handler))
    return WazeSession("row", client, credentials=credentials)


async def test_first_prepare_runs_the_handshake_and_hands_its_batch_back():
    fake = FakeWaze()
    session = _session(fake)
    elements = await session.prepare_for_area(37.80, -122.27)
    assert elements is not None, "the handshake batch must be merged, not discarded"
    assert rt_codec.parse_removed_alert_ids(elements) == ["from-handshake-2"]
    assert fake.count("/login") == 1
    assert fake.count("/command") == 1
    assert fake.bodies[-1].startswith("SeeMe,")
    assert "MapDisplayed," in fake.bodies[-1]


async def test_a_second_prepare_on_a_live_session_sends_nothing():
    fake = FakeWaze()
    session = _session(fake)
    await session.prepare_for_area(37.80, -122.27)
    posts = len(fake.urls)
    assert await session.prepare_for_area(37.81, -122.28) is None
    assert len(fake.urls) == posts


async def test_the_handshake_runs_again_after_the_session_is_invalidated():
    fake = FakeWaze()
    session = _session(fake)
    await session.prepare_for_area(37.80, -122.27)
    session.invalidate_session()
    assert await session.prepare_for_area(37.80, -122.27) is not None
    assert fake.count("/login") == 2
    assert fake.count("/command") == 2


async def test_register_mints_an_account_before_the_first_login():
    fake = FakeWaze()
    session = _session(fake, credentials=None)
    await session.prepare_for_area(37.80, -122.27)
    assert session.credentials == Credentials("minted-user", "minted-pass")
    assert fake.count("/static") == 1
    assert fake.count("/login") == 1


async def test_a_command_401_expires_the_session():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/login"):
            return httpx.Response(200, content=_batch(
                _ld(2745, _ld(1, _vint(1, 99) + _str(2, "7") + _str(3, "secret")))))
        return httpx.Response(401)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    session = WazeSession("row", client, credentials=Credentials("c", "s"))
    with pytest.raises(SessionExpired):
        await session.prepare_for_area(37.80, -122.27)
    assert session.server_session_id == 0


async def test_a_login_403_rejects_the_account():
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(403)))
    session = WazeSession("row", client, credentials=Credentials("c", "s"))
    with pytest.raises(AccountRejected):
        await session.prepare_for_area(37.80, -122.27)


# ---------------------------------------------------------- report codec


def test_report_request_encodes_the_documented_shape():
    body = report_codec.build_request(
        lat=37.8044, lon=-122.2712, altitude_m=0.0, heading_deg=90,
        member=report_codec.POLICE, subtype_number=1, is_opposite=False,
        time_delta_s=0, now_ms=1_700_000_000_000, from_node=111, to_node=222)
    expected = (
        _ld(1, _ld(1, _ld(1, _vint(101, -122_271_200) + _vint(102, 37_804_400)
                          + _vint(103, 0))
                   + _dbl(2, 10.0) + _vint(3, 1_700_000_000_000))
             + _ld(2, _vint(1, 111) + _vint(2, 222)))
        + _vint(2, 90)
        + _ld(3, _ld(2, _vint(1, 1)))
        + _vint(4, 1)
        + _ld(5, _vint(1, 1_700_000_000))
        + _vint(7, 1))
    assert body == expected


def test_a_report_without_a_snap_leaves_the_segment_nodes_out():
    body = report_codec.build_request(
        lat=37.8, lon=-122.2, altitude_m=0.0, heading_deg=0,
        member=report_codec.HAZARD, subtype_number=4, is_opposite=True,
        time_delta_s=30, now_ms=1_700_000_000_000, from_node=0, to_node=0)
    position = wire.sub(wire.fields(body), 1)
    assert wire.sub(position, 2) is None
    assert wire.first(wire.fields(body), 4) == proto.SEGMENT_DIRECTION_BACKWARD
    assert wire.first(wire.sub(wire.fields(body), 5), 1) == 1_699_999_970


def test_the_report_line_rides_on_element_2737_and_the_answer_on_2738():
    line = rt_codec.report_payload(_vint(2, 7))
    assert base64.b64decode(line.split(",", 1)[1]) == _batch(_ld(2737, _vint(2, 7)))

    answer = proto.elements(_batch(_ld(2738, _vint(2, 6) + _str(5, "abc"))))
    assert report_codec.report_accepted(answer)
    assert report_codec.report_uuid_from(answer) == "abc"
    assert report_codec.report_points_from(answer) == 6


def test_an_explicit_failure_is_not_an_acceptance():
    failed = proto.elements(_batch(_ld(2738, _vint(1, 2))))     # STATUS FAILURE
    assert not report_codec.report_accepted(failed)
    # A snapped report on an anonymous account comes back with points, the
    # default status and no uuid; that still counts as accepted.
    anonymous = proto.elements(_batch(_ld(2738, _vint(2, 6))))
    assert report_codec.report_accepted(anonymous)
    assert report_codec.report_uuid_from(anonymous) is None
    assert not report_codec.report_accepted(proto.elements(_batch(_str(2001, "x"))))
