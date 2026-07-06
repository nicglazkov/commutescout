"""Geometry helpers: great-circle distance and Caltrans district lookup."""

from __future__ import annotations

import math

# Rough bounding boxes for the 12 Caltrans districts (generous, may overlap):
# (district, lat_min, lat_max, lon_min, lon_max)
DISTRICT_BOXES: tuple[tuple[int, float, float, float, float], ...] = (
    (1, 38.70, 42.10, -124.60, -122.40),
    (2, 39.30, 42.10, -123.20, -119.95),
    (3, 38.00, 40.60, -122.60, -119.80),
    (4, 36.85, 38.95, -123.70, -121.15),
    (5, 34.25, 37.45, -122.50, -119.30),
    (6, 34.75, 37.70, -121.10, -117.55),
    (7, 33.60, 35.10, -119.70, -117.50),
    (8, 33.35, 35.85, -118.20, -114.05),
    (9, 35.75, 38.80, -119.30, -116.90),
    (10, 36.95, 38.95, -121.70, -119.10),
    (11, 32.45, 33.65, -118.20, -114.30),
    (12, 33.30, 34.00, -118.35, -117.35),
)

ALL_DISTRICTS: tuple[int, ...] = tuple(b[0] for b in DISTRICT_BOXES)


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(
        math.radians(lat2)
    ) * math.sin(d_lon / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def districts_for(lat: float, lon: float, radius_meters: float) -> list[int]:
    """Districts whose bounding box intersects the request circle."""
    lat_pad = radius_meters / 110_574.0
    lon_pad = radius_meters / (111_320.0 * max(0.2, math.cos(math.radians(lat))))
    out = []
    for d, lat_min, lat_max, lon_min, lon_max in DISTRICT_BOXES:
        if (
            lat + lat_pad >= lat_min
            and lat - lat_pad <= lat_max
            and lon + lon_pad >= lon_min
            and lon - lon_pad <= lon_max
        ):
            out.append(d)
    return out
