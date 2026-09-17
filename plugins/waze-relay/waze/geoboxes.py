"""Bounding-box geometry for Waze RT area queries.

Ported from ``GeoBoxes.java``. A single query over a wide viewport is thinned
server side, so minor alerts inside it are dropped. Querying a series of
progressively smaller boxes around the same center defeats that: the smaller
the viewport, the less the server thins it.

Boxes are ``[lon_min, lat_min, lon_max, lat_max]``.
"""

from __future__ import annotations

from .constants import M_PER_DEG_LAT, m_per_deg_lon


def circle_to_box(lon: float, lat: float, radius_m: float) -> list[float]:
    """A lon/lat box of half-width ``radius_m`` around the point."""
    d_lat = radius_m / M_PER_DEG_LAT
    d_lon = radius_m / m_per_deg_lon(lat)
    return [lon - d_lon, lat - d_lat, lon + d_lon, lat + d_lat]


def shrink(box: list[float], factor: float) -> list[float]:
    """The same center, half-extent scaled by ``factor``."""
    cx = (box[0] + box[2]) / 2.0
    cy = (box[1] + box[3]) / 2.0
    hx = ((box[2] - box[0]) / 2.0) * factor
    hy = ((box[3] - box[1]) / 2.0) * factor
    return [cx - hx, cy - hy, cx + hx, cy + hy]


def shrinking_boxes(lon: float, lat: float, radius_m: float, steps: int) -> list[list[float]]:
    """The full-radius box, then each successive box halved."""
    out = [circle_to_box(lon, lat, radius_m)]
    for _ in range(1, steps):
        out.append(shrink(out[-1], 0.5))
    return out
