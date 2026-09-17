"""Tile-id math and the WZDF road-graph decoder.

Ported from ``WazeTileCodec.java`` and ``WazeTileParser.java``. The tile
server's answer is not protobuf: it is a deflate-compressed section table
whose directory entries are cumulative end offsets, not lengths. Sections 8,
9, 13 and 26 carry the point deltas, the segments, the nodes and the tile
header; the rest are skipped.

The road graph is only needed to snap a report to a road before submitting
it, so a failure here degrades to a position-only report.
"""

from __future__ import annotations

import math
import zlib

from .constants import TILE_NUM_ROWS
from .roadgeo import LatLon, RoadSegment

MAGIC = bytes([87, 90, 68, 70, 1, 0, 0, 0, 0, 0, 3, 0])  # "WZDF" 01000000 00000300


def coord_to_tile_id(lon: float, lat: float) -> int:
    """The global tile id for a coordinate."""
    lon_tile = (int(lon * 1_000_000.0) + 180_000_000) // 10000
    lat_tile = (int(lat * 1_000_000.0) + 90_000_000) // 10000
    return lon_tile * TILE_NUM_ROWS + lat_tile


def build_tile_url(tile_host: str, server_session_id: int, secret_key: str | None,
                   tile_id: int) -> str:
    """The tile server's multi-get URL for one tile. The session part is
    omitted when there is no session yet."""
    session_part = (f"&sessionid={server_session_id}&cookie={secret_key}"
                    if server_session_id != 0 and secret_key is not None else "")
    return (f"https://{tile_host}/TileServer/multi-get?reqtype=tileBatch&protocol=2"
            f"{session_part}&num=1&variation=PARTIAL_SIMPLIFICATION"
            f"&t0={tile_id}&v0=0&p0=42")


def parse(data: bytes) -> list[RoadSegment]:
    """Raw tile-server bytes to road segments.

    Returns an empty list when the WZDF magic is absent or the tile has too
    few sections. Raises when the magic is there but the payload is corrupt,
    which the caller catches around the whole fetch.
    """
    magic_at = data.find(MAGIC)
    if magic_at < 0:
        return []
    compressed_len = _u32(data, magic_at + 12)
    uncompressed_len = _u32(data, magic_at + 16)
    sections = zlib.decompress(data[magic_at + 20:magic_at + 20 + compressed_len])
    if len(sections) != uncompressed_len:
        raise ValueError(f"decompressed {len(sections)} != expected {uncompressed_len}")
    return _parse_sections(sections)


def _parse_sections(data: bytes) -> list[RoadSegment]:
    num_sections = _u32(data, 0)
    align_bits = _u32(data, 4)
    if num_sections <= 26:
        return []

    # The directory holds one u32 per section, each the cumulative end offset
    # of that section relative to the byte after the directory. A section
    # starts at the aligned offset of the previous section's end.
    offsets = [0] * num_sections
    ends = [0] * num_sections
    cursor = 8
    running = 0
    for i in range(num_sections):
        offsets[i] = _align(running, align_bits)
        ends[i] = _u32(data, cursor)
        cursor += 4
        running = ends[i]
    base = cursor

    # Section 26 is the tile header; its first u32 is the tile id.
    header = _section(data, base, offsets[26], ends[26])
    if len(header) < 12:
        return []
    tile_id = _u32(header, 0)
    lon_idx, lat_idx = divmod(tile_id, TILE_NUM_ROWS)

    # Section 13 is the nodes: four bytes each, a u16 lon and lat offset.
    nodes_section = _section(data, base, offsets[13], ends[13])
    nodes = []
    for off in range(0, len(nodes_section) - 3, 4):
        lon_off = _u16(nodes_section, off)
        lat_off = _u16(nodes_section, off + 2)
        nodes.append(LatLon(((lat_idx * 10000 - 90000000) + lat_off) * 1e-6,
                            ((lon_idx * 10000 - 180000000) + lon_off) * 1e-6))

    # Section 8 is the point deltas: a signed i16 pair of micro-degrees each.
    deltas_section = _section(data, base, offsets[8], ends[8])
    deltas = [(_i16(deltas_section, off), _i16(deltas_section, off + 2))
              for off in range(0, len(deltas_section) - 3, 4)]

    # Section 9 is the segments: eight bytes each.
    segments_section = _section(data, base, offsets[9], ends[9])
    segments = []
    for seg_index, off in enumerate(range(0, len(segments_section) - 7, 8)):
        from_idx = _u16(segments_section, off) & 0x7FFF
        to_idx = _u16(segments_section, off + 2) & 0x7FFF
        pt_ref = _u16(segments_section, off + 4)
        if from_idx >= len(nodes) or to_idx >= len(nodes):
            continue
        points = [nodes[from_idx]]
        lon, lat = nodes[from_idx].lon, nodes[from_idx].lat
        if pt_ref != 0xFFFF and pt_ref < len(deltas):
            count = deltas[pt_ref][1]  # the reference entry's second field is the count
            for k in range(pt_ref + 1, min(pt_ref + 1 + count, len(deltas))):
                lon += deltas[k][0] * 1e-6
                lat += deltas[k][1] * 1e-6
                points.append(LatLon(lat, lon))
        points.append(nodes[to_idx])
        segments.append(RoadSegment(
            segment_id=tile_id * 100000 + seg_index,
            from_node=from_idx,
            to_node=to_idx,
            heading=_heading(points[0], points[-1]),
            points=points,
        ))
    return segments


def _heading(a: LatLon, b: LatLon) -> int:
    bearing = math.degrees(math.atan2(
        (b.lon - a.lon) * math.cos(math.radians((a.lat + b.lat) / 2.0)), b.lat - a.lat))
    return round((bearing + 360.0) % 360.0)


def _align(value: int, bits: int) -> int:
    mask = (1 << bits) - 1
    return (~mask) & (value + mask)


def _u32(d: bytes, o: int) -> int:
    return int.from_bytes(d[o:o + 4], "little")


def _u16(d: bytes, o: int) -> int:
    return int.from_bytes(d[o:o + 2], "little")


def _i16(d: bytes, o: int) -> int:
    return int.from_bytes(d[o:o + 2], "little", signed=True)


def _section(data: bytes, base: int, offset: int, end: int) -> bytes:
    start, stop = offset + base, base + end
    if start >= len(data) or stop > len(data) or start >= stop:
        return b""
    return data[start:stop]
