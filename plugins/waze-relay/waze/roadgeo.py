"""Segment-snap geometry: the nearest road to a point and a heading.

Ported from ``LatLon.java``, ``RoadSegment.java``, ``SegmentMatch.java`` and
``RoadGeo.java``. A report carries the directional nodes of the segment it was
made on, so it has to be snapped to the road graph first.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .constants import M_PER_DEG_LAT, m_per_deg_lon


@dataclass(frozen=True)
class LatLon:
    lat: float
    lon: float


@dataclass(frozen=True)
class RoadSegment:
    """A segment decoded from a tile: two tile-local node indices and the
    polyline between them."""

    segment_id: int
    from_node: int
    to_node: int
    heading: int
    points: list[LatLon]


@dataclass(frozen=True)
class SegmentMatch:
    """A segment matched to a position and heading, with the winning
    direction resolved."""

    segment: RoadSegment
    reverse: bool

    @property
    def from_node_directional(self) -> int:
        return self.segment.to_node if self.reverse else self.segment.from_node

    @property
    def to_node_directional(self) -> int:
        return self.segment.from_node if self.reverse else self.segment.to_node


def compute_heading(a: LatLon, b: LatLon) -> int:
    """The bearing from ``a`` to ``b``, in 0..359."""
    bearing = math.degrees(math.atan2(
        (b.lon - a.lon) * math.cos(math.radians((a.lat + b.lat) / 2.0)), b.lat - a.lat))
    return round((bearing + 360.0) % 360.0)


def find_matching_segment(pos: LatLon, heading: float, segments: list[RoadSegment],
                          max_angle_diff: float, max_dist_m: float) -> SegmentMatch | None:
    """The nearest segment to ``pos`` whose heading, forward or reverse, is
    within ``max_angle_diff`` degrees and which is within ``max_dist_m``.
    ``reverse`` says which direction matched, so the caller can order the
    from and to nodes correctly."""
    best: SegmentMatch | None = None
    best_dist = math.inf
    for segment in segments:
        dist = min_dist_to_polyline_m(pos, segment.points)
        forward = angle_diff_180(segment.heading, heading)
        backward = angle_diff_180(segment.heading + 180, heading)
        if min(forward, backward) <= max_angle_diff and dist <= max_dist_m and dist < best_dist:
            best = SegmentMatch(segment, backward < forward)
            best_dist = dist
    return best


def angle_diff_180(a: float, b: float) -> float:
    """The absolute angular difference between two headings, in 0..180."""
    return abs((((a - b) + 180.0) % 360.0) - 180.0)


def min_dist_to_polyline_m(point: LatLon, points: list[LatLon]) -> float:
    """The smallest perpendicular distance in meters from a point to a
    polyline."""
    if not points:
        return math.inf
    if len(points) == 1:
        return point_to_segment_dist_m(point, points[0], points[0])
    return min(point_to_segment_dist_m(point, points[i], points[i + 1])
               for i in range(len(points) - 1))


def point_to_segment_dist_m(point: LatLon, seg_start: LatLon, seg_end: LatLon) -> float:
    """The perpendicular distance in meters from a point to one segment, over
    a meters projection local to the segment's average latitude."""
    per_deg_lon = m_per_deg_lon((seg_start.lat + seg_end.lat) / 2.0)
    ax, ay = seg_start.lon * per_deg_lon, seg_start.lat * M_PER_DEG_LAT
    bx, by = seg_end.lon * per_deg_lon, seg_end.lat * M_PER_DEG_LAT
    px, py = point.lon * per_deg_lon, point.lat * M_PER_DEG_LAT
    dx, dy = bx - ax, by - ay
    len_sq = dx * dx + dy * dy
    if len_sq == 0.0:
        return math.hypot(px - ax, py - ay)
    rx, ry = px - ax, py - ay
    t = max(0.0, min(1.0, (rx * dx + ry * dy) / len_sq))
    return math.hypot(rx - dx * t, ry - dy * t)
